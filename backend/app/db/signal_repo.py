"""
MongoDB repository for raw signal documents.
This is the audit log / data lake — every signal ever received is stored here.
"""
import uuid
from datetime import datetime

from app.db.mongo import get_db
from app.models.schemas import SignalPayload


async def insert_signal(
    payload: SignalPayload,
    work_item_id: str | None,
    received_at: datetime,
) -> str:
    """Persist a raw signal. Returns the signal_id."""
    signal_id = str(uuid.uuid4())
    doc = {
        "signal_id": signal_id,
        "work_item_id": work_item_id,
        "component_id": payload.component_id,
        "component_type": payload.component_type.value,
        "error_code": payload.error_code,
        "message": payload.message,
        "severity": payload.severity.value,
        "metadata": payload.metadata,
        "received_at": received_at,
        "original_timestamp": payload.timestamp,
    }
    db = get_db()
    await db.signals.insert_one(doc)
    return signal_id


async def get_signals_for_work_item(
    work_item_id: str, limit: int = 100, skip: int = 0
) -> list[dict]:
    """Fetch raw signals linked to a work item — newest first."""
    db = get_db()
    cursor = (
        db.signals.find({"work_item_id": work_item_id})
        .sort("received_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    # Remove MongoDB internal _id before returning
    for doc in docs:
        doc.pop("_id", None)
    return docs


async def count_signals_for_work_item(work_item_id: str) -> int:
    db = get_db()
    return await db.signals.count_documents({"work_item_id": work_item_id})


async def get_signal_rate(component_id: str, since: datetime) -> int:
    """Count signals for a component since a given time — used for auto-escalation."""
    db = get_db()
    return await db.signals.count_documents({
        "component_id": component_id,
        "received_at": {"$gte": since},
    })
