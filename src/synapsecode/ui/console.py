"""Rich console output manager."""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class SynapseConsole:
    """Centralized Rich console for SynapseCode output."""

    def __init__(self, verbose: bool = False) -> None:
        self.console = Console()
        self.verbose = verbose

    def banner(self) -> None:
        self.console.print(
            Panel(
                "[bold cyan]SynapseCode[/] — AI Agent Orchestrator",
                border_style="cyan",
            )
        )

    def phase(self, name: str, agent: str) -> None:
        self.console.print()
        self.console.rule(f"[bold yellow]{name}[/] [dim]({agent})[/]")

    def info(self, msg: str) -> None:
        self.console.print(f"[cyan]>[/] {msg}")

    def success(self, msg: str) -> None:
        self.console.print(f"[green]OK[/] {msg}")

    def warn(self, msg: str) -> None:
        self.console.print(f"[yellow]WARN[/] {msg}")

    def error(self, msg: str) -> None:
        self.console.print(f"[bold red]ERROR[/] {msg}")

    def debug(self, msg: str) -> None:
        if self.verbose:
            self.console.print(f"[dim]{msg}[/]")

    def show_diff(self, diff_text: str) -> None:
        if not diff_text.strip():
            self.info("No changes detected.")
            return
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
        self.console.print(Panel(syntax, title="Changes", border_style="green"))

    def show_cost(self, total: float, warn_threshold: float) -> None:
        color = "red" if total >= warn_threshold else "green"
        self.console.print(f"[{color}]Cost so far: ${total:.4f}[/]")

    def spinner(self, message: str) -> "Console.status":
        return self.console.status(f"[bold cyan]{message}[/]", spinner="dots")

    def confirm(self, prompt: str) -> bool:
        resp = self.console.input(f"[bold yellow]{prompt} [y/N]: [/]")
        return resp.strip().lower() in ("y", "yes")
