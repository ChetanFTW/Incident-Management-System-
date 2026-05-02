import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.postgres import get_session
from app.db.redis_client import cache_invalidate_dashboard
from app.models.pg_models import WorkItem, WorkItemStatus, RCA as RCAModel
from app.models.schemas import RCACreateRequest, RCAResponse
from app.core.security import get_current_user

router = APIRouter(prefix="/incidents", tags=["rca"])


@router.post("/{incident_id}/rca", response_model=RCAResponse, status_code=201)
async def submit_rca(
    incident_id: uuid.UUID,
    body: RCACreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Submit RCA for an incident.
    - Incident must be in RESOLVED state (not OPEN/INVESTIGATING)
    - All text fields are mandatory (min 20 chars each)
    - incident_end must be after incident_start
    - Replaces existing RCA if re-submitted
    """
    async with session.begin():
        result = await session.execute(select(WorkItem).where(WorkItem.id == incident_id))
        wi = result.scalar_one_or_none()
        if not wi:
            raise HTTPException(status_code=404, detail="Incident not found")

        if wi.status not in (WorkItemStatus.RESOLVED, WorkItemStatus.CLOSED):
            raise HTTPException(
                status_code=422,
                detail=f"RCA can only be submitted for RESOLVED incidents. "
                       f"Current status: {wi.status.value}",
            )

        # Upsert RCA
        rca_result = await session.execute(
            select(RCAModel).where(RCAModel.work_item_id == incident_id)
        )
        existing_rca = rca_result.scalar_one_or_none()

        user_id = uuid.UUID(current_user["sub"]) if "sub" in current_user else None

        if existing_rca:
            # Update existing
            existing_rca.incident_start = body.incident_start
            existing_rca.incident_end = body.incident_end
            existing_rca.root_cause_category = body.root_cause_category
            existing_rca.root_cause_description = body.root_cause_description
            existing_rca.fix_applied = body.fix_applied
            existing_rca.prevention_steps = body.prevention_steps
            existing_rca.submitted_by_id = user_id
            existing_rca.submitted_at = datetime.now(timezone.utc)
            rca = existing_rca
        else:
            rca = RCAModel(
                work_item_id=incident_id,
                incident_start=body.incident_start,
                incident_end=body.incident_end,
                root_cause_category=body.root_cause_category,
                root_cause_description=body.root_cause_description,
                fix_applied=body.fix_applied,
                prevention_steps=body.prevention_steps,
                submitted_by_id=user_id,
            )
            session.add(rca)

    await cache_invalidate_dashboard()
    return RCAResponse.model_validate(rca)
