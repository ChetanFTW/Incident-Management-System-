"""
PostgreSQL ORM models.
All transitions are transactional — never update state directly,
always go through the WorkItem state machine (patterns/state_machine.py).
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    UUID,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


# ── Enums ────────────────────────────────────────────────────────────────────

class WorkItemStatus(str, PyEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Priority(str, PyEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class ComponentType(str, PyEnum):
    RDBMS = "RDBMS"
    CACHE = "CACHE"
    API = "API"
    MCP_HOST = "MCP_HOST"
    ASYNC_QUEUE = "ASYNC_QUEUE"
    NOSQL = "NOSQL"


class RootCauseCategory(str, PyEnum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    CODE_BUG = "CODE_BUG"
    CONFIGURATION = "CONFIGURATION"
    DEPENDENCY = "DEPENDENCY"
    CAPACITY = "CAPACITY"
    NETWORK = "NETWORK"
    SECURITY = "SECURITY"
    UNKNOWN = "UNKNOWN"


# ── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    work_items: Mapped[list["WorkItem"]] = relationship(
        "WorkItem", back_populates="assignee", lazy="selectin"
    )


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    component_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    component_type: Mapped[ComponentType] = mapped_column(
        Enum(ComponentType), nullable=False
    )
    priority: Mapped[Priority] = mapped_column(Enum(Priority), nullable=False, index=True)
    status: Mapped[WorkItemStatus] = mapped_column(
        Enum(WorkItemStatus), nullable=False, default=WorkItemStatus.OPEN, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Signal tracking
    signal_count: Mapped[int] = mapped_column(Integer, default=1)
    first_signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Resolution tracking
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mttr_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Ownership
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assignee: Mapped["User | None"] = relationship("User", back_populates="work_items")
    rca: Mapped["RCA | None"] = relationship(
        "RCA", back_populates="work_item", uselist=False, lazy="selectin"
    )
    transitions: Mapped[list["StateTransition"]] = relationship(
        "StateTransition", back_populates="work_item", lazy="selectin",
        order_by="StateTransition.transitioned_at"
    )


class RCA(Base):
    """
    Root Cause Analysis — mandatory before a WorkItem can be CLOSED.
    All fields must be non-null/non-empty for the record to be considered complete.
    """
    __tablename__ = "rcas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id"), unique=True, nullable=False
    )

    # Timing
    incident_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    incident_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Classification
    root_cause_category: Mapped[RootCauseCategory] = mapped_column(
        Enum(RootCauseCategory), nullable=False
    )

    # Narrative fields — all mandatory
    root_cause_description: Mapped[str] = mapped_column(Text, nullable=False)
    fix_applied: Mapped[str] = mapped_column(Text, nullable=False)
    prevention_steps: Mapped[str] = mapped_column(Text, nullable=False)

    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    work_item: Mapped["WorkItem"] = relationship("WorkItem", back_populates="rca")

    def is_complete(self) -> bool:
        """All narrative fields must be non-empty strings."""
        return all([
            self.root_cause_description and self.root_cause_description.strip(),
            self.fix_applied and self.fix_applied.strip(),
            self.prevention_steps and self.prevention_steps.strip(),
            self.root_cause_category is not None,
            self.incident_start is not None,
            self.incident_end is not None,
        ])


class StateTransition(Base):
    """Audit trail of every status change for a WorkItem."""
    __tablename__ = "state_transitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id"), nullable=False, index=True
    )
    from_status: Mapped[WorkItemStatus | None] = mapped_column(
        Enum(WorkItemStatus), nullable=True
    )
    to_status: Mapped[WorkItemStatus] = mapped_column(
        Enum(WorkItemStatus), nullable=False
    )
    transitioned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    work_item: Mapped["WorkItem"] = relationship("WorkItem", back_populates="transitions")
