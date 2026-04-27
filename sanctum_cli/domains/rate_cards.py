"""Rate card domain commands."""

import builtins

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_table
from sanctum_client.client import get


@click.group()
def rate_cards() -> None:
    """Manage rate cards."""
    pass


@rate_cards.command()
@click.option("--account-id", "-a", default=None, help="Filter by account UUID")
@click.option("--tier", "-t", default=None, help="Filter by tier")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, account_id: str | None, tier: str | None, limit: int) -> None:
    """List rate cards."""
    check_command_identity("rate_cards", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if account_id:
        params["account_id"] = account_id
    if tier:
        params["tier"] = tier
    result = get("/rate-cards", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    cards = result if isinstance(result, builtins.list) else result.get("rate_cards", [])
    if not cards:
        click.echo("No rate cards found.")
        return

    rows = []
    for c in cards:
        rows.append([
            c.get("tier", ""),
            f"${c.get('hourly_rate', '0')}/hr",
            c.get("account_name", "System Default"),
        ])
    print_table(["Tier", "Rate", "Account"], rows, title="Rate Cards")


@rate_cards.command(name="lookup")
@click.option("--account-id", "-a", required=True, help="Account UUID")
@click.option("--tier", "-t", required=True, help="Rate tier")
@click.pass_context
def lookup(ctx: click.Context, account_id: str, tier: str) -> None:
    """Look up effective rate for an account and tier."""
    check_command_identity("rate_cards", "lookup", ctx.obj.get("resolved_agent"))
    result = get("/rate-cards/lookup", params={"account_id": account_id, "tier": tier})
    if ctx.obj.get("output_json"):
        print_json(result)
        return
    click.echo(f"Effective rate: ${result.get('hourly_rate', '?')}/hr")
