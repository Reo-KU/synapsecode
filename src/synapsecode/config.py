"""Configuration loading from TOML files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import toml


@dataclass
class AgentConfig:
    command: str = ""
    model: str = ""
    timeout: int = 300
    enabled: bool = True


@dataclass
class OrchestratorConfig:
    max_iterations: int = 3
    auto_commit: bool = False
    verbose: bool = False
    dry_run: bool = False
    log_file: Optional[str] = None


@dataclass
class CostConfig:
    warn_threshold_usd: float = 1.0
    hard_limit_usd: float = 5.0


@dataclass
class GitConfig:
    auto_branch: bool = True
    branch_prefix: str = "synapse/"
    commit_prefix: str = "[synapsecode]"


@dataclass
class SynapseConfig:
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    claude: AgentConfig = field(
        default_factory=lambda: AgentConfig(command="claude", model="sonnet")
    )
    codex: AgentConfig = field(
        default_factory=lambda: AgentConfig(command="codex", model="o4-mini")
    )
    costs: CostConfig = field(default_factory=CostConfig)
    git: GitConfig = field(default_factory=GitConfig)


def _merge_agent(cfg: AgentConfig, raw: dict) -> None:
    for key in ("command", "model", "timeout", "enabled"):
        if key in raw:
            setattr(cfg, key, raw[key])


def load_config(path: Optional[str] = None) -> SynapseConfig:
    """Load configuration from a TOML file.

    Search order (first found wins):
    1. Explicit *path* argument
    2. ./synapsecode.toml  (project-local)
    3. ~/.config/synapsecode/config.toml  (user-global)
    4. Built-in defaults
    """
    cfg = SynapseConfig()

    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(Path.cwd() / "synapsecode.toml")
    candidates.append(Path.home() / ".config" / "synapsecode" / "config.toml")

    resolved: Optional[Path] = None
    for c in candidates:
        if c.is_file():
            resolved = c
            break

    if resolved is None:
        return cfg

    raw = toml.load(str(resolved))

    # Orchestrator
    if "orchestrator" in raw:
        orch = raw["orchestrator"]
        for key in ("max_iterations", "auto_commit", "verbose", "dry_run", "log_file"):
            if key in orch:
                setattr(cfg.orchestrator, key, orch[key])

    # Agents
    agents = raw.get("agents", {})
    if "claude" in agents:
        _merge_agent(cfg.claude, agents["claude"])
    if "codex" in agents:
        _merge_agent(cfg.codex, agents["codex"])

    # Costs
    if "costs" in raw:
        for key in ("warn_threshold_usd", "hard_limit_usd"):
            if key in raw["costs"]:
                setattr(cfg.costs, key, raw["costs"][key])

    # Git
    if "git" in raw:
        for key in ("auto_branch", "branch_prefix", "commit_prefix"):
            if key in raw["git"]:
                setattr(cfg.git, key, raw["git"][key])

    return cfg
