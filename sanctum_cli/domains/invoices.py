"""Invoice domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_key_value, print_table
from sanctum_client.client import get


@click.group()
def invoices() -> None:
    """Manage invoices."""
    pass


@invoices.command()
@click.argument("invoice_id")
@click.pass_context
def show(ctx: click.Context, invoice_id: str) -> None:
    """Show invoice details."""
    check_command_identity("invoices", "show", ctx.obj.get("resolved_agent"))

    check_command_identity("invoices", "show", ctx.obj.get("resolved_agent"))
    result = get(f"/invoices/{invoice_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value({
        "ID": result.get("id"),
        "Description": result.get("description"),
        "Status": result.get("status"),
        "Amount": f"${result.get('amount', '0')}",
        "Account": result.get("account_name"),
        "Created": result.get("created_at"),
        "Due": result.get("due_date"),
    }, title=f"Invoice: {result.get('description', '')}")


@invoices.command()
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, status: str | None, limit: int) -> None:
    """List invoices."""
    check_command_identity("invoices", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("invoices", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if status:
        params["status"] = status
    result = get("/invoices", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    invoices_list = result if isinstance(result, builtins.list) else result.get("invoices", [])
    if not invoices_list:
        click.echo("No invoices found.")
        return

    rows = []
    for inv in invoices_list:
        rows.append([
            inv.get("description", "")[:40],
            inv.get("status", ""),
            f"${inv.get('amount', '0')}",
            inv.get("account_name", ""),
        ])
    print_table(["Description", "Status", "Amount", "Account"], rows, title="Invoices")
