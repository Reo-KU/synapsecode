# SynapseCode

Synapsecode was finished. It was changed for multi-agent orchestra. Please use multi-agent orchestra repositry.

**Multi-agent orchestration layer for Claude Code + Codex CLI**

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

SynapseCode orchestrates multiple AI coding agents (Claude Code and Codex CLI) through a structured pipeline to design, implement, review, and commit code changes. Each agent is assigned a role — designer, implementer, reviewer, or fixer — with automatic fallback and cost control.

```
User Request
    │
    ▼
┌──────────┐
│  DESIGN  │  Claude drafts an implementation plan
└────┬─────┘
     ▼
┌──────────┐
│IMPLEMENT │  Codex writes code from the plan
└────┬─────┘
     ▼
┌──────────┐
│  REVIEW  │  Claude reviews changes vs. the plan
└────┬─────┘
     │ FAIL ──► FIX (Codex) ──► REVIEW again (up to N iterations)
     │ PASS
     ▼
┌──────────┐
│  COMMIT  │  Git commit with confirmation
└──────────┘
```

## Features

- **Subprocess-based agent execution** — calls `claude` and `codex` CLIs directly; no API keys needed in SynapseCode itself
- **Automatic fallback** — if Codex is unavailable, Claude handles all roles
- **Cost tracking & budget limits** — per-session cost ledger with configurable warn/hard thresholds
- **Structured code review** — reviewer outputs JSON with verdict, summary, and categorized issues
- **SQLite session state** — full history of sessions, tasks, agent calls, and costs (`~/.config/synapsecode/state.db`)
- **Dry-run mode** — simulate the entire pipeline without calling agents
- **`--claude-only` mode** — force Claude for every role

## Installation

```bash
git clone https://github.com/Reo-KU/synapsecode.git
cd synapsecode
pip install -e .
```

### Prerequisites

- Python 3.9+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude` command available)
- [Codex CLI](https://github.com/openai/codex) (optional — falls back to Claude if missing)

## Quick Start

```bash
# Run the full pipeline
synapsecode run "Add a login endpoint with JWT authentication"

# Use Claude for all roles
synapsecode run "Fix the broken test suite" --claude-only

# Dry run (no agent calls)
synapsecode run "Refactor the database module" --dry-run

# Check which agents are available
synapsecode agents

# View session history
synapsecode history

# Inspect a specific session
synapsecode status 1
```

## CLI Reference

### Commands

| Command   | Description                                          |
|-----------|------------------------------------------------------|
| `run`     | Execute the design → implement → review → fix → commit pipeline |
| `agents`  | Show agent backend availability                      |
| `history` | Display session history with status and costs        |
| `status`  | Show detailed status of a session by ID              |
| `init`    | Initialize a git repo and default `synapsecode.toml` |

### `run` Options

| Flag                | Short | Default | Description                          |
|---------------------|-------|---------|--------------------------------------|
| `--claude-only`     |       | `false` | Use Claude for all roles             |
| `--dry-run`         |       | `false` | Simulate without calling agents      |
| `--verbose`         | `-v`  | `false` | Show debug output                    |
| `--max-iterations`  | `-n`  | 3       | Max review/fix iterations            |
| `--model`           | `-m`  |         | Override Claude model                |
| `--dir`             | `-d`  | `.`     | Working directory                    |
| `--config`          | `-c`  |         | Path to config TOML                  |
| `--log`             |       |         | Write detailed logs to file          |

## Configuration

SynapseCode searches for config in this order:

1. `--config` path (explicit)
2. `./synapsecode.toml` (project-local)
3. `~/.config/synapsecode/config.toml` (user-global)
4. Built-in defaults

### `synapsecode.toml`

```toml
[orchestrator]
max_iterations = 3        # Max review/fix loop iterations
auto_commit = false       # Auto-commit without confirmation
verbose = false
log_file = ""             # Optional log file path

[agents.claude]
command = "claude"
model = "sonnet"
timeout = 300
enabled = true

[agents.codex]
command = "codex"
model = "o4-mini"
timeout = 300
enabled = true

[costs]
warn_threshold_usd = 1.0  # Display a warning above this
hard_limit_usd = 5.0      # Stop the pipeline above this

[git]
auto_branch = true
branch_prefix = "synapse/"
commit_prefix = "[synapsecode]"
```

## Project Structure

```
src/synapsecode/
├── __init__.py          # Package version (0.1.0)
├── __main__.py          # python -m synapsecode entry
├── cli.py               # Typer CLI commands
├── config.py            # Config loading & dataclasses
├── orchestrator.py      # Core pipeline state machine
├── agents/
│   ├── base.py          # Abstract AgentBackend + Role enum
│   ├── registry.py      # Role-to-backend mapping & fallback
│   ├── claude.py        # Claude CLI backend
│   └── codex.py         # Codex CLI backend (JSONL parsing)
├── git/
│   └── manager.py       # GitPython wrapper
├── state/
│   └── database.py      # SQLite session/task/cost storage
├── ui/
│   ├── console.py       # Rich terminal output
│   └── panels.py        # Display panels & tables
└── utils/
    ├── costs.py          # CostTracker + BudgetExceeded
    ├── retry.py          # Async retry with exponential backoff
    └── templates.py      # System prompts for each role
```

## Tech Stack

| Component      | Library / Tool       |
|----------------|----------------------|
| CLI framework  | Typer                |
| Terminal UI    | Rich                 |
| Config parsing | toml                 |
| Git operations | GitPython            |
| State storage  | SQLite (WAL mode)    |
| Async runtime  | asyncio              |
| Testing        | pytest, pytest-asyncio |

## Testing

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT

---

## 日本語ガイド

### 概要

SynapseCode は、Claude Code と Codex CLI を組み合わせたマルチエージェントオーケストレーションツールです。ユーザーのリクエストに対して、設計・実装・レビュー・修正・コミットのパイプラインを自動で実行します。

### インストール

```bash
git clone https://github.com/Reo-KU/synapsecode.git
cd synapsecode
pip install -e .
```

**必要環境:** Python 3.9+、Claude Code CLI（`claude` コマンド）、Codex CLI（任意 — なければ Claude にフォールバック）

### 使い方

```bash
# パイプラインを実行
synapsecode run "JWTを使ったログインエンドポイントを追加"

# Claude のみで実行
synapsecode run "テストを修正" --claude-only

# ドライラン（エージェント呼び出しなし）
synapsecode run "データベースモジュールをリファクタリング" --dry-run

# エージェントの状態を確認
synapsecode agents

# セッション履歴を表示
synapsecode history
```

### 設定ファイル

`synapsecode.toml` をプロジェクトルートまたは `~/.config/synapsecode/config.toml` に配置します。

```toml
[orchestrator]
max_iterations = 3        # レビュー/修正の最大反復回数
auto_commit = false       # 確認なしで自動コミット

[agents.claude]
model = "sonnet"
timeout = 300

[agents.codex]
model = "o4-mini"
timeout = 300

[costs]
warn_threshold_usd = 1.0  # 警告を表示するコスト閾値
hard_limit_usd = 5.0      # パイプラインを停止するコスト上限
```

### ワークフロー

```
ユーザーリクエスト → 設計 (Claude) → 実装 (Codex) → レビュー (Claude) → 修正 (Codex) → コミット
                                                        ↑                        │
                                                        └── FAIL の場合ループ ──┘
```

レビューで PASS になるか、最大反復回数に達するとコミットフェーズに進みます。Codex が利用できない場合、すべてのロールを Claude が担当します。
