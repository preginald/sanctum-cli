"""Milestone domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_cli.domains.projects import _resolve_project_id
from sanctum_client.client import get, put


@click.group()
def milestones() -> None:
    """Manage milestones."""
    pass


@milestones.command()
@click.option("--project-id", "-p", required=True, help="Project name or UUID")
@click.pass_context
def list(ctx: click.Context, project_id: str) -> None:
    """List milestones for a project."""
    check_command_identity("milestones", "list", ctx.obj.get("resolved_agent"))
    project_id = _resolve_project_id(project_id)
    result = get("/milestones", params={"project_id": project_id})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    milestones_list = result if isinstance(result, builtins.list) else result.get("milestones", [])
    if not milestones_list:
        click.echo("No milestones found.")
        return

    rows = []
    for m in milestones_list:
        rows.append([
            m.get("name", "")[:50],
            m.get("status", ""),
            str(m.get("ticket_count", 0)),
            str(m.get("sequence", "")),
        ])
    print_table(["Name", "Status", "Tickets", "Seq"], rows, title="Milestones")


@milestones.command()
@click.argument("milestone_id")
@click.pass_context
def show(ctx: click.Context, milestone_id: str) -> None:
    """Show milestone details."""
    check_command_identity("milestones", "show", ctx.obj.get("resolved_agent"))

    check_command_identity("milestones", "show", ctx.obj.get("resolved_agent"))
    result = get(f"/milestones/{milestone_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value({
        "Name": result.get("name"),
        "Status": result.get("status"),
        "Due Date": result.get("due_date"),
        "Sequence": result.get("sequence"),
        "Ticket Count": result.get("ticket_count"),
    }, title=f"Milestone: {result.get('name', '')}")


@milestones.command()
@click.argument("milestone_id")
@click.option("--name", default=None, help="New milestone name")
@click.option("--status", "-s", default=None, help="New status")
@click.option("--sequence", type=int, default=None, help="New sequence number")
@click.option("--description", "-d", default=None, help="New description")
@click.pass_context
def update(
    ctx: click.Context,
    milestone_id: str,
    name: str | None,
    status: str | None,
    sequence: int | None,
    description: str | None,
) -> None:
    """Update a milestone's fields."""
    check_command_identity("milestones", "update", ctx.obj.get("resolved_agent"))

    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if status is not None:
        payload["status"] = status
    if sequence is not None:
        payload["sequence"] = sequence
    if description is not None:
        payload["description"] = description

    if not payload:
        print_error("Nothing to update. Provide at least one field.")
        return

    result = put(f"/milestones/{milestone_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Milestone {milestone_id} updated")
    else:
        print_error(str(result))


@milestones.command()
@click.argument("milestone_id")
@click.option("--status", "-s", default="completed", help="Target status (e.g. active, completed)")
@click.pass_context
def complete(ctx: click.Context, milestone_id: str, status: str) -> None:
    """Mark a milestone as completed (or transition to another status)."""
    check_command_identity("milestones", "complete", ctx.obj.get("resolved_agent"))

    result = put(f"/milestones/{milestone_id}", json={"status": status})
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Milestone {milestone_id} → {status}")
    else:
        print_error(str(result))
