"""Ticket domain commands."""

import click

from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_client.client import get, post, put


@click.group()
def tickets() -> None:
    """Manage tickets."""
    pass


@tickets.command()
@click.option("--subject", "-s", required=True, help="Ticket subject")
@click.option("--project-id", "-p", required=True, help="Project UUID")
@click.option("--milestone-id", "-m", default=None, help="Milestone UUID")
@click.option("--description", "-d", default="", help="Ticket description")
@click.option(
    "--priority", type=click.Choice(["low", "normal", "high", "critical"]), default="normal"
)
@click.option(
    "--ticket-type",
    type=click.Choice([
        "bug", "feature", "task", "refactor", "hotfix",
        "alert", "support", "access", "maintenance", "test",
    ]),
    default="task",
)
@click.option("--articles", "-A", multiple=True, help="Article IDs to link")
@click.pass_context
def create(ctx: click.Context, subject: str, project_id: str, milestone_id: str | None,
           description: str, priority: str, ticket_type: str, articles: tuple) -> None:
    """Create a new ticket."""
    payload = {
        "subject": subject,
        "project_id": project_id,
        "priority": priority,
        "ticket_type": ticket_type,
    }
    if milestone_id:
        payload["milestone_id"] = milestone_id
    if description:
        payload["description"] = description
    if articles:
        payload["article_ids"] = list(articles)

    result = post("/tickets", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Ticket #{result['id']} created: {result.get('subject', '')}")
    else:
        print_error(str(result))


@tickets.command()
@click.argument("ticket_id", type=int)
@click.option("--comments", "-c", is_flag=True, help="Include comments")
@click.option("--articles", "-a", is_flag=True, help="Include linked articles")
@click.pass_context
def show(ctx: click.Context, ticket_id: int, comments: bool, articles: bool) -> None:
    """Show ticket details."""
    params = {}
    expand = []
    if comments:
        expand.append("comments")
    if articles:
        expand.append("articles")
    if expand:
        params["expand"] = ",".join(expand)

    result = get(f"/tickets/{ticket_id}", params=params or None)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value({
        "ID": result.get("id"),
        "Subject": result.get("subject"),
        "Status": result.get("status"),
        "Priority": result.get("priority"),
        "Type": result.get("ticket_type"),
        "Project": result.get("project_name"),
        "Milestone": result.get("milestone_name"),
        "Account": result.get("account_name"),
        "Created": result.get("created_at"),
    }, title=f"Ticket #{ticket_id}")

    if result.get("description"):
        click.echo(f"\n[bold]Description:[/bold]\n{result['description']}")


@tickets.command()
@click.option("--project", "-p", default=None, help="Filter by project name")
@click.option("--milestone", "-m", default=None, help="Filter by milestone name")
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--limit", "-l", default=20, type=int, help="Max results")
@click.pass_context
def list(
    ctx: click.Context, project: str | None, milestone: str | None,
    status: str | None, limit: int,
) -> None:
    """List tickets."""
    params: dict = {"limit": str(limit)}
    if project:
        params["project"] = project
    if milestone:
        params["milestone"] = milestone
    if status:
        params["status"] = status

    result = get("/tickets", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    tickets_list = result if isinstance(result, list) else result.get("tickets", [])
    if not tickets_list:
        click.echo("No tickets found.")
        return

    rows = []
    for t in tickets_list:
        rows.append([
            f"#{t.get('id', '')}",
            t.get("subject", "")[:60],
            t.get("status", ""),
            t.get("priority", ""),
            t.get("ticket_type", ""),
        ])
    print_table(["ID", "Subject", "Status", "Priority", "Type"], rows, title="Tickets")


@tickets.command()
@click.argument("ticket_id", type=int)
@click.option("--body", "-b", required=True, help="Comment text (markdown)")
@click.pass_context
def comment(ctx: click.Context, ticket_id: int, body: str) -> None:
    """Add a comment to a ticket."""
    result = post(f"/tickets/{ticket_id}/comments", json={"body": body})
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Comment added to #{ticket_id}")
    else:
        print_error(str(result))


@tickets.command()
@click.argument("ticket_id", type=int)
@click.option("--status", "-s", default=None, help="New status")
@click.option("--subject", default=None, help="New subject")
@click.option("--priority", type=click.Choice(["low", "normal", "high", "critical"]), default=None)
@click.option("--assigned-tech-id", default=None, help="Assigned tech UUID")
@click.pass_context
def update(ctx: click.Context, ticket_id: int, status: str | None, subject: str | None,
           priority: str | None, assigned_tech_id: str | None) -> None:
    """Update a ticket."""
    payload: dict = {}
    if status:
        payload["status"] = status
    if subject:
        payload["subject"] = subject
    if priority:
        payload["priority"] = priority
    if assigned_tech_id:
        payload["assigned_tech_id"] = assigned_tech_id

    result = put(f"/tickets/{ticket_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Ticket #{ticket_id} updated")
    else:
        print_error(str(result))


@tickets.command()
@click.argument("ticket_id", type=int)
@click.option("--body", "-b", required=True, help="Resolution body (markdown)")
@click.pass_context
def resolve(ctx: click.Context, ticket_id: int, body: str) -> None:
    """Resolve a ticket (two-step: update status + post resolution)."""
    put(f"/tickets/{ticket_id}", json={"status": "resolved"})
    result = post(f"/tickets/{ticket_id}/comments", json={"body": body, "is_resolution": True})
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Ticket #{ticket_id} resolved")
    else:
        print_error(str(result))
