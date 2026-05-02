from fastapi import APIRouter, Depends, HTTPException, status
from app.models.schemas import SignalPayload, SignalIngestResponse
from app.workers.signal_processor import enqueue_signal
from app.core.rate_limiter import check_signal_rate_limit
from app.core.security import get_current_user
import uuid

router = APIRouter(prefix="/signals", tags=["ingestion"])


@router.post(
    "",
    response_model=SignalIngestResponse,
    status_code=202,
    dependencies=[Depends(check_signal_rate_limit)],
)
async def ingest_signal(
    payload: SignalPayload,
    current_user: dict = Depends(get_current_user),
):
    """
    High-throughput signal ingestion endpoint.
    Immediately enqueues signal — never waits for DB.
    Returns 202 Accepted (not 200) because processing is async.
    Returns 429 if queue is full (backpressure).
    """
    enqueued, reason = await enqueue_signal(payload)
    if not enqueued:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=reason)

    return SignalIngestResponse(
        accepted=True,
        signal_id=str(uuid.uuid4()),
        debounced=False,
        message=reason,
    )
