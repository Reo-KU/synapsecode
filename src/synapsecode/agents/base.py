"""Abstract base for agent backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Role(str, Enum):
    DESIGNER = "designer"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    FIXER = "fixer"


@dataclass
class AgentRequest:
    prompt: str
    role: Role
    system_prompt: str = ""
    working_dir: str = "."
    timeout: int = 300


@dataclass
class AgentResponse:
    text: str
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    model: str = ""
    raw: Dict = field(default_factory=dict)
    files_changed: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class AgentBackend(ABC):
    """Abstract base class for an AI agent backend."""

    name: str = "base"

    @abstractmethod
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Run a prompt through the agent and return the response."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this agent backend is installed and reachable."""
