"""Tests for config loading."""

import os
from pathlib import Path

from synapsecode.config import SynapseConfig, load_config


def test_default_config():
    cfg = SynapseConfig()
    assert cfg.orchestrator.max_iterations == 3
    assert cfg.claude.command == "claude"
    assert cfg.codex.command == "codex"
    assert cfg.costs.hard_limit_usd == 5.0


def test_load_config_from_file(tmp_dir):
    toml_content = """\
[orchestrator]
max_iterations = 7
auto_commit = true

[agents.claude]
model = "opus"

[costs]
hard_limit_usd = 10.0
"""
    config_file = tmp_dir / "synapsecode.toml"
    config_file.write_text(toml_content)

    cfg = load_config(str(config_file))
    assert cfg.orchestrator.max_iterations == 7
    assert cfg.orchestrator.auto_commit is True
    assert cfg.claude.model == "opus"
    assert cfg.costs.hard_limit_usd == 10.0
    # Defaults preserved for unset fields
    assert cfg.codex.command == "codex"


def test_load_config_no_file(tmp_dir):
    cfg = load_config()
    # Should return defaults when no file found
    assert cfg.orchestrator.max_iterations == 3


def test_load_config_project_local(tmp_dir):
    toml_content = """\
[orchestrator]
verbose = true
"""
    (tmp_dir / "synapsecode.toml").write_text(toml_content)

    cfg = load_config()
    assert cfg.orchestrator.verbose is True
