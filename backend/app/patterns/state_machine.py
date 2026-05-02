"""
State Pattern — WorkItem lifecycle management.

Valid transitions:
  OPEN → INVESTIGATING
  INVESTIGATING → RESOLVED
  RESOLVED → CLOSED  (only if RCA is complete)
  RESOLVED → INVESTIGATING  (re-open)

Any other transition raises InvalidTransitionError.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.models.pg_models import WorkItemStatus


class InvalidTransitionError(Exception):
    pass


class RCARequiredError(Exception):
    pass


# ── Abstract state ────────────────────────────────────────────────────────────

class WorkItemState(ABC):
    @abstractmethod
    def transition_to(self, target: WorkItemStatus, rca_complete: bool) -> WorkItemStatus:
        ...

    @property
    @abstractmethod
    def status(self) -> WorkItemStatus:
        ...


# ── Concrete states ───────────────────────────────────────────────────────────

class OpenState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.OPEN

    def transition_to(self, target: WorkItemStatus, rca_complete: bool) -> WorkItemStatus:
        if target == WorkItemStatus.INVESTIGATING:
            return WorkItemStatus.INVESTIGATING
        raise InvalidTransitionError(
            f"Cannot move from OPEN to {target}. Only INVESTIGATING is allowed."
        )


class InvestigatingState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.INVESTIGATING

    def transition_to(self, target: WorkItemStatus, rca_complete: bool) -> WorkItemStatus:
        if target == WorkItemStatus.RESOLVED:
            return WorkItemStatus.RESOLVED
        raise InvalidTransitionError(
            f"Cannot move from INVESTIGATING to {target}. Only RESOLVED is allowed."
        )


class ResolvedState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.RESOLVED

    def transition_to(self, target: WorkItemStatus, rca_complete: bool) -> WorkItemStatus:
        if target == WorkItemStatus.CLOSED:
            if not rca_complete:
                raise RCARequiredError(
                    "RCA must be complete before closing an incident. "
                    "Submit a full RCA (root_cause_description, fix_applied, prevention_steps) first."
                )
            return WorkItemStatus.CLOSED
        if target == WorkItemStatus.INVESTIGATING:
            return WorkItemStatus.INVESTIGATING  # allow re-open
        raise InvalidTransitionError(
            f"Cannot move from RESOLVED to {target}."
        )


class ClosedState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.CLOSED

    def transition_to(self, target: WorkItemStatus, rca_complete: bool) -> WorkItemStatus:
        raise InvalidTransitionError("CLOSED is a terminal state. No further transitions allowed.")


# ── State machine ─────────────────────────────────────────────────────────────

_STATE_MAP: dict[WorkItemStatus, WorkItemState] = {
    WorkItemStatus.OPEN: OpenState(),
    WorkItemStatus.INVESTIGATING: InvestigatingState(),
    WorkItemStatus.RESOLVED: ResolvedState(),
    WorkItemStatus.CLOSED: ClosedState(),
}


class WorkItemStateMachine:
    """
    Wraps a WorkItem's current status and enforces valid transitions.
    Usage:
        machine = WorkItemStateMachine(work_item.status)
        new_status = machine.transition(WorkItemStatus.INVESTIGATING, rca_complete=False)
    """

    def __init__(self, current_status: WorkItemStatus):
        self._state = _STATE_MAP[current_status]

    def transition(self, target: WorkItemStatus, rca_complete: bool = False) -> WorkItemStatus:
        return self._state.transition_to(target, rca_complete)

    @property
    def current(self) -> WorkItemStatus:
        return self._state.status

    @staticmethod
    def calculate_mttr(first_signal_at: datetime, resolved_at: datetime) -> float:
        """MTTR in seconds from first signal to resolution."""
        return (resolved_at - first_signal_at).total_seconds()
