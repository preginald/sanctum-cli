"""Search domain command."""

import click

from sanctum_cli.display import print_json, print_table
from sanctum_client.client import get


@click.command()
@click.argument("query")
@click.option("--type", "-t", "entity_type", default=None, help="Filter by entity type")
@click.option("--limit", "-l", default=10, type=int, help="Max results per type")
@click.pass_context
def search(ctx: click.Context, query: str, entity_type: str | None, limit: int) -> None:
    """Cross-entity search across tickets, articles, clients, and more."""
    params: dict = {"q": query, "limit": str(limit)}
    if entity_type:
        params["type"] = entity_type

    result = get("/search", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    results = result if isinstance(result, list) else result.get("results", [])
    if not results:
        click.echo("No results found.")
        return

    rows = []
    for r in results:
        rows.append([
            r.get("type", ""),
            r.get("title", "")[:50],
            r.get("subtitle", ""),
            f"{r.get('score', 0):.2f}",
        ])
    print_table(["Type", "Title", "Subtitle", "Score"], rows, title=f"Search: {query}")
