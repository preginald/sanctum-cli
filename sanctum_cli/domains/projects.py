"""Project domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_client.client import get, post


@click.group()
def projects() -> None:
    """Manage projects."""
    pass


@projects.command()
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, limit: int) -> None:
    """List projects."""
    check_command_identity("projects", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("projects", "list", ctx.obj.get("resolved_agent"))
    result = get("/projects", params={"limit": str(limit)})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    projects_list = result if isinstance(result, builtins.list) else result.get("projects", [])
    if not projects_list:
        click.echo("No projects found.")
        return

    rows = []
    for p in projects_list:
        rows.append([
            p.get("name", "")[:50],
            p.get("status", ""),
            p.get("account_name", ""),
        ])
    print_table(["Name", "Status", "Account"], rows, title="Projects")


@projects.command()
@click.argument("project_id")
@click.option("--expand", "-x", default=None, help="Comma-separated fields to expand")
@click.pass_context
def show(ctx: click.Context, project_id: str, expand: str | None) -> None:
    """Show project details."""
    check_command_identity("projects", "show", ctx.obj.get("resolved_agent"))

    check_command_identity("projects", "show", ctx.obj.get("resolved_agent"))
    params: dict = {}
    if expand:
        params["expand"] = expand
    result = get(f"/projects/{project_id}", params=params or None)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value({
        "Name": result.get("name"),
        "Status": result.get("status"),
        "Account": result.get("account_name"),
        "Budget": f"${result.get('budget', '0')}",
        "Start Date": result.get("start_date"),
        "Due Date": result.get("due_date"),
    }, title=f"Project: {result.get('name', '')}")


@projects.command()
@click.argument("project_id")
@click.pass_context
def overview(ctx: click.Context, project_id: str) -> None:
    """Get project overview with tickets grouped by milestone."""
    check_command_identity("projects", "overview", ctx.obj.get("resolved_agent"))

    check_command_identity("projects", "overview", ctx.obj.get("resolved_agent"))
    result = get(f"/projects/{project_id}", params={"expand": "overview"})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    milestones = result.get("milestones", [])
    for m in milestones:
        print_key_value({"Status": m.get("status", "")}, title=f"Milestone: {m.get('name', '')}")
        for t in m.get("tickets", []):
            click.echo(f"  #{t['id']} [{t['status']}] {t['subject'][:70]}")


@projects.command()
@click.argument("name")
@click.option("--account-id", "-a", required=True, help="Account UUID")
@click.option("--description", "-d", default="", help="Project description")
@click.option(
    "--status", default="capture",
    type=click.Choice(["capture", "planning", "active"]),
    help="Initial project status (default: capture)",
)
@click.option("--start-date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--due-date", default=None, help="Due date (YYYY-MM-DD)")
@click.pass_context
def create(
    ctx: click.Context, name: str, account_id: str, description: str,
    status: str, start_date: str | None, due_date: str | None,
) -> None:
    """Create a new project."""
    check_command_identity("projects", "create", ctx.obj.get("resolved_agent"))

    payload: dict = {"name": name, "account_id": account_id, "status": status}
    if description:
        payload["description"] = description
    if start_date:
        payload["start_date"] = start_date
    if due_date:
        payload["due_date"] = due_date

    result = post("/projects", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Project created: {result['id']}")
        click.echo(f"  Name:   {result['name']}")
        click.echo(f"  Status: {result['status']}")
    else:
        print_error(str(result))
