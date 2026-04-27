"""Mockup domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_table
from sanctum_client.client import get


@click.group()
def mockups() -> None:
    """Manage mockup artefacts."""
    pass


@mockups.command()
@click.option("--ticket-id", "-t", type=int, default=None, help="Filter by ticket")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, ticket_id: int | None, limit: int) -> None:
    """List mockups."""
    check_command_identity("mockups", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if ticket_id:
        params["ticket_id"] = str(ticket_id)
    result = get("/artefacts", params={**params, "category": "mockup"})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    mockups_list = result if isinstance(result, builtins.list) else result.get("artefacts", [])
    if not mockups_list:
        click.echo("No mockups found.")
        return

    rows = []
    for m in mockups_list:
        rows.append([
            m.get("name", "")[:50],
            m.get("status", ""),
            str(m.get("links_count", 0)),
            m.get("created_at", ""),
        ])
    print_table(["Name", "Status", "Links", "Created"], rows, title="Mockups")
