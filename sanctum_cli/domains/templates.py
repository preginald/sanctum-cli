"""Template domain commands."""

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_table
from sanctum_client.client import get


@click.group()
def templates() -> None:
    """Manage project templates."""
    pass


@templates.command()
@click.option("--type", "-t", "template_type", default=None, help="Filter by template type")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, template_type: str | None, limit: int) -> None:
    """List available templates."""
    check_command_identity("templates", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if template_type:
        params["template_type"] = template_type
    result = get("/templates", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    templates_list = result if isinstance(result, list) else result.get("templates", [])
    if not templates_list:
        click.echo("No templates found.")
        return

    rows = []
    for t in templates_list:
        rows.append([
            t.get("name", "")[:50],
            t.get("template_type", ""),
            t.get("category", ""),
            "✓" if t.get("is_active") else "—",
        ])
    print_table(["Name", "Type", "Category", "Active"], rows, title="Templates")


@templates.command()
@click.argument("template_id")
@click.pass_context
def show(ctx: click.Context, template_id: str) -> None:
    """Show template with its full section/item tree."""
    check_command_identity("templates", "show", ctx.obj.get("resolved_agent"))
    result = get(f"/templates/{template_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    click.echo(f"\n[bold]{result.get('name', '')}[/bold]")
    for section in result.get("sections", []):
        click.echo(f"\n  ## {section['name']}")
        for item in section.get("items", []):
            click.echo(f"    - [{item.get('ticket_type', 'task')}] {item['name']}")
