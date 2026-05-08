"""Typer CLI for SynapseCode."""

import asyncio
from typing import Optional

import typer
from rich.console import Console

from synapsecode import __version__
from synapsecode.agents.registry import AgentRegistry
from synapsecode.config import load_config
from synapsecode.git.manager import GitManager
from synapsecode.orchestrator import Orchestrator
from synapsecode.state.database import StateDB
from synapsecode.ui.console import SynapseConsole
from synapsecode.ui.panels import show_agent_table, show_session_history
from synapsecode.utils.costs import CostTracker

app = typer.Typer(
    name="synapsecode",
    help="AI agent orchestrator — Claude Code + Codex CLI integration.",
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"synapsecode {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass


@app.command()
def run(
    request: str = typer.Argument(..., help="What you want the agents to build or change."),
    claude_only: bool = typer.Option(False, "--claude-only", help="Use Claude for all roles."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug output."),
    max_iterations: Optional[int] = typer.Option(None, "--max-iterations", "-n", help="Max review/fix iterations."),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config TOML."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override Claude model."),
    working_dir: str = typer.Option(".", "--dir", "-d", help="Working directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate pipeline without calling agents."),
    log_file: Optional[str] = typer.Option(None, "--log", help="Write detailed logs to file."),
) -> None:
    """Run the full design->implement->review->fix->commit pipeline."""
    cfg = load_config(config_path)

    if max_iterations is not None:
        cfg.orchestrator.max_iterations = max_iterations
    if verbose:
        cfg.orchestrator.verbose = True
    if model:
        cfg.claude.model = model
    if dry_run:
        cfg.orchestrator.dry_run = True
    if log_file:
        cfg.orchestrator.log_file = log_file

    registry = AgentRegistry(cfg, claude_only=claude_only)
    git = GitManager(working_dir)
    db = StateDB()
    ui = SynapseConsole(verbose=cfg.orchestrator.verbose)
    costs = CostTracker(cfg.costs)

    orchestrator = Orchestrator(
        config=cfg,
        registry=registry,
        git=git,
        db=db,
        ui=ui,
        cost_tracker=costs,
    )

    asyncio.run(orchestrator.run(request))
    db.close()


@app.command()
def agents(
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config TOML."),
) -> None:
    """Show agent backend availability."""
    cfg = load_config(config_path)
    registry = AgentRegistry(cfg)
    console = Console()

    avail = asyncio.run(registry.check_availability())
    show_agent_table(console, avail)


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of sessions to show."),
) -> None:
    """Show session history."""
    db = StateDB()
    console = Console()
    sessions = db.list_sessions(limit=limit)
    show_session_history(console, sessions)
    db.close()


@app.command()
def status(
    session_id: int = typer.Argument(..., help="Session ID to inspect."),
) -> None:
    """Show status of a specific session."""
    db = StateDB()
    console = Console()
    session = db.get_session(session_id)
    if session is None:
        console.print(f"[red]Session #{session_id} not found.[/]")
    else:
        console.print(f"[cyan]Session #{session['id']}[/]")
        console.print(f"  Request: {session['request']}")
        console.print(f"  Status:  {session['status']}")
        total = db.session_total_cost(session_id)
        console.print(f"  Cost:    ${total:.4f}")
    db.close()


@app.command()
def init(
    working_dir: str = typer.Option(".", "--dir", "-d", help="Directory to initialize."),
) -> None:
    """Initialize a git repo and default config in the working directory."""
    import os
    import shutil
    from pathlib import Path

    console = Console()
    wd = Path(os.path.abspath(working_dir))

    # Git init if needed
    git_dir = wd / ".git"
    if not git_dir.exists():
        import subprocess
        subprocess.run(["git", "init"], cwd=str(wd), check=True)
        console.print("[green]Initialized git repository[/]")
    else:
        console.print("[dim]Git repository already exists[/]")

    # Copy default config
    config_dest = wd / "synapsecode.toml"
    if not config_dest.exists():
        default_config = Path(__file__).parent.parent.parent / "synapsecode.toml"
        if default_config.exists():
            shutil.copy2(str(default_config), str(config_dest))
            console.print("[green]Created synapsecode.toml[/]")
        else:
            # Write a minimal config
            config_dest.write_text(
                '[orchestrator]\nmax_iterations = 3\nauto_commit = false\nverbose = false\n\n'
                '[agents.claude]\ncommand = "claude"\nmodel = "sonnet"\ntimeout = 300\nenabled = true\n\n'
                '[agents.codex]\ncommand = "codex"\nmodel = "o4-mini"\ntimeout = 300\nenabled = true\n\n'
                '[costs]\nwarn_threshold_usd = 1.0\nhard_limit_usd = 5.0\n\n'
                '[git]\nauto_branch = true\nbranch_prefix = "synapse/"\ncommit_prefix = "[synapsecode]"\n'
            )
            console.print("[green]Created synapsecode.toml (defaults)[/]")
    else:
        console.print("[dim]synapsecode.toml already exists[/]")


def app_entry() -> None:
    """Entry point for the CLI (used by pyproject.toml scripts)."""
    app()
