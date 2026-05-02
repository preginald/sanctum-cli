"""Artefact domain commands."""

import builtins

import click
import httpx

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_client.client import delete as api_delete
from sanctum_client.client import get, post, put


@click.group()
def artefacts() -> None:
    """Manage artefacts."""
    pass


@artefacts.command()
@click.argument("artefact_id")
@click.option("--content", is_flag=True, help="Include artefact content when available")
@click.pass_context
def show(ctx: click.Context, artefact_id: str, content: bool) -> None:
    """Show artefact details."""
    check_command_identity("artefacts", "show", ctx.obj.get("resolved_agent"))
    params = {"expand": "content"} if content else None
    result = get(f"/artefacts/{artefact_id}", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value(
        {
            "Name": result.get("name"),
            "Type": result.get("artefact_type"),
            "Status": result.get("status"),
            "Category": result.get("category"),
            "Account": result.get("account_name"),
            "Links": result.get("links_count"),
            "Created": result.get("created_at"),
        },
        title=f"Artefact: {result.get('name', '')}",
    )
    if content and result.get("content") is not None:
        click.echo("\n--- Content ---")
        click.echo(result["content"])


@artefacts.command()
@click.option("--category", "-c", default=None, help="Filter by category")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, category: str | None, limit: int) -> None:
    """List artefacts."""
    check_command_identity("artefacts", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if category:
        params["category"] = category
    result = get("/artefacts", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    artefacts_list = result if isinstance(result, builtins.list) else result.get("artefacts", [])
    if not artefacts_list:
        click.echo("No artefacts found.")
        return

    rows = []
    for a in artefacts_list:
        rows.append(
            [
                a.get("name", "")[:50],
                a.get("artefact_type", ""),
                a.get("status", ""),
                str(a.get("links_count", 0)),
            ]
        )
    print_table(["Name", "Type", "Status", "Links"], rows, title="Artefacts")


@artefacts.command()
@click.option("--name", "-n", required=True, help="Artefact name")
@click.option(
    "--type",
    "-t",
    "artefact_type",
    required=True,
    type=click.Choice(["file", "url", "code_path", "document", "credential_ref"]),
)
@click.option("--url", "-u", default=None, help="Artefact URL (for url type)")
@click.option("--description", "-d", default="", help="Description")
@click.option("--content", default=None, help="Artefact body content")
@click.option("--mime-type", "mime_type", default=None, help="Content MIME type (e.g. text/html)")
@click.pass_context
def create(
    ctx: click.Context,
    name: str,
    artefact_type: str,
    url: str | None,
    description: str,
    content: str | None,
    mime_type: str | None,
) -> None:
    """Create a new artefact."""
    check_command_identity("artefacts", "create", ctx.obj.get("resolved_agent"))
    payload: dict = {"name": name, "artefact_type": artefact_type}
    if url:
        payload["url"] = url
    if description:
        payload["description"] = description
    result = post("/artefacts", json=payload)
    error: dict | None = None
    if isinstance(result, dict) and "id" in result:
        artefact_id = result["id"]
        if content or mime_type:
            update: dict = {}
            if content:
                update["content"] = content
            if mime_type:
                update["mime_type"] = mime_type
            update_result = put(f"/artefacts/{artefact_id}", json=update)
            if isinstance(update_result, dict) and update_result.get("error"):
                error = update_result
        if ctx.obj.get("output_json"):
            if error:
                print_json({"create": result, "content_update": error})
            else:
                print_json(result)
            return
        if error:
            print_error(f"Artefact created but content update failed: {error}")
            return
        print_success(f"Artefact created: {artefact_id}")
    elif isinstance(result, dict) and result.get("error"):
        print_error(str(result))
    else:
        print_error(str(result))


ENTITY_TYPES = ["ticket", "account", "article", "project", "milestone"]


@artefacts.command()
@click.argument("artefact_id")
@click.option("--project-id", "-p", default=None, help="Core project UUID to link to")
@click.option("--entity-type", "-t", default=None, type=click.Choice(ENTITY_TYPES))
@click.option("--entity-id", "-e", default=None, help="Target entity ID")
@click.pass_context
def link(
    ctx: click.Context,
    artefact_id: str,
    project_id: str | None,
    entity_type: str | None,
    entity_id: str | None,
) -> None:
    """Link an artefact to a project, ticket, account, article, or milestone."""
    check_command_identity("artefacts", "link", ctx.obj.get("resolved_agent"))

    if project_id and (entity_type or entity_id):
        print_error("Provide either --project-id or --entity-type/--entity-id, not both.")
        return

    if project_id:
        resolved_type = "project"
        resolved_id = project_id
    elif entity_type and entity_id:
        resolved_type = entity_type
        resolved_id = entity_id
    else:
        print_error("Provide --project-id or both --entity-type and --entity-id.")
        return

    result = post(
        f"/artefacts/{artefact_id}/link",
        json={"entity_type": resolved_type, "entity_id": resolved_id},
    )
    if ctx.obj.get("output_json"):
        print_json(result)
        return
    if isinstance(result, dict) and result.get("error"):
        print_error(str(result))
    else:
        print_success(f"Artefact {artefact_id} linked to {resolved_type} {resolved_id}")


@artefacts.command()
@click.argument("artefact_id")
@click.option("--name", "-n", default=None, help="New artefact name")
@click.option("--description", "-d", default=None, help="New description")
@click.option("--content", default=None, help="Artefact body content")
@click.option("--mime-type", "mime_type", default=None, help="Content MIME type (e.g. text/html)")
@click.option("--sensitivity", default=None, help="Sensitivity level")
@click.option("--category", "-c", default=None, help="Category")
@click.option("--status", default=None, help="Status (if backend allows direct patch)")
@click.pass_context
def update(
    ctx: click.Context,
    artefact_id: str,
    name: str | None,
    description: str | None,
    content: str | None,
    mime_type: str | None,
    sensitivity: str | None,
    category: str | None,
    status: str | None,
) -> None:
    """Update an artefact's mutable fields."""
    check_command_identity("artefacts", "update", ctx.obj.get("resolved_agent"))

    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if content is not None:
        payload["content"] = content
    if mime_type is not None:
        payload["mime_type"] = mime_type
    if sensitivity is not None:
        payload["sensitivity"] = sensitivity
    if category is not None:
        payload["category"] = category
    if status is not None:
        payload["status"] = status

    if not payload:
        print_error(
            "Nothing to update. Provide --name, --description, --content, "
            "--mime-type, --sensitivity, --category, or --status."
        )
        return

    result = put(f"/artefacts/{artefact_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Artefact {artefact_id} updated")
    else:
        print_error(str(result))


@artefacts.command()
@click.argument("artefact_id")
@click.option("--to", required=True, help="Target status transition")
@click.pass_context
def transition(ctx: click.Context, artefact_id: str, to: str) -> None:
    """Transition an artefact to a new status."""
    check_command_identity("artefacts", "transition", ctx.obj.get("resolved_agent"))

    try:
        artefact = get(f"/artefacts/{artefact_id}")
    except httpx.HTTPStatusError as exc:
        print_error(f"Failed to fetch artefact: {exc}")
        return
    if isinstance(artefact, dict) and artefact.get("error"):
        print_error(f"Failed to fetch artefact: {artefact}")
        return

    available = artefact.get("available_transitions", [])
    if to not in available:
        print_error(
            f"Cannot transition artefact {artefact_id} to '{to}'. Valid transitions: {available}"
        )
        return

    result = put(f"/artefacts/{artefact_id}", json={"status": to})
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Artefact {artefact_id} transitioned to {to}")
    else:
        print_error(str(result))


@artefacts.command()
@click.argument("artefact_id")
@click.option("--project-id", "-p", default=None, help="Core project UUID to unlink from")
@click.option("--entity-type", "-t", default=None, type=click.Choice(ENTITY_TYPES))
@click.option("--entity-id", "-e", default=None, help="Target entity ID")
@click.pass_context
def unlink(
    ctx: click.Context,
    artefact_id: str,
    project_id: str | None,
    entity_type: str | None,
    entity_id: str | None,
) -> None:
    """Unlink an artefact from a project, ticket, account, article, or milestone."""
    check_command_identity("artefacts", "unlink", ctx.obj.get("resolved_agent"))

    if project_id and (entity_type or entity_id):
        print_error("Provide either --project-id or --entity-type/--entity-id, not both.")
        return

    if project_id:
        resolved_type = "project"
        resolved_id = project_id
    elif entity_type and entity_id:
        resolved_type = entity_type
        resolved_id = entity_id
    else:
        print_error("Provide --project-id or both --entity-type and --entity-id.")
        return

    result = api_delete(f"/artefacts/{artefact_id}/link/{resolved_type}/{resolved_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return
    if isinstance(result, dict) and result.get("error"):
        print_error(str(result))
    else:
        print_success(f"Artefact {artefact_id} unlinked from {resolved_type} {resolved_id}")
