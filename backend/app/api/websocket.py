"""
WebSocket feed — broadcasts real-time incident updates to all connected clients.
"""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.postgres import AsyncSessionLocal
from app.models.pg_models import WorkItem

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# All active WebSocket connections
_connections: list[WebSocket] = []


@router.websocket("/ws/feed")
async def websocket_feed(ws: WebSocket):
    await ws.accept()
    _connections.append(ws)
    logger.info("WS client connected. Total: %d", len(_connections))

    try:
        # Send current snapshot on connect
        snapshot = await get_active_incidents_snapshot()
        await ws.send_text(json.dumps({"type": "snapshot", "data": snapshot}))

        # Keep alive — ping every 20s
        while True:
            await asyncio.sleep(20)
            await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WS error: %s", e)
    finally:
        _connections.remove(ws)
        logger.info("WS client disconnected. Total: %d", len(_connections))


async def broadcast_incident_update(work_item_id: str, event_type: str, data: dict):
    """Call this from API routes when an incident changes."""
    if not _connections:
        return
    message = json.dumps({
        "type": event_type,
        "work_item_id": work_item_id,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }, default=str)
    dead = []
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections.remove(ws)


async def get_active_incidents_snapshot() -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorkItem)
            .where(WorkItem.status != "CLOSED")
            .order_by(WorkItem.priority, WorkItem.last_signal_at.desc())
            .limit(50)
        )
        items = result.scalars().all()
        return [
            {
                "id": str(i.id),
                "component_id": i.component_id,
                "priority": i.priority.value,
                "status": i.status.value,
                "title": i.title,
                "signal_count": i.signal_count,
                "first_signal_at": i.first_signal_at.isoformat(),
                "last_signal_at": i.last_signal_at.isoformat(),
            }
            for i in items
        ]
