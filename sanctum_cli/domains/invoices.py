"""Invoice domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_client.client import get, post, put


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

    print_key_value(
        {
            "ID": result.get("id"),
            "Description": result.get("description"),
            "Status": result.get("status"),
            "Total Amount": f"${result.get('total_amount', '0')}",
            "Account": result.get("account_name"),
            "Created": result.get("generated_at"),
            "Due": result.get("due_date"),
        },
        title=f"Invoice: {result.get('description', '')}",
    )


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
        rows.append(
            [
                str(inv.get("id", ""))[:8],
                inv.get("description", "")[:40],
                inv.get("status", ""),
                f"${inv.get('total_amount', '0')}",
                inv.get("account_name", ""),
            ]
        )
    print_table(["ID", "Description", "Status", "Amount", "Account"], rows, title="Invoices")


@invoices.command()
@click.argument("invoice_id")
@click.option(
    "--method",
    "-m",
    required=True,
    help="Payment method (eft, cash, cheque, credit_card, etc.)",
)
@click.option(
    "--date",
    "-d",
    "paid_at",
    default=None,
    help="Payment date (default now, ISO format e.g. 2025-04-28T10:00:00)",
)
@click.pass_context
def pay(
    ctx: click.Context,
    invoice_id: str,
    method: str,
    paid_at: str | None,
) -> None:
    """Record a payment and transition invoice to paid."""
    check_command_identity("invoices", "pay", ctx.obj.get("resolved_agent"))

    payload: dict = {"status": "paid", "payment_method": method}
    if paid_at:
        payload["paid_at"] = paid_at

    result = put(f"/invoices/{invoice_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and result.get("error"):
        print_error(f"Payment failed: {result}")
    elif isinstance(result, dict) and result.get("status") == "paid":
        print_success(f"Invoice {invoice_id} paid")
    else:
        print_error(f"Unexpected response: {result}")


@invoices.command()
@click.argument("invoice_id")
@click.option("--to", "-t", "to_email", required=True, help="Recipient email address")
@click.option("--cc", "cc_emails", default="", help="CC email(s), comma-separated")
@click.pass_context
def send_receipt(
    ctx: click.Context,
    invoice_id: str,
    to_email: str,
    cc_emails: str,
) -> None:
    """Send a payment receipt email to the client."""
    check_command_identity("invoices", "send_receipt", ctx.obj.get("resolved_agent"))

    parsed_cc = [e.strip() for e in cc_emails.split(",") if e.strip()] if cc_emails else []

    payload: dict = {"to_email": to_email}
    if parsed_cc:
        payload["cc_emails"] = parsed_cc

    result = post(f"/invoices/{invoice_id}/send", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and result.get("error"):
        print_error(f"Send receipt failed: {result}")
    elif isinstance(result, dict) and result.get("status") == "sent":
        print_success(f"Receipt sent for invoice {invoice_id}")
    else:
        print_error(f"Unexpected response: {result}")
