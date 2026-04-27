"""Milestone domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_key_value, print_table
from sanctum_client.client import get


@click.group()
def milestones() -> None:
    """Manage milestones."""
    pass


@milestones.command()
@click.option("--project-id", "-p", required=True, help="Project UUID")
@click.pass_context
def list(ctx: click.Context, project_id: str) -> None:
    """List milestones for a project."""
    check_command_identity("milestones", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("milestones", "list", ctx.obj.get("resolved_agent"))
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
