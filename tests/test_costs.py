"""Tests for cost tracking and budget enforcement."""

import pytest

from synapsecode.utils.costs import BudgetExceeded, CostEntry, CostTracker
from synapsecode.config import CostConfig


@pytest.fixture
def tracker():
    config = CostConfig(warn_threshold_usd=1.0, hard_limit_usd=5.0)
    return CostTracker(config)


def test_initial_total_is_zero(tracker):
    assert tracker.total_usd == 0.0
    assert tracker.entries == []


def test_record_single_entry(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=0.25, model="sonnet"))
    assert tracker.total_usd == 0.25
    assert len(tracker.entries) == 1


def test_record_multiple_entries(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=0.10))
    tracker.record(CostEntry(agent="claude", role="reviewer", cost_usd=0.20))
    tracker.record(CostEntry(agent="codex", role="implementer", cost_usd=0.05))
    assert abs(tracker.total_usd - 0.35) < 1e-9
    assert len(tracker.entries) == 3


def test_check_budget_under_threshold(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=0.50))
    assert tracker.check_budget() is None


def test_check_budget_warn_threshold(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=1.50))
    warning = tracker.check_budget()
    assert warning is not None
    assert "Warning" in warning
    assert "1.5" in warning


def test_check_budget_hard_limit_raises(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=5.50))
    with pytest.raises(BudgetExceeded):
        tracker.check_budget()


def test_check_budget_exact_hard_limit(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=5.0))
    with pytest.raises(BudgetExceeded):
        tracker.check_budget()


def test_check_budget_exact_warn_threshold(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=1.0))
    warning = tracker.check_budget()
    assert warning is not None


def test_summary_format(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=0.12, model="sonnet"))
    tracker.record(CostEntry(agent="codex", role="implementer", cost_usd=0.08, model="o4-mini"))
    summary = tracker.summary()
    assert "Total cost: $0.2000" in summary
    assert "designer (claude)" in summary
    assert "implementer (codex)" in summary


def test_entries_returns_copy(tracker):
    tracker.record(CostEntry(agent="claude", role="designer", cost_usd=0.10))
    entries = tracker.entries
    entries.clear()
    assert len(tracker.entries) == 1  # original unaffected
