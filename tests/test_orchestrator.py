"""Tests for the orchestrator state machine with mocked agents."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapsecode.agents.base import AgentRequest, AgentResponse, Role
from synapsecode.agents.registry import AgentRegistry
from synapsecode.config import SynapseConfig
from synapsecode.git.manager import GitManager
from synapsecode.orchestrator import Orchestrator, Phase
from synapsecode.state.database import StateDB
from synapsecode.ui.console import SynapseConsole
from synapsecode.utils.costs import CostTracker


@pytest.fixture
def config():
    cfg = SynapseConfig()
    cfg.orchestrator.max_iterations = 2
    cfg.orchestrator.auto_commit = True
    return cfg


@pytest.fixture
def mock_registry(config):
    registry = AgentRegistry(config, claude_only=True)
    return registry


@pytest.fixture
def mock_git(tmp_path):
    git = MagicMock(spec=GitManager)
    git.working_dir = str(tmp_path)
    git.is_repo.return_value = True
    git.file_tree.return_value = "project/\n├── README.md"
    git.diff.return_value = "+hello world"
    git.diff_stat.return_value = "1 file changed"
    git.has_changes.return_value = True
    git.commit.return_value = "abc1234"
    git.stage_all.return_value = None
    return git


@pytest.fixture
def db(tmp_path):
    return StateDB(str(tmp_path / "test.db"))


@pytest.fixture
def ui():
    console = SynapseConsole(verbose=False)
    # Suppress actual output in tests
    console.console = MagicMock()
    console.confirm = MagicMock(return_value=True)
    return console


@pytest.fixture
def cost_tracker(config):
    return CostTracker(config.costs)


def _make_response(text: str, cost: float = 0.01) -> AgentResponse:
    return AgentResponse(text=text, cost_usd=cost, duration_seconds=1.0, model="test", success=True)


def _make_review_pass() -> AgentResponse:
    review = {"verdict": "PASS", "summary": "All good", "issues": []}
    return _make_response(json.dumps(review), cost=0.02)


def _make_review_fail() -> AgentResponse:
    review = {
        "verdict": "FAIL",
        "summary": "Found issues",
        "issues": [{"severity": "major", "file": "main.py", "description": "Missing error handling"}],
    }
    return _make_response(json.dumps(review), cost=0.02)


@pytest.mark.asyncio
async def test_full_pipeline_pass_on_first_review(config, mock_git, db, ui, cost_tracker):
    """Pipeline should complete when review passes on first try."""
    registry = AgentRegistry(config, claude_only=True)

    # Mock the claude backend execute method
    mock_execute = AsyncMock(side_effect=[
        _make_response("## Plan\n1. Create hello.py"),  # design
        _make_response("Created hello.py"),              # implement
        _make_review_pass(),                              # review -> PASS
    ])

    with patch.object(registry._backends["claude"], "execute", mock_execute), \
         patch.object(registry._backends["claude"], "is_available", new_callable=AsyncMock, return_value=True):
        orch = Orchestrator(config, registry, mock_git, db, ui, cost_tracker)
        await orch.run("Create hello world")

    # Should have 3 agent calls: design, implement, review
    assert mock_execute.call_count == 3
    # Session should be completed
    sessions = db.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["status"] == "completed"
    # Git commit should have been called (auto_commit=True)
    mock_git.commit.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_fix_loop(config, mock_git, db, ui, cost_tracker):
    """Pipeline should loop through fix when review fails, then pass."""
    registry = AgentRegistry(config, claude_only=True)

    mock_execute = AsyncMock(side_effect=[
        _make_response("## Plan\n1. Create app.py"),  # design
        _make_response("Created app.py"),              # implement (iter 1)
        _make_review_fail(),                            # review -> FAIL (iter 1)
        _make_response("Fixed error handling"),         # fix (iter 1)
        _make_response("Re-implemented"),               # implement (iter 2)
        _make_review_pass(),                            # review -> PASS (iter 2)
    ])

    with patch.object(registry._backends["claude"], "execute", mock_execute), \
         patch.object(registry._backends["claude"], "is_available", new_callable=AsyncMock, return_value=True):
        orch = Orchestrator(config, registry, mock_git, db, ui, cost_tracker)
        await orch.run("Create an app")

    # design + implement + review(FAIL) + fix + implement + review(PASS) = 6 calls
    assert mock_execute.call_count == 6
    sessions = db.list_sessions()
    assert sessions[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_pipeline_max_iterations_reached(config, mock_git, db, ui, cost_tracker):
    """Pipeline should stop after max_iterations even if review keeps failing."""
    config.orchestrator.max_iterations = 2
    registry = AgentRegistry(config, claude_only=True)

    mock_execute = AsyncMock(side_effect=[
        _make_response("## Plan"),                      # design
        _make_response("Implemented"),                  # implement iter 1
        _make_review_fail(),                            # review FAIL iter 1
        _make_response("Fixed"),                        # fix iter 1
        _make_response("Implemented again"),            # implement iter 2
        _make_review_fail(),                            # review FAIL iter 2 -> max reached
    ])

    with patch.object(registry._backends["claude"], "execute", mock_execute), \
         patch.object(registry._backends["claude"], "is_available", new_callable=AsyncMock, return_value=True):
        orch = Orchestrator(config, registry, mock_git, db, ui, cost_tracker)
        await orch.run("Create something")

    sessions = db.list_sessions()
    assert sessions[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_pipeline_design_failure(config, mock_git, db, ui, cost_tracker):
    """Pipeline should fail gracefully when design phase fails."""
    registry = AgentRegistry(config, claude_only=True)

    mock_execute = AsyncMock(return_value=AgentResponse(
        text="", success=False, error="Claude CLI not found"
    ))

    with patch.object(registry._backends["claude"], "execute", mock_execute), \
         patch.object(registry._backends["claude"], "is_available", new_callable=AsyncMock, return_value=True):
        orch = Orchestrator(config, registry, mock_git, db, ui, cost_tracker)
        await orch.run("Create something")

    sessions = db.list_sessions()
    assert sessions[0]["status"] == "failed"
    mock_git.commit.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_no_changes_skips_commit(config, mock_git, db, ui, cost_tracker):
    """When there are no git changes, commit should be skipped."""
    mock_git.has_changes.return_value = False
    mock_git.diff.return_value = ""
    registry = AgentRegistry(config, claude_only=True)

    mock_execute = AsyncMock(side_effect=[
        _make_response("## Plan"),
        _make_response("Done"),
        _make_review_pass(),
    ])

    with patch.object(registry._backends["claude"], "execute", mock_execute), \
         patch.object(registry._backends["claude"], "is_available", new_callable=AsyncMock, return_value=True):
        orch = Orchestrator(config, registry, mock_git, db, ui, cost_tracker)
        await orch.run("Do nothing")

    mock_git.commit.assert_not_called()


def test_parse_review_valid_json():
    """_parse_review should parse valid review JSON."""
    review_json = json.dumps({"verdict": "PASS", "summary": "OK", "issues": []})
    result = Orchestrator._parse_review(review_json)
    assert result["verdict"] == "PASS"


def test_parse_review_with_markdown_fences():
    """_parse_review should strip markdown fences."""
    text = '```json\n{"verdict": "FAIL", "summary": "bad", "issues": []}\n```'
    result = Orchestrator._parse_review(text)
    assert result["verdict"] == "FAIL"


def test_parse_review_invalid_json():
    """_parse_review should return PASS fallback for unparseable text."""
    result = Orchestrator._parse_review("This is not JSON at all")
    assert result["verdict"] == "PASS"
    assert "_raw" in result
