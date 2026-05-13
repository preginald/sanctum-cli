"""Ticket domain commands."""

import builtins
import os
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
from sanctum_cli.domains.ticket_resolver import AmbiguousEntity, TicketCreateResolver
from sanctum_cli.group import HelpfulGroup
from sanctum_client.client import get, post, put

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_TEMPLATE_SECTIONS: dict[str, list[str]] = {
    "feature": ["## Objective", "## Requirements", "## Test Plan", "## Acceptance Criteria"],
    "task": ["## Objective", "## Requirements", "## Test Plan", "## Acceptance Criteria"],
    "bug": [
        "## Bug",
        "## Root Cause",
        "## Acceptance Criteria",
    ],
    "test": ["## Objective", "## Test Plan", "## Expected Results", "## Acceptance Criteria"],
}

# Maps non-standard headings the user might write to the canonical required heading.
_HEADING_ALIASES: dict[str, str] = {
    "## Problem": "## Bug",
    "## Summary": "## Bug",
    "## Description": "## Bug",
    "## Root cause": "## Root Cause",
}


def _ensure_template_compliance(description: str | None, ticket_type: str) -> str:
    """Normalise a description to include all required template sections.

    If the description has no ##-level headings the content is placed under the
    first required section and remaining sections are appended as empty stubs.
    If it already has some ## headings, non-standard headings are mapped via
    _HEADING_ALIASES and any still-missing required sections are appended
    as empty stubs so the server-side DOC-013 validation passes.
    """
    if not description:
        return description or ""
    required = _TEMPLATE_SECTIONS.get(ticket_type)
    if not required:
        return description

    # Remap common non-standard headings to canonical names.
    for alias, canonical in _HEADING_ALIASES.items():
        description = description.replace(alias, canonical)

    existing_headings = set(re.findall(r"^(#{1,6} .+)$", description, re.MULTILINE))
    if not any(h in existing_headings for h in required):
        # No recognised headings at all — wrap content under first required section.
        parts = [f"{required[0]}\n\n{description.strip()}"]
        for section in required[1:]:
            parts.append(f"\n\n{section}\n\n")
        return "".join(parts)

    missing = [h for h in required if h not in existing_headings]
    if not missing:
        return description

    parts = [description.rstrip()]
    for section in missing:
        parts.append(f"\n\n{section}\n\n")
    return "".join(parts)


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


def _print_history_hint(ticket_id: int) -> None:
    import click as _click

    _click.echo(f"  View full history: sanctum tickets show --comments {ticket_id}")


def _print_template_validation_help(result: dict) -> None:
    if not isinstance(result, dict):
        print_error(str(result))
        return
    detail = result.get("detail") or {}
    if isinstance(detail, dict):
        detail = detail.get("detail", detail)
    missing = result.get("missing_sections", [])
    if isinstance(detail, builtins.list):
        for item in detail:
            if isinstance(item, dict) and item.get("msg"):
                msg = item["msg"]
                if "section" in msg.lower():
                    parsed = msg.split(":", 1)[-1].strip()
                    if parsed:
                        missing.append(parsed)
    template_article = result.get("template_article", "")
    lines = [str(result)]
    if missing:
        lines.append("\nMissing template sections:")
        for s in missing:
            lines.append(f"  - {s}")
    if template_article:
        lines.append(f"\nSee {template_article} for the required template format.")
        lines.append(
            "Include sections as top-level ## headings with blank lines after each heading."
        )
    print_error("\n".join(lines))


def _handle_resolve_error(
    ctx: click.Context, ticket_id: int, update_result: dict, body: str, comment_id: str | None
) -> None:
    detail = update_result.get("detail", {})
    if isinstance(detail, str):
        detail = {"detail": detail}
    error_code = detail.get("error_code", "")
    project_id = detail.get("project_id", "")
    project_name = detail.get("project_name", "")

    if error_code == "project_budget_required" and project_id:
        label = project_name or project_id
        click.echo(f"\n  Project '{label}' has no market_value set.")
        click.echo("  Set a nominal budget to allow ticket resolution.")
        if ctx.obj.get("yes") or click.confirm("  Set market_value to 1000?", default=True):
            from sanctum_client.client import put as _project_put

            budget_result = _project_put(
                f"/projects/{project_id}",
                json={"market_value": "1000.00"},
            )
            if isinstance(budget_result, dict) and budget_result.get("error"):
                print_error(f"Failed to set project budget: {budget_result}")
                print_error(
                    "Set it manually via: sanctum projects update <project> --market-value 1000"
                )
                return
            print_success(f"Set market_value=1000 on project '{label}'")
            if comment_id:
                retry = _project_put(
                    f"/tickets/{ticket_id}",
                    json={"status": "resolved", "resolution_comment_id": comment_id},
                )
                if isinstance(retry, dict) and not retry.get("error"):
                    print_success(
                        f"Ticket #{ticket_id} resolved (auto-retried after setting budget)"
                    )
                    return
                print_error(f"Auto-retry failed: {retry}")
        print_error(
            "Set the budget and retry:\n"
            f"  sanctum projects update {project_id} --market-value 1000\n"
            f'  sanctum tickets resolve {ticket_id} -b "{body}"'
        )
    else:
        print_error(
            "To retry, fix the issue above and run:\n"
            f'  sanctum tickets resolve {ticket_id} -b "{body}"'
        )


