"""Output formatting — tables, colors, JSON output."""

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def print_table(headers: list[str], rows: list[list[str]], title: str | None = None) -> None:
    table = Table(title=title)
    for h in headers:
        table.add_column(h, no_wrap=True)
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
    console.print(table)


def print_json(data: Any) -> None:
    console.print_json(json.dumps(data))


def print_error(message: str) -> None:
    console.print(f"[red]✗[/red] {message}")


def print_success(message: str) -> None:
    console.print(f"[green]✓[/green] {message}")


def print_warning(message: str) -> None:
    console.print(f"[yellow]→[/yellow] {message}")


def print_key_value(pairs: dict[str, Any], title: str | None = None) -> None:
    if title:
        console.print(f"\n[bold]{title}[/bold]")
    for key, value in pairs.items():
        if value is not None and value != "":
            console.print(f"  [dim]{key}:[/dim] {value}")
