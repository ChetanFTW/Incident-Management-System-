"""
Signal Processor — the heart of the IMS backend.

Architecture:
  ┌─────────────┐    asyncio.Queue    ┌──────────────────┐
  │  POST /signals │ ──────────────► │  worker_loop()   │
  │  (HTTP fast)   │  (backpressure)  │  (DB writes slow)│
  └─────────────┘                    └──────────────────┘

Key behaviours:
  - Queue max 50,000 items — if full, ingestor returns 429 immediately
    (DB slowness NEVER crashes the ingestion endpoint)
  - Debounce: 100 signals for same component_id within 10s → single WorkItem
  - Throughput metrics printed to console every 5s
  - Auto-escalation: P2 with >500 signals in 60s → promoted to P1
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field

from sqlalchemy import select, func
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.metrics import (
    signals_ingested_total,
    signals_debounced_total,
    queue_depth_gauge,
    active_incidents_gauge,
    incidents_created_total,
    throughput_gauge,
)
from app.db.postgres import AsyncSessionLocal
from app.db.signal_repo import insert_signal, get_signal_rate
from app.db.redis_client import cache_invalidate_dashboard
from app.models.pg_models import WorkItem, WorkItemStatus, Priority, StateTransition
from app.models.schemas import SignalPayload
from app.patterns.alert_strategy import (
    AlertContext, get_strategy, resolve_priority, COMPONENT_PRIORITY_MAP
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Shared queue (module-level singleton) ─────────────────────────────────────
signal_queue: asyncio.Queue[tuple[SignalPayload, datetime]] = asyncio.Queue(
    maxsize=settings.queue_max_size
)

# ── Debounce window ───────────────────────────────────────────────────────────
@dataclass
class DebounceWindow:
    work_item_id: str
    first_seen: float
    count: int = 1
    signal_ids: list[str] = field(default_factory=list)


_debounce: dict[str, DebounceWindow] = {}
_debounce_lock = asyncio.Lock()

# ── Throughput tracking ───────────────────────────────────────────────────────
_signal_count_window: int = 0
_tasks: list[asyncio.Task] = []


async def enqueue_signal(payload: SignalPayload) -> tuple[bool, str]:
    """
    Called by the HTTP ingestion endpoint.
    Returns (enqueued: bool, reason: str).
    Non-blocking — never waits for DB.
    """
    received_at = datetime.now(timezone.utc)
    try:
        signal_queue.put_nowait((payload, received_at))
        queue_depth_gauge.set(signal_queue.qsize())
        signals_ingested_total.labels(
            component_type=payload.component_type.value,
            severity=payload.severity.value,
        ).inc()
        global _signal_count_window
        _signal_count_window += 1
        return True, "accepted"
    except asyncio.QueueFull:
        return False, "Queue at capacity — backpressure triggered"


async def start_workers():
    """Start background tasks on app startup."""
    num_workers = 4
    for i in range(num_workers):
        task = asyncio.create_task(worker_loop(f"worker-{i}"), name=f"signal-worker-{i}")
        _tasks.append(task)
    task = asyncio.create_task(metrics_reporter(), name="metrics-reporter")
    _tasks.append(task)
    task = asyncio.create_task(debounce_janitor(), name="debounce-janitor")
    _tasks.append(task)
    logger.info("Started %d signal workers + metrics reporter + debounce janitor", num_workers)


async def stop_workers():
    for t in _tasks:
        t.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    logger.info("All workers stopped")


# ── Worker loop ───────────────────────────────────────────────────────────────

async def worker_loop(name: str):
    logger.info("%s started", name)
    while True:
        try:
            payload, received_at = await signal_queue.get()
            queue_depth_gauge.set(signal_queue.qsize())
            await process_signal(payload, received_at)
            signal_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("%s error processing signal: %s", name, e)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
async def process_signal(payload: SignalPayload, received_at: datetime):
    """Debounce → create/update WorkItem → persist signal → alert."""
    async with _debounce_lock:
        window = _debounce.get(payload.component_id)
        now = time.monotonic()

        if window and (now - window.first_seen) < settings.debounce_window_seconds:
            # Within debounce window — link to existing work item
            window.count += 1
            work_item_id = window.work_item_id
            is_new = False

            if window.count > settings.debounce_max_signals:
                # Flush and start a new window
                del _debounce[payload.component_id]
                is_new = False
            else:
                signals_debounced_total.inc()
        else:
            # New window
            work_item_id = str(uuid.uuid4())
            _debounce[payload.component_id] = DebounceWindow(
                work_item_id=work_item_id,
                first_seen=now,
            )
            is_new = True

    # Persist signal to MongoDB (audit log)
    await insert_signal(payload, work_item_id, received_at)

    # Create or update WorkItem in PostgreSQL
    if is_new:
        await create_work_item(payload, work_item_id, received_at)
    else:
        await increment_signal_count(work_item_id, received_at)

    # Auto-escalation check (P2 → P1 if volume spikes)
    await check_auto_escalation(payload, work_item_id)


async def create_work_item(payload: SignalPayload, work_item_id: str, received_at: datetime):
    priority = resolve_priority(payload.component_type, payload.severity)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            wi = WorkItem(
                id=uuid.UUID(work_item_id),
                component_id=payload.component_id,
                component_type=payload.component_type,
                priority=priority,
                status=WorkItemStatus.OPEN,
                title=f"{payload.component_type.value} failure: {payload.component_id}",
                description=payload.message,
                signal_count=1,
                first_signal_at=received_at,
                last_signal_at=received_at,
            )
            session.add(wi)
            session.add(StateTransition(
                work_item_id=uuid.UUID(work_item_id),
                from_status=None,
                to_status=WorkItemStatus.OPEN,
                note="Auto-created by signal processor",
            ))

    incidents_created_total.labels(priority=priority.value).inc()
    active_incidents_gauge.labels(priority=priority.value).inc()
    await cache_invalidate_dashboard()

    # Fire alert strategy
    ctx = AlertContext(
        work_item_id=work_item_id,
        component_id=payload.component_id,
        component_type=payload.component_type,
        priority=priority,
        title=f"{payload.component_type.value} failure: {payload.component_id}",
        signal_count=1,
    )
    await get_strategy(priority).send(ctx)
    logger.info("Created WorkItem %s [%s] for %s", work_item_id, priority.value, payload.component_id)


async def increment_signal_count(work_item_id: str, received_at: datetime):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(WorkItem).where(WorkItem.id == uuid.UUID(work_item_id))
            )
            wi = result.scalar_one_or_none()
            if wi:
                wi.signal_count += 1
                wi.last_signal_at = received_at


async def check_auto_escalation(payload: SignalPayload, work_item_id: str):
    """Promote P2 → P1 if >500 signals in last 60 seconds."""
    from datetime import timedelta
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkItem).where(WorkItem.id == uuid.UUID(work_item_id))
        )
        wi = result.scalar_one_or_none()
        if not wi or wi.priority != Priority.P2:
            return

    since = datetime.now(timezone.utc) - timedelta(seconds=60)
    count = await get_signal_rate(payload.component_id, since)
    if count > 500:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(WorkItem).where(WorkItem.id == uuid.UUID(work_item_id))
                )
                wi = result.scalar_one_or_none()
                if wi and wi.priority == Priority.P2:
                    wi.priority = Priority.P1
                    logger.warning(
                        "AUTO-ESCALATED %s from P2 → P1 (%d signals/60s)", work_item_id, count
                    )
                    await cache_invalidate_dashboard()


# ── Metrics reporter ──────────────────────────────────────────────────────────

async def metrics_reporter():
    interval = settings.metrics_interval_seconds
    while True:
        await asyncio.sleep(interval)
        global _signal_count_window
        rate = _signal_count_window / interval
        _signal_count_window = 0
        throughput_gauge.set(rate)
        logger.info(
            "📊 Throughput: %.1f signals/sec | Queue depth: %d",
            rate, signal_queue.qsize(),
        )


# ── Debounce janitor ──────────────────────────────────────────────────────────

async def debounce_janitor():
    """Purge stale debounce windows every 30s to prevent memory leak."""
    while True:
        await asyncio.sleep(30)
        now = time.monotonic()
        async with _debounce_lock:
            stale = [
                k for k, v in _debounce.items()
                if (now - v.first_seen) > settings.debounce_window_seconds * 3
            ]
            for k in stale:
                del _debounce[k]
        if stale:
            logger.debug("Debounce janitor purged %d stale windows", len(stale))
