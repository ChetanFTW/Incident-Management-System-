import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.postgres import get_session
from app.db.redis_client import cache_get, cache_set, cache_invalidate_dashboard, DASHBOARD_CACHE_KEY
from app.db.signal_repo import get_signals_for_work_item, count_signals_for_work_item
from app.models.pg_models import WorkItem, WorkItemStatus, StateTransition, RCA
from app.models.schemas import (
    WorkItemResponse, WorkItemListResponse,
    StateTransitionRequest, StateTransitionResponse,
)
from app.patterns.state_machine import WorkItemStateMachine, InvalidTransitionError, RCARequiredError
from app.core.security import get_current_user
from app.core.metrics import active_incidents_gauge, incidents_closed_total, mttr_seconds_histogram

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=WorkItemListResponse)
async def list_incidents(
    status: WorkItemStatus | None = None,
    priority: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    # Try cache for default query (no filters, page 1)
    if not status and not priority and page == 1:
        cached = await cache_get(DASHBOARD_CACHE_KEY)
        if cached:
            return cached

    query = select(WorkItem)
    if status:
        query = query.where(WorkItem.status == status)
    if priority:
        query = query.where(WorkItem.priority == priority)

    # Sort: P0 first, then by last signal time
    query = query.order_by(WorkItem.priority, WorkItem.last_signal_at.desc())

    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    items = result.scalars().all()

    response = WorkItemListResponse(
        items=[WorkItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )

    # Cache default query
    if not status and not priority and page == 1:
        await cache_set(DASHBOARD_CACHE_KEY, response.model_dump(mode="json"))

    return response


@router.get("/{incident_id}")
async def get_incident(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await session.execute(select(WorkItem).where(WorkItem.id == incident_id))
    wi = result.scalar_one_or_none()
    if not wi:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Fetch raw signals from MongoDB
    signals = await get_signals_for_work_item(str(incident_id), limit=50)
    signal_count = await count_signals_for_work_item(str(incident_id))

    data = WorkItemResponse.model_validate(wi).model_dump(mode="json")
    data["raw_signals"] = signals
    data["total_signals"] = signal_count
    return data


@router.patch("/{incident_id}/state", response_model=StateTransitionResponse)
async def transition_state(
    incident_id: uuid.UUID,
    body: StateTransitionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    async with session.begin():
        result = await session.execute(select(WorkItem).where(WorkItem.id == incident_id))
        wi = result.scalar_one_or_none()
        if not wi:
            raise HTTPException(status_code=404, detail="Incident not found")

        rca_complete = wi.rca is not None and wi.rca.is_complete()
        machine = WorkItemStateMachine(wi.status)

        try:
            new_status = machine.transition(body.to_status, rca_complete=rca_complete)
        except RCARequiredError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except InvalidTransitionError as e:
            raise HTTPException(status_code=409, detail=str(e))

        old_status = wi.status
        wi.status = new_status

        now = datetime.now(timezone.utc)
        if new_status == WorkItemStatus.RESOLVED:
            wi.resolved_at = now
            mttr = WorkItemStateMachine.calculate_mttr(wi.first_signal_at, now)
            wi.mttr_seconds = mttr
            mttr_seconds_histogram.observe(mttr)
        if new_status == WorkItemStatus.CLOSED:
            wi.closed_at = now
            active_incidents_gauge.labels(priority=wi.priority.value).dec()
            incidents_closed_total.inc()

        transition = StateTransition(
            work_item_id=incident_id,
            from_status=old_status,
            to_status=new_status,
            note=body.note,
        )
        session.add(transition)

    await cache_invalidate_dashboard()
    return StateTransitionResponse.model_validate(transition)
