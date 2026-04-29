"""Notification domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_table
from sanctum_client.client import get


@click.group()
def notify() -> None:
    """Manage notifications."""
    pass


@notify.command()
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, status: str | None, limit: int) -> None:
    """List notifications."""
    check_command_identity("notify", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("notify", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if status:
        params["status"] = status
    result = get("/notifications", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    notes = result if isinstance(result, builtins.list) else result.get("notifications", [])
    if not notes:
        click.echo("No notifications found.")
        return

    rows = []
    for n in notes:
        rows.append(
            [
                n.get("type", "")[:30],
                n.get("status", ""),
                n.get("recipient", "")[:30],
                n.get("created_at", ""),
            ]
        )
    print_table(["Type", "Status", "Recipient", "Created"], rows, title="Notifications")
