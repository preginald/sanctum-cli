"""Mockup domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_success, print_table
from sanctum_client.client import delete as api_delete
from sanctum_client.client import get, post, put


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


@mockups.command()
@click.option("--name", "-n", required=True, help="Mockup name")
@click.option("--ticket-id", "-t", type=int, default=None, help="Link to ticket")
@click.option("--file", "-f", type=click.Path(exists=True, dir_okay=False), help="Mockup file path")
@click.pass_context
def create(ctx: click.Context, name: str, ticket_id: int | None, file: str | None) -> None:
    """Create a new mockup artefact."""
    check_command_identity("mockups", "create", ctx.obj.get("resolved_agent"))

    payload: dict = {"name": name, "category": "mockup"}
    if ticket_id:
        payload["ticket_id"] = ticket_id
    if file:
        payload["file_path"] = file

    result = post("/artefacts", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Mockup created: {result['id']}")
    else:
        print_error(str(result))


@mockups.command()
@click.argument("mockup_id")
@click.option("--name", "-n", default=None, help="New mockup name")
@click.option("--file", "-f", type=click.Path(exists=True, dir_okay=False), help="Mockup file path")
@click.pass_context
def update(ctx: click.Context, mockup_id: str, name: str | None, file: str | None) -> None:
    """Update a mockup artefact."""
    check_command_identity("mockups", "update", ctx.obj.get("resolved_agent"))

    payload: dict = {}
    if name:
        payload["name"] = name
    if file:
        payload["file_path"] = file
    if not payload:
        print_error("Nothing to update. Provide --name, --file, or both.")
        return

    result = put(f"/artefacts/{mockup_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Mockup {mockup_id} updated")
    else:
        print_error(str(result))


@mockups.command()
@click.argument("mockup_id")
@click.confirmation_option(prompt="Delete this mockup?")
@click.pass_context
def delete(ctx: click.Context, mockup_id: str) -> None:
    """Delete a mockup artefact."""
    check_command_identity("mockups", "delete", ctx.obj.get("resolved_agent"))

    result = api_delete(f"/artefacts/{mockup_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and result.get("status") == "deleted":
        print_success(f"Mockup {mockup_id} deleted")
    else:
        print_error(str(result))
