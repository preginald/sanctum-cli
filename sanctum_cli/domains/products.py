"""Product domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_client.client import get, post, put


@click.group()
def products() -> None:
    """Manage products and services."""
    pass


@products.command()
@click.option("--name", "-n", required=True, help="Product name")
@click.option("--description", "-d", default="", help="Product description")
@click.option(
    "--type",
    "-t",
    "product_type",
    required=True,
    help="Product type (hosting, service, hardware, platform, etc.)",
)
@click.option("--unit-price", default="0.00", help="Unit price (e.g. 99.00)")
@click.option("--billing-frequency", default=None, help="Billing frequency (yearly, monthly, etc.)")
@click.option("--is-recurring", is_flag=True, help="Set is_recurring to true")
@click.option("--is-active/--inactive", default=True, help="Set product active state")
@click.pass_context
def create(
    ctx: click.Context,
    name: str,
    description: str,
    product_type: str,
    unit_price: str,
    billing_frequency: str | None,
    is_recurring: bool,
    is_active: bool,
) -> None:
    """Create a product/service."""
    check_command_identity("products", "create", ctx.obj.get("resolved_agent"))

    payload: dict = {
        "name": name,
        "description": description,
        "type": product_type,
        "unit_price": unit_price,
        "is_recurring": is_recurring,
        "is_active": is_active,
    }
    if billing_frequency is not None:
        payload["billing_frequency"] = billing_frequency

    result = post("/products", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Product created: {result.get('id')}")
    else:
        print_error(str(result))


@products.command()
@click.option("--type", "-t", "product_type", default=None, help="Filter by product type")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, product_type: str | None, limit: int) -> None:
    """List products/services."""
    check_command_identity("products", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("products", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if product_type:
        params["product_type"] = product_type
    result = get("/products", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    products_list = result if isinstance(result, builtins.list) else result.get("products", [])
    if not products_list:
        click.echo("No products found.")
        return

    rows = []
    for p in products_list:
        rows.append(
            [
                p.get("name", "")[:50],
                p.get("type", ""),
                f"${p.get('price', '0')}",
                p.get("billing_frequency", ""),
            ]
        )
    print_table(["Name", "Type", "Price", "Billing"], rows, title="Products")


@products.command()
@click.argument("product_id")
@click.pass_context
def show(ctx: click.Context, product_id: str) -> None:
    """Show product details."""
    check_command_identity("products", "show", ctx.obj.get("resolved_agent"))

    result = get(f"/products/{product_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value(
        {
            "Name": result.get("name"),
            "Description": result.get("description"),
            "Type": result.get("type"),
            "Unit Price": result.get("unit_price"),
            "Billing Frequency": result.get("billing_frequency"),
            "Is Recurring": result.get("is_recurring"),
            "Is Active": result.get("is_active"),
            "Created": result.get("created_at"),
            "ID": result.get("id"),
        },
        title=f"Product: {result.get('name', '')}",
    )


@products.command()
@click.argument("product_id")
@click.option("--name", "-n", default=None, help="New product name")
@click.option("--description", "-d", default=None, help="New description")
@click.option(
    "--type",
    "-t",
    "product_type",
    default=None,
    help="Product type (hosting, service, hardware, platform, etc.)",
)
@click.option("--unit-price", default=None, help="Unit price (e.g. 99.00)")
@click.option("--billing-frequency", default=None, help="Billing frequency (yearly, monthly, etc.)")
@click.option("--is-active", is_flag=True, default=None, help="Set is_active to true")
@click.option("--is-recurring", is_flag=True, default=None, help="Set is_recurring to true")
@click.pass_context
def update(
    ctx: click.Context,
    product_id: str,
    name: str | None,
    description: str | None,
    product_type: str | None,
    unit_price: str | None,
    billing_frequency: str | None,
    is_active: bool | None,
    is_recurring: bool | None,
) -> None:
    """Update a product's mutable fields."""
    check_command_identity("products", "update", ctx.obj.get("resolved_agent"))

    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if product_type is not None:
        payload["type"] = product_type
    if unit_price is not None:
        payload["unit_price"] = unit_price
    if billing_frequency is not None:
        payload["billing_frequency"] = billing_frequency
    if is_active is not None:
        payload["is_active"] = is_active
    if is_recurring is not None:
        payload["is_recurring"] = is_recurring

    if not payload:
        print_error(
            "Nothing to update. Provide --name, --description, --type, "
            "--unit-price, --billing-frequency, --is-active, or --is-recurring."
        )
        return

    result = put(f"/products/{product_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Product {product_id} updated")
    else:
        print_error(str(result))
