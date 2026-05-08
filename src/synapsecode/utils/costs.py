"""Cost tracking and budget enforcement."""

from dataclasses import dataclass, field
from typing import List, Optional

from synapsecode.config import CostConfig


@dataclass
class CostEntry:
    agent: str
    role: str
    cost_usd: float
    model: str = ""


class BudgetExceeded(Exception):
    """Raised when the hard cost limit is exceeded."""


class CostTracker:
    """Tracks cumulative costs and enforces budget limits."""

    def __init__(self, config: Optional[CostConfig] = None) -> None:
        self.config = config or CostConfig()
        self._entries: List[CostEntry] = []

    def record(self, entry: CostEntry) -> None:
        self._entries.append(entry)

    @property
    def total_usd(self) -> float:
        return sum(e.cost_usd for e in self._entries)

    @property
    def entries(self) -> List[CostEntry]:
        return list(self._entries)

    def check_budget(self) -> Optional[str]:
        """Return a warning string if warn threshold hit, raise if hard limit hit."""
        total = self.total_usd
        if total >= self.config.hard_limit_usd:
            raise BudgetExceeded(
                f"Cost ${total:.4f} exceeds hard limit ${self.config.hard_limit_usd:.2f}"
            )
        if total >= self.config.warn_threshold_usd:
            return (
                f"Warning: cost ${total:.4f} exceeds warning threshold "
                f"${self.config.warn_threshold_usd:.2f}"
            )
        return None

    def summary(self) -> str:
        lines = [f"Total cost: ${self.total_usd:.4f}"]
        for e in self._entries:
            lines.append(f"  {e.role} ({e.agent}): ${e.cost_usd:.4f}")
        return "\n".join(lines)
