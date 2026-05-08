"""Tests for agent registry and fallback logic."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from synapsecode.agents.base import AgentBackend, AgentRequest, AgentResponse, Role
from synapsecode.agents.registry import AgentRegistry
from synapsecode.config import SynapseConfig


@pytest.fixture
def config():
    return SynapseConfig()


def test_default_role_mapping(config):
    """Designer and reviewer should prefer claude, implementer and fixer should prefer codex."""
    registry = AgentRegistry(config)
    # Before availability check, all backends are returned by default
    assert registry.get_backend_name(Role.DESIGNER) == "claude"
    assert registry.get_backend_name(Role.REVIEWER) == "claude"
    assert registry.get_backend_name(Role.IMPLEMENTER) == "codex"
    assert registry.get_backend_name(Role.FIXER) == "codex"


def test_claude_only_mode(config):
    """With claude_only=True, all roles should use claude."""
    registry = AgentRegistry(config, claude_only=True)
    for role in Role:
        assert registry.get_backend_name(role) == "claude"


def test_fallback_when_codex_unavailable(config):
    """When codex is marked unavailable, implementer/fixer should fall back to claude."""
    registry = AgentRegistry(config)
    # Simulate codex being unavailable
    registry._availability["codex"] = False
    registry._availability["claude"] = True

    assert registry.get_backend_name(Role.DESIGNER) == "claude"
    assert registry.get_backend_name(Role.IMPLEMENTER) == "claude"  # fallback
    assert registry.get_backend_name(Role.REVIEWER) == "claude"
    assert registry.get_backend_name(Role.FIXER) == "claude"  # fallback


def test_codex_used_when_available(config):
    """When codex is available, implementer/fixer should use it."""
    registry = AgentRegistry(config)
    registry._availability["codex"] = True
    registry._availability["claude"] = True

    assert registry.get_backend_name(Role.IMPLEMENTER) == "codex"
    assert registry.get_backend_name(Role.FIXER) == "codex"


@pytest.mark.asyncio
async def test_check_availability(config):
    """check_availability should probe all backends."""
    registry = AgentRegistry(config)

    with patch.object(registry._backends["claude"], "is_available", new_callable=AsyncMock, return_value=True), \
         patch.object(registry._backends["codex"], "is_available", new_callable=AsyncMock, return_value=False):
        result = await registry.check_availability()

    assert result["claude"] is True
    assert result["codex"] is False
    assert registry.availability_summary()["claude"] is True
    assert registry.availability_summary()["codex"] is False


def test_availability_summary_initial(config):
    """Before probing, availability should be None for all backends."""
    registry = AgentRegistry(config)
    summary = registry.availability_summary()
    assert summary["claude"] is None
    assert summary["codex"] is None
