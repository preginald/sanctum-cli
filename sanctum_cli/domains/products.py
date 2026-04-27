"""Product domain commands."""

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_table
from sanctum_client.client import get


@click.group()
def products() -> None:
    """Manage products and services."""
    pass


@products.command()
@click.option("--type", "-t", "product_type", default=None, help="Filter by product type")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, product_type: str | None, limit: int) -> None:
    """List products/services."""
    check_command_identity("products", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if product_type:
        params["product_type"] = product_type
    result = get("/products", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    products_list = result if isinstance(result, list) else result.get("products", [])
    if not products_list:
        click.echo("No products found.")
        return

    rows = []
    for p in products_list:
        rows.append([
            p.get("name", "")[:50],
            p.get("type", ""),
            f"${p.get('price', '0')}",
            p.get("billing_frequency", ""),
        ])
    print_table(["Name", "Type", "Price", "Billing"], rows, title="Products")
