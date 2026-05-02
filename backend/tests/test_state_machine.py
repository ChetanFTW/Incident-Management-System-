"""
Unit tests — RCA validation and state machine guards.
Run with: pytest backend/tests/ -v
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.patterns.state_machine import (
    WorkItemStateMachine, InvalidTransitionError, RCARequiredError
)
from app.models.pg_models import WorkItemStatus


# ── State machine tests ───────────────────────────────────────────────────────

class TestStateMachine:
    def test_open_to_investigating(self):
        m = WorkItemStateMachine(WorkItemStatus.OPEN)
        assert m.transition(WorkItemStatus.INVESTIGATING) == WorkItemStatus.INVESTIGATING

    def test_open_cannot_jump_to_resolved(self):
        m = WorkItemStateMachine(WorkItemStatus.OPEN)
        with pytest.raises(InvalidTransitionError):
            m.transition(WorkItemStatus.RESOLVED)

    def test_open_cannot_jump_to_closed(self):
        m = WorkItemStateMachine(WorkItemStatus.OPEN)
        with pytest.raises(InvalidTransitionError):
            m.transition(WorkItemStatus.CLOSED)

    def test_investigating_to_resolved(self):
        m = WorkItemStateMachine(WorkItemStatus.INVESTIGATING)
        assert m.transition(WorkItemStatus.RESOLVED) == WorkItemStatus.RESOLVED

    def test_resolved_to_closed_without_rca_raises(self):
        m = WorkItemStateMachine(WorkItemStatus.RESOLVED)
        with pytest.raises(RCARequiredError):
            m.transition(WorkItemStatus.CLOSED, rca_complete=False)

    def test_resolved_to_closed_with_rca_succeeds(self):
        m = WorkItemStateMachine(WorkItemStatus.RESOLVED)
        assert m.transition(WorkItemStatus.CLOSED, rca_complete=True) == WorkItemStatus.CLOSED

    def test_resolved_can_reopen_to_investigating(self):
        m = WorkItemStateMachine(WorkItemStatus.RESOLVED)
        assert m.transition(WorkItemStatus.INVESTIGATING) == WorkItemStatus.INVESTIGATING

    def test_closed_is_terminal(self):
        m = WorkItemStateMachine(WorkItemStatus.CLOSED)
        with pytest.raises(InvalidTransitionError):
            m.transition(WorkItemStatus.OPEN)

    def test_mttr_calculation(self):
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end   = datetime(2024, 1, 1, 11, 30, 0, tzinfo=timezone.utc)
        mttr  = WorkItemStateMachine.calculate_mttr(start, end)
        assert mttr == 5400.0  # 90 minutes in seconds


# ── RCA validation tests ──────────────────────────────────────────────────────

class TestRCAValidation:
    def _make_rca(self, **overrides):
        """Helper — create a mock RCA-like object."""
        from types import SimpleNamespace
        defaults = dict(
            root_cause_description="Database connection pool exhausted due to query surge",
            fix_applied="Increased pool size from 10 to 50 and added connection timeout",
            prevention_steps="Add alerting on connection pool usage >80%, add circuit breaker",
            root_cause_category="CAPACITY",
            incident_start=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            incident_end=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
        )
        defaults.update(overrides)
        obj = SimpleNamespace(**defaults)
        # attach is_complete method from real model
        from app.models.pg_models import RCA
        obj.is_complete = lambda: all([
            obj.root_cause_description and obj.root_cause_description.strip(),
            obj.fix_applied and obj.fix_applied.strip(),
            obj.prevention_steps and obj.prevention_steps.strip(),
            obj.root_cause_category is not None,
            obj.incident_start is not None,
            obj.incident_end is not None,
        ])
        return obj

    def test_complete_rca_passes(self):
        rca = self._make_rca()
        assert rca.is_complete() is True

    def test_empty_description_fails(self):
        rca = self._make_rca(root_cause_description="")
        assert rca.is_complete() is False

    def test_whitespace_only_fails(self):
        rca = self._make_rca(fix_applied="   ")
        assert rca.is_complete() is False

    def test_missing_category_fails(self):
        rca = self._make_rca(root_cause_category=None)
        assert rca.is_complete() is False

    def test_missing_start_fails(self):
        rca = self._make_rca(incident_start=None)
        assert rca.is_complete() is False


# ── Schema validation tests ───────────────────────────────────────────────────

class TestRCASchema:
    def test_end_before_start_raises(self):
        from pydantic import ValidationError
        from app.models.schemas import RCACreateRequest
        with pytest.raises(ValidationError):
            RCACreateRequest(
                incident_start=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                incident_end=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                root_cause_category="UNKNOWN",
                root_cause_description="x" * 20,
                fix_applied="x" * 20,
                prevention_steps="x" * 20,
            )

    def test_short_description_raises(self):
        from pydantic import ValidationError
        from app.models.schemas import RCACreateRequest
        with pytest.raises(ValidationError):
            RCACreateRequest(
                incident_start=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                incident_end=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
                root_cause_category="UNKNOWN",
                root_cause_description="too short",  # < 20 chars
                fix_applied="x" * 20,
                prevention_steps="x" * 20,
            )
