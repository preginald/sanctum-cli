"""Project domain commands."""

import click

from sanctum_client.client import get
from sanctum_cli.display import print_table, print_json, print_key_value


@click.group()
def projects() -> None:
    """Manage projects."""
    pass


@projects.command()
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, limit: int) -> None:
    """List projects."""
    result = get("/projects", params={"limit": str(limit)})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    projects_list = result if isinstance(result, list) else result.get("projects", [])
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
    result = get(f"/projects/{project_id}", params={"expand": "overview"})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    milestones = result.get("milestones", [])
    for m in milestones:
        print_key_value({"Status": m.get("status", "")}, title=f"Milestone: {m.get('name', '')}")
        for t in m.get("tickets", []):
            click.echo(f"  #{t['id']} [{t['status']}] {t['subject'][:70]}")
