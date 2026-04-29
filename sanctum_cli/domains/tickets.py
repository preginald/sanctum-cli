"""Ticket domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_cli.group import HelpfulGroup
from sanctum_client.client import get, post, put


@click.group(
    cls=HelpfulGroup,
    suggestions={
        "comments": (
            "tickets show --comments <id>    View comments inline\n"
            'tickets comment <id> -b "..."  Add a comment'
        ),
        "links": (
            "tickets show --articles <id>     View linked articles inline\n"
            "tickets link-article <id> <aid>  Link an article"
        ),
    },
)
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
    type=click.Choice(
        [
            "bug",
            "feature",
            "task",
            "refactor",
            "hotfix",
            "alert",
            "support",
            "access",
            "maintenance",
            "test",
        ]
    ),
    default="task",
)
@click.option("--articles", "-A", multiple=True, help="Article IDs to link")
@click.pass_context
def create(
    ctx: click.Context,
    subject: str,
    project_id: str,
    milestone_id: str | None,
    description: str,
    priority: str,
    ticket_type: str,
    articles: tuple,
) -> None:
    """Create a new ticket."""
    check_command_identity("tickets", "create", ctx.obj.get("resolved_agent"))
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
    check_command_identity("tickets", "show", ctx.obj.get("resolved_agent"))
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

    print_key_value(
        {
            "ID": result.get("id"),
            "Subject": result.get("subject"),
            "Status": result.get("status"),
            "Priority": result.get("priority"),
            "Type": result.get("ticket_type"),
            "Project": result.get("project_name"),
            "Milestone": result.get("milestone_name"),
            "Account": result.get("account_name"),
            "Created": result.get("created_at"),
        },
        title=f"Ticket #{ticket_id}",
    )

    if result.get("description"):
        click.echo(f"\n[bold]Description:[/bold]\n{result['description']}")


@tickets.command()
@click.option("--project", "-p", default=None, help="Filter by project name")
@click.option("--milestone", "-m", default=None, help="Filter by milestone name")
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--limit", "-l", default=20, type=int, help="Max results")
@click.pass_context
def list(
    ctx: click.Context,
    project: str | None,
    milestone: str | None,
    status: str | None,
    limit: int,
) -> None:
    """List tickets."""
    check_command_identity("tickets", "list", ctx.obj.get("resolved_agent"))
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

    tickets_list = result if isinstance(result, builtins.list) else result.get("tickets", [])
    if not tickets_list:
        click.echo("No tickets found.")
        return

    rows = []
    for t in tickets_list:
        rows.append(
            [
                f"#{t.get('id', '')}",
                t.get("subject", "")[:60],
                t.get("status", ""),
                t.get("priority", ""),
                t.get("ticket_type", ""),
            ]
        )
    print_table(["ID", "Subject", "Status", "Priority", "Type"], rows, title="Tickets")


@tickets.command()
@click.argument("ticket_id", type=int)
@click.option("--body", "-b", required=True, help="Comment text (markdown)")
@click.pass_context
def comment(ctx: click.Context, ticket_id: int, body: str) -> None:
    """Add a comment to a ticket."""
    check_command_identity("tickets", "comment", ctx.obj.get("resolved_agent"))
    result = post("/comments", json={"ticket_id": ticket_id, "body": body})
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
@click.option("--resolution-comment-id", default=None, help="Resolution comment UUID")
@click.pass_context
def update(
    ctx: click.Context,
    ticket_id: int,
    status: str | None,
    subject: str | None,
    priority: str | None,
    assigned_tech_id: str | None,
    resolution_comment_id: str | None,
) -> None:
    """Update a ticket."""
    check_command_identity("tickets", "update", ctx.obj.get("resolved_agent"))
    payload: dict = {}
    if status:
        payload["status"] = status
    if subject:
        payload["subject"] = subject
    if priority:
        payload["priority"] = priority
    if assigned_tech_id:
        payload["assigned_tech_id"] = assigned_tech_id
    if resolution_comment_id:
        payload["resolution_comment_id"] = resolution_comment_id

    result = put(f"/tickets/{ticket_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        response_status = result.get("status")
        if status and response_status and response_status != status:
            print_error(
                f"Ticket #{ticket_id} status is '{response_status}', "
                f"not '{status}'. Update may have been rejected."
            )
        else:
            print_success(f"Ticket #{ticket_id} updated")
    else:
        print_error(str(result))


@tickets.command()
@click.argument("ticket_id", type=int)
@click.argument("article_id")
@click.pass_context
def link_article(ctx: click.Context, ticket_id: int, article_id: str) -> None:
    """Link an article to a ticket."""
    check_command_identity("tickets", "update", ctx.obj.get("resolved_agent"))
    result = post(f"/tickets/{ticket_id}/articles/{article_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict):
        print_success(f"Linked article {article_id} to ticket #{ticket_id}")
    else:
        print_error(str(result))


@tickets.command()
@click.argument("ticket_id", type=int)
@click.option("--body", "-b", required=True, help="Resolution body (markdown)")
@click.pass_context
def resolve(ctx: click.Context, ticket_id: int, body: str) -> None:
    """Resolve a ticket (two-step: post resolution comment, then update status)."""
    check_command_identity("tickets", "resolve", ctx.obj.get("resolved_agent"))

    ticket = get(f"/tickets/{ticket_id}")
    if isinstance(ticket, dict) and ticket.get("error"):
        print_error(f"Failed to fetch ticket: {ticket}")
        return
    available = ticket.get("available_transitions", [])
    if "resolved" not in available:
        print_error(
            f"Cannot resolve ticket #{ticket_id} from "
            f"'{ticket.get('status')}'. "
            f"Valid transitions: {available}"
        )
        return

    result = post("/comments", json={"ticket_id": ticket_id, "body": body, "is_resolution": True})
    comment_id = result.get("id") if isinstance(result, dict) else None

    if not comment_id:
        if ctx.obj.get("output_json"):
            print_json(result)
        else:
            print_error(str(result))
        return

    update_result = put(
        f"/tickets/{ticket_id}",
        json={"status": "resolved", "resolution_comment_id": comment_id},
    )

    if isinstance(update_result, dict) and update_result.get("error"):
        if ctx.obj.get("output_json"):
            print_json({"comment": result, "status_update": update_result})
        else:
            print_error(f"Comment created but status update failed: {update_result}")
        return

    if ctx.obj.get("output_json"):
        print_json(result)
    else:
        print_success(f"Ticket #{ticket_id} resolved")