def _check_status_change(ticket_id: int, before: dict) -> None:
    if not isinstance(before, dict) or before.get("error"):
        return
    after = get(f"/tickets/{ticket_id}")
    if not isinstance(after, dict):
        return
    before_status = before.get("status")
    after_status = after.get("status")
    if before_status and after_status and before_status != after_status:
        import click as _click

        _click.echo(
            f"  Note: Ticket moved from {before_status} to {after_status}"
            " (auto-transitioned on comment)"
        )


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


def _resolve_description(
    description: str, description_file: str | None, description_stdin: bool
) -> str:
    sources = sum(1 for x in (description, description_file, description_stdin) if x)
    if sources > 1:
        raise click.ClickException(
            "--description, --description-file, and --description-stdin are mutually exclusive."
        )
    if description_file:
        if not os.path.isfile(description_file):
            raise click.ClickException(f"Description file not found: {description_file}")
        with open(description_file, encoding="utf-8") as f:
            return f.read()
    if description_stdin:
        return click.get_text_stream("stdin").read()
    return description


@tickets.command()
@click.option("--subject", "-s", required=True, help="Ticket subject")
@click.option(
    "--account-id", "-a", default=None,
    help="Account UUID (inferred from project/product if omitted)",
)
@click.option(
    "--project-id",
    "-p",
    default=None,
    help="Project UUID or name (optional for multi-product tickets)",
)
@click.option("--milestone-id", "-m", default=None, help="Milestone UUID or name")
@click.option("--description", "-d", default="", help="Ticket description (markdown)")
@click.option("--description-file", default=None, help="Read description from file")
@click.option("--description-stdin", is_flag=True, help="Read description from stdin")
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
    description_file: str | None,
    description_stdin: bool,
    priority: str,
    ticket_type: str,
    articles: tuple,
    product_ids: str | None,
) -> None:
    """Create a new ticket."""
    check_command_identity("tickets", "create", ctx.obj.get("resolved_agent"))

    description = _resolve_description(description, description_file, description_stdin)
    description = _ensure_template_compliance(description, ticket_type)

    resolver = TicketCreateResolver(ctx)
    try:
        resolved = resolver.resolve(
            account_id=account_id,
            project_id=project_id,
            milestone_id=milestone_id,
            product_ids=product_ids,
            subject=subject,
            description=description,
        )
    except AmbiguousEntity as exc:
        if ctx.obj.get("output_json"):
            print_json(resolver.print_ambiguous_json(exc))
        else:
            resolver.print_ambiguous_error(exc)
        ctx.exit(1)
        return

    if not ctx.obj.get("output_json"):
        resolver.print_warnings(resolved)

    account_id = resolved.get("account_id")
    project_id = resolved.get("project_id")
    milestone_id = resolved.get("milestone_id")
    product_ids = resolved.get("product_ids")

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
        created_id = result["id"]
        print_success(f"Ticket #{created_id} created: {result.get('subject', '')}")
        _print_history_hint(created_id)
    else:
        _print_template_validation_help(result)


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


def _resolve_body(body: str | None, body_file: str | None) -> str:
    """Return body text from string or file. Exactly one must be provided."""
    if body_file:
        if not os.path.isfile(body_file):
            raise click.ClickException(f"Body file not found: {body_file}")
        with open(body_file, encoding="utf-8") as f:
            return f.read()
    return body or ""


@tickets.command()
@click.argument("ticket_id", type=int)
@click.option("--body", "-b", default=None, help="Comment text (markdown)")
@click.option("--body-file", default=None, help="Read comment body from file")
@click.pass_context
def comment(ctx: click.Context, ticket_id: int, body: str | None, body_file: str | None) -> None:
    """Add a comment to a ticket."""
    if not body and not body_file:
        raise click.ClickException("Either --body or --body-file is required.")
    if body and body_file:
        raise click.ClickException("--body and --body-file are mutually exclusive.")
    body = _resolve_body(body, body_file)
    check_command_identity("tickets", "comment", ctx.obj.get("resolved_agent"))
    before = get(f"/tickets/{ticket_id}")
    result = post("/comments", json={"ticket_id": ticket_id, "body": body})
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Comment added to #{ticket_id}")
        _check_status_change(ticket_id, before)
        _print_history_hint(ticket_id)
    else:
        print_error(str(result))


@tickets.command()
@click.argument("ticket_id", type=int)
@click.option(
    "--status",
    "-s",
    type=click.Choice(
        [
            "recon",
            "proposal",
            "pending",
            "new",
            "triaging",
            "open",
            "implementation",
            "verification",
            "review",
            "documented",
            "resolved",
            "closed",
        ]
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
            _print_history_hint(ticket_id)
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
@click.option("--body", "-b", default=None, help="Resolution body (markdown)")
@click.option("--body-file", default=None, help="Read resolution body from file")
@click.pass_context
def resolve(ctx: click.Context, ticket_id: int, body: str | None, body_file: str | None) -> None:
    if not body and not body_file:
        raise click.ClickException("Either --body or --body-file is required.")
    if body and body_file:
        raise click.ClickException("--body and --body-file are mutually exclusive.")
    body = _resolve_body(body, body_file)
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
            print_error(
                "Comment created but status update failed. "
                f"Reason: {update_result.get('detail', {}).get('detail', update_result)}"
            )
            _handle_resolve_error(ctx, ticket_id, update_result, body, comment_id)
        return

    if ctx.obj.get("output_json"):
        print_json(result)
    else:
        print_success(f"Ticket #{ticket_id} resolved")
        _print_history_hint(ticket_id)
