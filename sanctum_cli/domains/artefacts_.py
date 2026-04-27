"""Artefact domain commands."""

import click

from sanctum_client.client import get, post
from sanctum_cli.display import print_table, print_json, print_success, print_key_value


@click.group()
def artefacts() -> None:
    """Manage artefacts."""
    pass


@artefacts.command()
@click.argument("artefact_id")
@click.pass_context
def show(ctx: click.Context, artefact_id: str) -> None:
    """Show artefact details."""
    result = get(f"/artefacts/{artefact_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value({
        "Name": result.get("name"),
        "Type": result.get("artefact_type"),
        "Status": result.get("status"),
        "Category": result.get("category"),
        "Account": result.get("account_name"),
        "Links": result.get("links_count"),
        "Created": result.get("created_at"),
    }, title=f"Artefact: {result.get('name', '')}")


@artefacts.command()
@click.option("--category", "-c", default=None, help="Filter by category")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, category: str | None, limit: int) -> None:
    """List artefacts."""
    params: dict = {"limit": str(limit)}
    if category:
        params["category"] = category
    result = get("/artefacts", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    artefacts_list = result if isinstance(result, list) else result.get("artefacts", [])
    if not artefacts_list:
        click.echo("No artefacts found.")
        return

    rows = []
    for a in artefacts_list:
        rows.append([
            a.get("name", "")[:50],
            a.get("artefact_type", ""),
            a.get("status", ""),
            str(a.get("links_count", 0)),
        ])
    print_table(["Name", "Type", "Status", "Links"], rows, title="Artefacts")


@artefacts.command()
@click.option("--name", "-n", required=True, help="Artefact name")
@click.option("--type", "-t", "artefact_type", required=True,
              type=click.Choice(["file", "url", "code_path", "document", "credential_ref"]))
@click.option("--url", "-u", default=None, help="Artefact URL (for url type)")
@click.option("--description", "-d", default="", help="Description")
@click.pass_context
def create(ctx: click.Context, name: str, artefact_type: str, url: str | None, description: str) -> None:
    """Create a new artefact."""
    payload: dict = {"name": name, "artefact_type": artefact_type}
    if url:
        payload["url"] = url
    if description:
        payload["description"] = description
    result = post("/artefacts", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Artefact created: {result.get('id', '')}")
    else:
        from sanctum_cli.display import print_error
        print_error(str(result))
