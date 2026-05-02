"""Template domain commands."""

import builtins
import json

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_success, print_table
from sanctum_client.client import get, post, put


@click.group()
def templates() -> None:
    """Manage project templates."""
    pass


@templates.command()
@click.option("--name", "-n", required=True, help="Template name")
@click.option(
    "--type",
    "-t",
    "template_type",
    required=True,
    type=click.Choice(["project", "task", "milestone"]),
    help="Template type",
)
@click.option("--category", "-c", default=None, help="Template category")
@click.option("--description", "-d", default=None, help="Template description")
@click.option("--icon", default=None, help="Template icon")
@click.option(
    "--tag",
    multiple=True,
    default=[],
    help="Tag for the template (repeatable)",
)
@click.option(
    "--is-active/--no-is-active",
    default=True,
    help="Set template as active or inactive",
)
@click.option(
    "--sections-json",
    default=None,
    help='Sections as JSON (e.g. \'[{"name":"Section 1","items":[{"name":"Item 1"}]}]\')',
)
@click.option(
    "--sections-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to JSON file containing sections array",
)
@click.pass_context
def create(
    ctx: click.Context,
    name: str,
    template_type: str,
    category: str | None,
    description: str | None,
    icon: str | None,
    tag: tuple[str, ...],
    is_active: bool,
    sections_json: str | None,
    sections_file: str | None,
) -> None:
    """Create a new template."""
    check_command_identity("templates", "create", ctx.obj.get("resolved_agent"))

    # Handle JSON input for sections (following forms.py pattern)
    sections_data = None
    if sections_json and sections_file:
        print_error("Provide either --sections-json or --sections-file, not both.")
        return
    elif sections_file:
        with open(sections_file) as f:
            sections_data = json.load(f)
    elif sections_json:
        try:
            sections_data = json.loads(sections_json)
        except json.JSONDecodeError as e:
            print_error(f"Invalid --sections-json JSON: {e}")
            return

    payload: dict = {
        "name": name,
        "template_type": template_type,
        "is_active": is_active,
    }
    if category:
        payload["category"] = category
    if description:
        payload["description"] = description
    if icon:
        payload["icon"] = icon
    if tag:
        payload["tags"] = builtins.list(tag)
    if sections_data is not None:
        payload["sections"] = sections_data

    result = post("/templates", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Template created: {result['id']}")
        click.echo(f"  Name:   {result['name']}")
        click.echo(f"  Type:   {result.get('template_type', '')}")
        click.echo(f"  Active: {result.get('is_active', True)}")
    else:
        print_error(str(result))


@templates.command()
@click.option("--type", "-t", "template_type", default=None, help="Filter by template type")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, template_type: str | None, limit: int) -> None:
    """List available templates."""
    check_command_identity("templates", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("templates", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if template_type:
        params["template_type"] = template_type
    result = get("/templates", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    templates_list = result if isinstance(result, builtins.list) else result.get("templates", [])
    if not templates_list:
        click.echo("No templates found.")
        return

    rows = []
    for t in templates_list:
        rows.append(
            [
                t.get("name", "")[:50],
                t.get("template_type", ""),
                t.get("category", ""),
                "✓" if t.get("is_active") else "—",
            ]
        )
    print_table(["Name", "Type", "Category", "Active"], rows, title="Templates")


@templates.command()
@click.argument("template_id")
@click.pass_context
def show(ctx: click.Context, template_id: str) -> None:
    """Show template with its full section/item tree."""
    check_command_identity("templates", "show", ctx.obj.get("resolved_agent"))

    check_command_identity("templates", "show", ctx.obj.get("resolved_agent"))
    result = get(f"/templates/{template_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    click.echo(f"\n[bold]{result.get('name', '')}[/bold]")
    for section in result.get("sections", []):
        click.echo(f"\n  ## {section.get('name', '')}")
        for item in section.get("items", []):
            click.echo(f"    - [{item.get('ticket_type', 'task')}] {item.get('name', '')}")


@templates.command()
@click.argument("template_id")
@click.option("--name", "-n", default=None, help="New template name")
@click.option("--description", "-d", default=None, help="New template description")
@click.option("--icon", default=None, help="New template icon")
@click.option(
    "--tag",
    multiple=True,
    default=[],
    help="Tag for the template (repeatable)",
)
@click.option("--category", "-c", default=None, help="New template category")
@click.option(
    "--template-type",
    "-t",
    "template_type",
    default=None,
    type=click.Choice(["project", "task", "milestone"]),
    help="New template type",
)
@click.option(
    "--is-active/--no-is-active",
    default=None,
    help="Set template as active or inactive",
)
@click.option(
    "--sections-json",
    default=None,
    help='Sections as JSON (e.g. \'[{"name":"Section 1","items":[{"name":"Item 1"}]}]\')',
)
@click.option(
    "--sections-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to JSON file containing sections array",
)
@click.pass_context
def update(
    ctx: click.Context,
    template_id: str,
    name: str | None,
    description: str | None,
    icon: str | None,
    tag: tuple[str, ...],
    category: str | None,
    template_type: str | None,
    is_active: bool | None,
    sections_json: str | None,
    sections_file: str | None,
) -> None:
    """Update an existing template."""
    check_command_identity("templates", "update", ctx.obj.get("resolved_agent"))

    # Handle JSON input for sections (following forms.py pattern)
    sections_data = None
    if sections_json and sections_file:
        print_error("Provide either --sections-json or --sections-file, not both.")
        return
    elif sections_file:
        with open(sections_file) as f:
            sections_data = json.load(f)
    elif sections_json:
        try:
            sections_data = json.loads(sections_json)
        except json.JSONDecodeError as e:
            print_error(f"Invalid --sections-json JSON: {e}")
            return

    payload: dict = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if icon is not None:
        payload["icon"] = icon
    if category is not None:
        payload["category"] = category
    if template_type is not None:
        payload["template_type"] = template_type
    if is_active is not None:
        payload["is_active"] = is_active
    if tag:
        payload["tags"] = builtins.list(tag)
    if sections_data is not None:
        payload["sections"] = sections_data

    if not payload:
        print_error("Nothing to update. Provide at least one option to change.")
        return

    result = put(f"/templates/{template_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Template {template_id} updated")
    elif isinstance(result, dict) and result.get("error"):
        print_error(f"Template update failed: {result}")
    else:
        print_error(str(result))


@templates.command()
@click.argument("template_id")
@click.option("--account-id", "-a", required=True, help="Account UUID")
@click.option("--project-id", "-p", required=True, help="Project UUID to scaffold")
@click.option(
    "--variable",
    "-v",
    "variables",
    multiple=True,
    default=[],
    help="Template variables as key=value (repeatable)",
)
@click.pass_context
def apply(
    ctx: click.Context,
    template_id: str,
    account_id: str,
    project_id: str,
    variables: tuple[str, ...],
) -> None:
    """Apply a template to scaffold milestones and tickets in a project."""
    check_command_identity("templates", "apply", ctx.obj.get("resolved_agent"))

    var_dict: dict[str, str] = {}
    for v in variables:
        if "=" not in v:
            print_error(f"Invalid variable format: {v} (expected key=value)")
            return
        key, _, value = v.partition("=")
        var_dict[key] = value

    result = post(
        f"/templates/{template_id}/apply",
        json={
            "account_id": account_id,
            "project_id": project_id,
            "variables": var_dict or None,
        },
    )
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and result.get("error"):
        print_error(f"Template apply failed: {result}")
    else:
        print_success(f"Template {template_id} applied to project {project_id}")
