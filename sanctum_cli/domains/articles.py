"""Article domain commands."""

import builtins
from pathlib import Path

import click
import httpx

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_client.client import get, post, put
from sanctum_client.client import patch as api_patch


def _handle_get(path: str, **kwargs: object) -> dict | list | None:
    """Call get() and return None on 404 for clean CLI errors."""
    try:
        return get(path, **kwargs)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


@click.group()
def articles() -> None:
    """Manage knowledge base articles."""
    pass


@articles.command()
@click.argument("slug_or_id")
@click.option("--content", is_flag=True, help="Include article content")
@click.pass_context
def show(ctx: click.Context, slug_or_id: str, content: bool) -> None:
    """Show an article by slug (DOC-009) or UUID."""
    check_command_identity("articles", "show", ctx.obj.get("resolved_agent"))

    params = {"expand": "content"} if content else None
    result = _handle_get(f"/articles/{slug_or_id}", params=params)
    if result is None:
        print_error(f"Article not found: {slug_or_id}")
        raise SystemExit(1)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value(
        {
            "Identifier": result.get("identifier"),
            "Title": result.get("title"),
            "Slug": result.get("slug"),
            "Category": result.get("category"),
            "Version": result.get("version"),
            "Author": result.get("author_name"),
            "Revision Count": result.get("revision_count"),
            "Created": result.get("created_at"),
            "Updated": result.get("updated_at"),
        },
        title=f"Article: {result.get('identifier', slug_or_id)}",
    )


@articles.command()
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, limit: int) -> None:
    """List all articles."""
    check_command_identity("articles", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("articles", "list", ctx.obj.get("resolved_agent"))
    result = get("/articles", params={"limit": str(limit)})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    articles_list = result if isinstance(result, builtins.list) else result.get("articles", [])
    if not articles_list:
        click.echo("No articles found.")
        return

    rows = []
    for a in articles_list:
        rows.append(
            [
                a.get("identifier", ""),
                a.get("title", "")[:60],
                a.get("category", ""),
                a.get("version", ""),
            ]
        )
    print_table(["ID", "Title", "Category", "Version"], rows, title="Articles")


@articles.command()
@click.option("--title", "-t", required=True, help="Article title")
@click.option("--slug", "-s", required=True, help="URL-friendly slug")
@click.option("--identifier", "-i", required=True, help="Identifier (e.g. DOC-001)")
@click.option("--category", "-c", default="Knowledge Base", help="Article category")
@click.option(
    "--file", "-f", type=click.Path(exists=True, dir_okay=False), help="Markdown content file"
)
@click.pass_context
def create(
    ctx: click.Context, title: str, slug: str, identifier: str, category: str, file: str | None
) -> None:
    """Create a new article."""
    check_command_identity("articles", "create", ctx.obj.get("resolved_agent"))

    check_command_identity("articles", "create", ctx.obj.get("resolved_agent"))
    payload = {
        "title": title,
        "slug": slug,
        "identifier": identifier,
        "category": category,
        "content": Path(file).read_text() if file else "",
    }
    result = post("/articles", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Article {identifier} created")
    else:
        print_error(str(result))


@articles.command()
@click.argument("slug_or_id")
@click.option("--title", "-t", default=None, help="New article title")
@click.option(
    "--file", "-f", type=click.Path(exists=True, dir_okay=False), help="Markdown content file"
)
@click.option("--section", default=None, help="Section heading to patch (requires --file)")
@click.pass_context
def update(
    ctx: click.Context, slug_or_id: str, title: str | None, file: str | None, section: str | None
) -> None:
    """Update an article by identifier (DOC-009) or UUID.

    Use --section to patch a single heading's content without replacing the
    entire article body. Section updates require --file.
    """
    check_command_identity("articles", "update", ctx.obj.get("resolved_agent"))

    if section:
        if not file:
            print_error("--section requires --file")
            return
        content = Path(file).read_text()
        payload = {"heading": section, "content": content}
        result = api_patch(f"/articles/{slug_or_id}/sections", json=payload)
        if ctx.obj.get("output_json"):
            print_json(result)
        elif isinstance(result, dict) and "id" in result:
            print_success(f"Section patched in {slug_or_id}: {section}")
        else:
            print_error(str(result))
        return

    payload: dict = {}
    if file:
        payload["content"] = Path(file).read_text()
    if title:
        payload["title"] = title
    if not payload:
        print_error("Nothing to update. Provide --title, --file, or both.")
        return

    result = put(f"/articles/{slug_or_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Article {slug_or_id} updated")
    else:
        print_error(str(result))
