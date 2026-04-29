"""Workbench domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_success, print_table
from sanctum_client.client import delete, get, post


@click.group()
def workbench() -> None:
    """Manage the operator workbench."""
    pass


@workbench.command()
@click.pass_context
def list(ctx: click.Context) -> None:
    """List pinned projects on the workbench."""
    check_command_identity("workbench", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("workbench", "list", ctx.obj.get("resolved_agent"))
    result = get("/workbench")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    projects = result if isinstance(result, builtins.list) else result.get("projects", [])
    if not projects:
        click.echo("No pinned projects.")
        return

    rows = []
    for p in projects:
        rows.append(
            [
                p.get("name", "")[:50],
                str(p.get("open_tickets", 0)),
                p.get("status", ""),
            ]
        )
    print_table(["Project", "Open Tickets", "Status"], rows, title="Workbench")


@workbench.command()
@click.argument("project_id")
@click.pass_context
def pin(ctx: click.Context, project_id: str) -> None:
    """Pin a project to the workbench."""
    check_command_identity("workbench", "pin", ctx.obj.get("resolved_agent"))

    check_command_identity("workbench", "pin", ctx.obj.get("resolved_agent"))
    post("/workbench/pin", json={"project_id": project_id})
    if not ctx.obj.get("output_json"):
        print_success("Project pinned")


@workbench.command()
@click.argument("project_id")
@click.pass_context
def unpin(ctx: click.Context, project_id: str) -> None:
    """Remove a project from the workbench."""
    check_command_identity("workbench", "unpin", ctx.obj.get("resolved_agent"))

    check_command_identity("workbench", "unpin", ctx.obj.get("resolved_agent"))
    delete(f"/workbench/pin/{project_id}")
    if not ctx.obj.get("output_json"):
        print_success("Project unpinned")
