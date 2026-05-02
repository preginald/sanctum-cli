"""Ticket domain commands."""

import builtins
import re

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import (
    print_error,
    print_json,
    print_key_value,
    print_success,
    print_table,
    print_warning,
)
from sanctum_cli.group import HelpfulGroup
from sanctum_client.client import get, post, put

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


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


def _search_accounts(query: str) -> list[dict]:
    result = get("/search", params={"q": query, "type": "client", "limit": "5"})
    results = result if isinstance(result, builtins.list) else result.get("results", [])
    return [r for r in results if r.get("type") in {"client", "account", None}]


def _account_id_from_search_result(result: dict) -> str | None:
    for key in ("account_id", "uuid", "id"):
        value = result.get(key)
        if isinstance(value, str) and UUID_RE.match(value):
            return value
    return None


def _account_name_from_search_result(result: dict) -> str:
    return str(result.get("name") or result.get("title") or "Unknown client")


def _resolve_missing_account_id(ctx: click.Context) -> str:
    if ctx.obj.get("output_json"):
        print_json({"error": "Missing required option: --account-id"})
        ctx.exit(1)

    print_warning("Ticket creation needs an account UUID.")
    answer = click.prompt(
        "Enter the account UUID or client name, or 'no' if you do not know it",
        default="",
        show_default=False,
    ).strip()

    if UUID_RE.match(answer):
        return answer

    if answer.lower() in {"", "n", "no", "unknown", "don't know", "dont know"}:
        answer = click.prompt(
            "Do you know the client's name? Enter it here",
            default="",
            show_default=False,
        )
        answer = answer.strip()

    if not answer:
        raise click.ClickException("Cannot create a ticket without an account UUID or client name.")

    matches = _search_accounts(answer)
    rows = []
    usable_matches = []
    for index, match in enumerate(matches, start=1):
        account_id = _account_id_from_search_result(match)
        if not account_id:
            continue
        usable_matches.append(match)
        rows.append([str(index), _account_name_from_search_result(match), account_id])

    if not usable_matches:
        raise click.ClickException(f"No client account found for '{answer}'.")

    print_table(["#", "Client", "Account UUID"], rows, title=f"Client matches for: {answer}")

    selected = usable_matches[0]
    if len(usable_matches) > 1:
        choice = click.prompt(
            "Select the matching client number",
            type=click.IntRange(1, len(usable_matches)),
        )
        selected = usable_matches[choice - 1]

    selected_name = _account_name_from_search_result(selected)
    selected_account_id = _account_id_from_search_result(selected)
    if not selected_account_id:
        raise click.ClickException(
            f"Selected client '{selected_name}' does not include an account UUID."
        )

    if not click.confirm(
        f"Use {selected_name} ({selected_account_id}) for this ticket?", default=True
    ):
        raise click.ClickException("Ticket creation cancelled; account was not confirmed.")

    return selected_account_id


@tickets.command()
@click.option("--subject", "-s", required=True, help="Ticket subject")
@click.option("--account-id", "-a", default=None, help="Account UUID")
@click.option(
    "--project-id",
    "-p",
    default=None,
    help="Project UUID (optional for multi-product tickets)",
)
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
@click.option(
    "--product-ids",
    "-P",
    default=None,
    help="Product IDs (comma-separated) for multi-product tickets",
)
@click.pass_context
def create(
    ctx: click.Context,
    subject: str,
    account_id: str | None,
    project_id: str | None,
    milestone_id: str | None,
    description: str,
    priority: str,
    ticket_type: str,
    articles: tuple,
    product_ids: str | None,
) -> None:
    """Create a new ticket."""
    check_command_identity("tickets", "create", ctx.obj.get("resolved_agent"))
    if not account_id:
        account_id = _resolve_missing_account_id(ctx)

    payload = {
        "subject": subject,
        "account_id": account_id,
        "priority": priority,
        "ticket_type": ticket_type,
    }
    if project_id:
        payload["project_id"] = project_id
    if milestone_id:
        payload["milestone_id"] = milestone_id
    if description:
        payload["description"] = description
    if articles:
        payload["article_ids"] = list(articles)
    if product_ids:
        payload["product_ids"] = [p.strip() for p in product_ids.split(",")]

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

    ticket_comments = result.get("comments")
    if ticket_comments:
        click.echo(f"\n[bold]Comments ({len(ticket_comments)}):[/bold]")
        for c in ticket_comments:
            click.echo(
                f"  [{c.get('id', '?')}] "
                f"{c.get('author_name', c.get('created_by', '?'))} "
                f"({c.get('created_at', '?')})"
            )
            body = (c.get("body") or "").strip()
            if body:
                for line in body.split("\n"):
                    click.echo(f"    {line}")
            click.echo("")


@tickets.command()
@click.option("--project", "-p", default=None, help="Filter by project name")
@click.option("--milestone", "-m", default=None, help="Filter by milestone name")
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--product-id", "-P", default=None, help="Filter by product ID")
@click.option("--orphan", "-O", is_flag=True, help="Show only orphan tickets (no project)")
@click.option("--limit", "-l", default=20, type=int, help="Max results")
@click.pass_context
def list(
    ctx: click.Context,
    project: str | None,
    milestone: str | None,
    status: str | None,
    product_id: str | None,
    orphan: bool,
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
    if product_id:
        params["product_id"] = product_id
    if orphan:
        params["orphan"] = "true"

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
@click.option(
    "--status",
    "-s",
    type=click.Choice(
        ["recon", "proposal", "pending", "new", "triaging", "open", "resolved", "closed"]
    ),
    default=None,
    help="New status (triaging requires WIKI-034)",
)
@click.option("--subject", default=None, help="New subject")
@click.option("--priority", type=click.Choice(["low", "normal", "high", "critical"]), default=None)
@click.option("--assigned-tech-id", default=None, help="Assigned tech UUID")
@click.option("--resolution-comment-id", default=None, help="Resolution comment UUID")
@click.option(
    "--product-ids",
    "-P",
    default=None,
    help="Product IDs (comma-separated) for multi-product tickets",
)
@click.option(
    "--phase-criteria",
    "-p",
    multiple=True,
    help="Phase criteria to tick (can be used multiple times), format: key=true",
)
@click.pass_context
def update(
    ctx: click.Context,
    ticket_id: int,
    status: str | None,
    subject: str | None,
    priority: str | None,
    assigned_tech_id: str | None,
    resolution_comment_id: str | None,
    product_ids: str | None,
    phase_criteria: tuple,
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
    if product_ids:
        payload["product_ids"] = [p.strip() for p in product_ids.split(",")]
    if phase_criteria:
        parsed_criteria = {}
        for criterion in phase_criteria:
            key, separator, value = criterion.partition("=")
            key = key.strip()
            if not key:
                raise click.BadParameter("phase criteria keys cannot be empty")
            if separator:
                normalized = value.strip().lower()
                if normalized not in {"true", "false"}:
                    raise click.BadParameter("phase criteria values must be true or false")
                parsed_criteria[key] = normalized == "true"
            else:
                parsed_criteria[key] = True
        payload["phase_criteria"] = parsed_criteria

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
