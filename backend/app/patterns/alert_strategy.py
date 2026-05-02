"""
Strategy Pattern — pluggable alerting logic per component priority.

P0 (RDBMS/critical): Console critical + Slack webhook (if configured)
P1 (API/Queue):      Console error
P2 (Cache/NoSQL):    Console warning

Swap strategies by passing a different AlertStrategy implementation.
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.pg_models import ComponentType, Priority

logger = logging.getLogger(__name__)


@dataclass
class AlertContext:
    work_item_id: str
    component_id: str
    component_type: ComponentType
    priority: Priority
    title: str
    signal_count: int


class AlertStrategy(ABC):
    @abstractmethod
    async def send(self, ctx: AlertContext) -> None: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


# ── Concrete strategies ───────────────────────────────────────────────────────

class P0CriticalAlert(AlertStrategy):
    """
    P0 — RDBMS or any critical component failure.
    In production: page on-call, flood Slack, open PagerDuty.
    Here: structured critical log (hook in your Slack webhook via env var).
    """
    @property
    def name(self) -> str:
        return "P0_CRITICAL"

    async def send(self, ctx: AlertContext) -> None:
        logger.critical(
            "🚨 P0 INCIDENT | work_item=%s | component=%s | signals=%d | %s",
            ctx.work_item_id, ctx.component_id, ctx.signal_count, ctx.title,
        )
        # Hook: POST to Slack/PagerDuty webhook here if SLACK_WEBHOOK_URL env var set


class P1HighAlert(AlertStrategy):
    """P1 — API or async queue failure."""
    @property
    def name(self) -> str:
        return "P1_HIGH"

    async def send(self, ctx: AlertContext) -> None:
        logger.error(
            "🔴 P1 INCIDENT | work_item=%s | component=%s | signals=%d | %s",
            ctx.work_item_id, ctx.component_id, ctx.signal_count, ctx.title,
        )


class P2MediumAlert(AlertStrategy):
    """P2 — Cache or NoSQL degradation."""
    @property
    def name(self) -> str:
        return "P2_MEDIUM"

    async def send(self, ctx: AlertContext) -> None:
        logger.warning(
            "🟡 P2 INCIDENT | work_item=%s | component=%s | signals=%d | %s",
            ctx.work_item_id, ctx.component_id, ctx.signal_count, ctx.title,
        )


# ── Strategy selector ─────────────────────────────────────────────────────────

# Maps component type → default priority
COMPONENT_PRIORITY_MAP: dict[ComponentType, Priority] = {
    ComponentType.RDBMS:       Priority.P0,
    ComponentType.MCP_HOST:    Priority.P0,
    ComponentType.API:         Priority.P1,
    ComponentType.ASYNC_QUEUE: Priority.P1,
    ComponentType.CACHE:       Priority.P2,
    ComponentType.NOSQL:       Priority.P2,
}

_STRATEGY_MAP: dict[Priority, AlertStrategy] = {
    Priority.P0: P0CriticalAlert(),
    Priority.P1: P1HighAlert(),
    Priority.P2: P2MediumAlert(),
}


def get_strategy(priority: Priority) -> AlertStrategy:
    return _STRATEGY_MAP[priority]


def resolve_priority(component_type: ComponentType, override: Priority | None = None) -> Priority:
    if override:
        return override
    return COMPONENT_PRIORITY_MAP.get(component_type, Priority.P1)
