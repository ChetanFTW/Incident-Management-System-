"""
Pydantic v2 schemas — strict validation for all API payloads.
Separate from ORM models intentionally (clean separation of concerns).
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.pg_models import (
    ComponentType,
    Priority,
    RootCauseCategory,
    WorkItemStatus,
)


# ── Signal schemas ────────────────────────────────────────────────────────────

class SignalPayload(BaseModel):
    component_id: str = Field(..., min_length=1, max_length=128)
    component_type: ComponentType
    error_code: str | None = Field(None, max_length=64)
    message: str = Field(..., min_length=1, max_length=2048)
    severity: Priority
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None

    @field_validator("component_id")
    @classmethod
    def uppercase_component_id(cls, v: str) -> str:
        return v.upper().strip()


class SignalIngestResponse(BaseModel):
    accepted: bool
    signal_id: str
    work_item_id: str | None = None
    debounced: bool = False
    message: str


# ── WorkItem schemas ──────────────────────────────────────────────────────────

class StateTransitionResponse(BaseModel):
    id: uuid.UUID
    from_status: WorkItemStatus | None
    to_status: WorkItemStatus
    note: str | None
    transitioned_at: datetime
    model_config = {"from_attributes": True}


class RCAResponse(BaseModel):
    id: uuid.UUID
    work_item_id: uuid.UUID
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    root_cause_description: str
    fix_applied: str
    prevention_steps: str
    submitted_at: datetime
    model_config = {"from_attributes": True}


class WorkItemResponse(BaseModel):
    id: uuid.UUID
    component_id: str
    component_type: ComponentType
    priority: Priority
    status: WorkItemStatus
    title: str
    description: str | None
    signal_count: int
    first_signal_at: datetime
    last_signal_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    mttr_seconds: float | None
    created_at: datetime
    updated_at: datetime
    rca: RCAResponse | None = None
    transitions: list[StateTransitionResponse] = []
    model_config = {"from_attributes": True}


class WorkItemListResponse(BaseModel):
    items: list[WorkItemResponse]
    total: int
    page: int
    page_size: int


class StateTransitionRequest(BaseModel):
    to_status: WorkItemStatus
    note: str | None = Field(None, max_length=1024)


# ── RCA schemas ───────────────────────────────────────────────────────────────

class RCACreateRequest(BaseModel):
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    root_cause_description: str = Field(..., min_length=20)
    fix_applied: str = Field(..., min_length=20)
    prevention_steps: str = Field(..., min_length=20)

    @model_validator(mode="after")
    def end_after_start(self) -> "RCACreateRequest":
        if self.incident_end <= self.incident_start:
            raise ValueError("incident_end must be after incident_start")
        return self


# ── Auth schemas ──────────────────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    username: str
    password: str


# ── MongoDB signal document ───────────────────────────────────────────────────

class SignalDocument(BaseModel):
    signal_id: str
    work_item_id: str | None
    component_id: str
    component_type: str
    error_code: str | None
    message: str
    severity: str
    metadata: dict[str, Any]
    received_at: datetime
    original_timestamp: datetime | None
    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    components: dict[str, str]
