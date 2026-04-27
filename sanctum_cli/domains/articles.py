"""Article domain commands."""

import click

from sanctum_client.client import get, post
from sanctum_cli.display import print_table, print_json, print_error, print_success, print_key_value


@click.group()
def articles() -> None:
    """Manage knowledge base articles."""
    pass


@articles.command()
@click.argument("slug_or_id")
@click.pass_context
def show(ctx: click.Context, slug_or_id: str) -> None:
    """Show an article by slug (DOC-009) or UUID."""
    result = get(f"/articles/{slug_or_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value({
        "Identifier": result.get("identifier"),
        "Title": result.get("title"),
        "Slug": result.get("slug"),
        "Category": result.get("category"),
        "Version": result.get("version"),
        "Author": result.get("author_name"),
        "Revision Count": result.get("revision_count"),
        "Created": result.get("created_at"),
        "Updated": result.get("updated_at"),
    }, title=f"Article: {result.get('identifier', slug_or_id)}")


@articles.command()
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, limit: int) -> None:
    """List all articles."""
    result = get("/articles", params={"limit": str(limit)})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    articles_list = result if isinstance(result, list) else result.get("articles", [])
    if not articles_list:
        click.echo("No articles found.")
        return

    rows = []
    for a in articles_list:
        rows.append([
            a.get("identifier", ""),
            a.get("title", "")[:60],
            a.get("category", ""),
            a.get("version", ""),
        ])
    print_table(["ID", "Title", "Category", "Version"], rows, title="Articles")


@articles.command()
@click.option("--title", "-t", required=True, help="Article title")
@click.option("--slug", "-s", required=True, help="URL-friendly slug")
@click.option("--identifier", "-i", required=True, help="Identifier (e.g. DOC-001)")
@click.option("--category", "-c", default="Knowledge Base", help="Article category")
@click.pass_context
def create(ctx: click.Context, title: str, slug: str, identifier: str, category: str) -> None:
    """Create a new article."""
    payload = {
        "title": title,
        "slug": slug,
        "identifier": identifier,
        "category": category,
    }
    result = post("/articles", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Article {identifier} created")
    else:
        print_error(str(result))
