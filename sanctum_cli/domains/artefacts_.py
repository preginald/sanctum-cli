"""Artefact domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_key_value, print_success, print_table
from sanctum_client.client import get, post, put


@click.group()
def artefacts() -> None:
    """Manage artefacts."""
    pass


@artefacts.command()
@click.argument("artefact_id")
@click.pass_context
def show(ctx: click.Context, artefact_id: str) -> None:
    """Show artefact details."""
    check_command_identity("artefacts", "show", ctx.obj.get("resolved_agent"))
    result = get(f"/artefacts/{artefact_id}")
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
            from sanctum_cli.display import print_error

            print_error(f"Artefact created but content update failed: {error}")
            return
        print_success(f"Artefact created: {artefact_id}")
    elif isinstance(result, dict) and result.get("error"):
        from sanctum_cli.display import print_error

        print_error(str(result))
    else:
        from sanctum_cli.display import print_error

        print_error(str(result))
