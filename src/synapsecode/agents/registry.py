"""Agent registry — resolves roles to backends with fallback."""

import asyncio
from typing import Dict, Optional

from synapsecode.agents.base import AgentBackend, Role
from synapsecode.agents.claude import ClaudeBackend
from synapsecode.agents.codex import CodexBackend
from synapsecode.config import SynapseConfig


# Default role-to-backend mapping
_DEFAULT_ROLES: Dict[Role, str] = {
    Role.DESIGNER: "claude",
    Role.IMPLEMENTER: "codex",
    Role.REVIEWER: "claude",
    Role.FIXER: "codex",
}


class AgentRegistry:
    """Resolves roles to agent backends, handling availability fallback."""

    def __init__(self, config: SynapseConfig, claude_only: bool = False) -> None:
        self.config = config
        self.claude_only = claude_only

        self._backends: Dict[str, AgentBackend] = {
            "claude": ClaudeBackend(config.claude),
            "codex": CodexBackend(config.codex),
        }
        self._availability: Dict[str, Optional[bool]] = {
            "claude": None,
            "codex": None,
        }

    async def check_availability(self) -> Dict[str, bool]:
        """Probe all backends and cache results."""
        results = {}
        for name, backend in self._backends.items():
            available = await backend.is_available()
            self._availability[name] = available
            results[name] = available
        return results

    def get_backend(self, role: Role) -> AgentBackend:
        """Return the best available backend for a role.

        If claude_only is set, always return claude.
        Otherwise, try the default backend; fall back to claude if unavailable.
        """
        if self.claude_only:
            return self._backends["claude"]

        preferred_name = _DEFAULT_ROLES.get(role, "claude")
        preferred = self._backends[preferred_name]

        # If we haven't probed yet, or the preferred is available, use it
        if self._availability.get(preferred_name) is not False:
            return preferred

        # Fallback to claude
        return self._backends["claude"]

    def get_backend_name(self, role: Role) -> str:
        """Return the name of the backend that would handle a given role."""
        backend = self.get_backend(role)
        return backend.name

    def availability_summary(self) -> Dict[str, Optional[bool]]:
        return dict(self._availability)
