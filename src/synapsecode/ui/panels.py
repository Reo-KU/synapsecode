"""Display panels for phases and review results."""

import json
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def show_review_result(console: Console, review: Dict[str, Any]) -> None:
    """Display a structured review result panel."""
    verdict = review.get("verdict", "UNKNOWN")
    summary = review.get("summary", "")
    issues: List[Dict[str, str]] = review.get("issues", [])

    color = "green" if verdict == "PASS" else "red"
    title = f"Review: [{color}]{verdict}[/]"

    lines: List[str] = []
    if summary:
        lines.append(f"[bold]{summary}[/]")

    if issues:
        lines.append("")
        for issue in issues:
            sev = issue.get("severity", "?")
            sev_color = {
                "critical": "bold red",
                "major": "yellow",
                "minor": "dim",
            }.get(sev, "white")
            f = issue.get("file", "")
            desc = issue.get("description", "")
            lines.append(f"  [{sev_color}][{sev}][/] {f}: {desc}")

    body = "\n".join(lines) if lines else "No issues found."
    console.print(Panel(body, title=title, border_style=color))


def show_agent_table(console: Console, availability: Dict[str, bool]) -> None:
    """Show a table of agent availability."""
    table = Table(title="Agent Backends")
    table.add_column("Agent", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Command")

    for name, available in availability.items():
        if available:
            status = "[green]Available[/]"
        elif available is None:
            status = "[dim]Unknown[/]"
        else:
            status = "[red]Not found[/]"
        table.add_row(name, status, name)

    console.print(table)


def show_session_history(console: Console, sessions: List[Dict[str, Any]]) -> None:
    """Display session history table."""
    if not sessions:
        console.print("[dim]No sessions found.[/]")
        return

    table = Table(title="Session History")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Request")
    table.add_column("Status", justify="center")

    for s in sessions:
        status = s.get("status", "?")
        color = "green" if status == "completed" else "yellow" if status == "running" else "red"
        table.add_row(
            str(s["id"]),
            (s.get("request", "")[:60] + "...") if len(s.get("request", "")) > 60 else s.get("request", ""),
            f"[{color}]{status}[/]",
        )

    console.print(table)
