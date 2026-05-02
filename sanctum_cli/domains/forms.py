"""Form template domain commands."""

import builtins
import json

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_client.client import (
    forms_delete,
    forms_get,
    forms_patch,
    forms_post,
    set_forms_account_id,
)


@click.group()
@click.option("--account-id", required=True, help="Account UUID for tenant scoping")
@click.pass_context
def forms(ctx: click.Context, account_id: str) -> None:
    """Manage Sanctum Forms templates and instances."""
    ctx.ensure_object(dict)
    set_forms_account_id(account_id)


@forms.group()
def templates() -> None:
    """Manage form templates."""
    pass


def _load_json_option(value: str | None, file_path: str | None, option_name: str) -> object | None:
    if value and file_path:
        print_error(f"Provide either --{option_name} or --{option_name}-file, not both.")
        return None
    if file_path:
        with open(file_path) as f:
            return json.load(f)
    if value:
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            print_error(f"Invalid --{option_name} JSON: {e}")
            return None
    return None


def _template_payload(
    name: str | None,
    field_schema: str | None,
    field_schema_file: str | None,
    notification_emails: tuple[str, ...],
    notify_template_id: str | None,
    settings: str | None,
    settings_file: str | None,
) -> dict | None:
    payload: dict = {}
    if name is not None:
        payload["name"] = name

    field_schema_data = _load_json_option(field_schema, field_schema_file, "field-schema")
    if (field_schema or field_schema_file) and field_schema_data is None:
        return None
    if field_schema_data is not None:
        payload["field_schema"] = field_schema_data

    settings_data = _load_json_option(settings, settings_file, "settings")
    if (settings or settings_file) and settings_data is None:
        return None
    if settings_data is not None:
        payload["settings"] = settings_data

    if notification_emails:
        payload["notification_emails"] = builtins.list(notification_emails)
    if notify_template_id is not None:
        payload["notify_template_id"] = notify_template_id
    return payload


def _template_rows(result: object) -> list:
    if isinstance(result, builtins.list):
        return result
    if isinstance(result, dict):
        for key in ("templates", "items", "results"):
            value = result.get(key)
            if isinstance(value, builtins.list):
                return value
    return []


def _print_template_detail(result: dict) -> None:
    print_key_value(
        {
            "ID": result.get("id"),
            "Name": result.get("name"),
            "Version": result.get("version"),
            "Notify Template": result.get("notify_template_id"),
            "Created": result.get("created_at"),
            "Updated": result.get("updated_at"),
        },
        title=f"Form Template: {result.get('name', result.get('id', ''))}",
    )
    field_schema = result.get("field_schema")
    if field_schema:
        click.echo("\nField Schema:")
        click.echo(json.dumps(field_schema, indent=2))
    settings = result.get("settings")
    if settings:
        click.echo("\nSettings:")
        click.echo(json.dumps(settings, indent=2))


@templates.command()
@click.option("--name", "-n", required=True, help="Template name")
@click.option(
    "--field-schema",
    "-f",
    default=None,
    help='Field schema as JSON (e.g. \'[{"name":"email","type":"email"}]\')',
)
@click.option(
    "--field-schema-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to JSON file containing field_schema array",
)
@click.option(
    "--notification-email",
    "-e",
    "notification_emails",
    multiple=True,
    default=[],
    help="Notification email address (repeatable)",
)
@click.option(
    "--notify-template-id",
    default=None,
    help="Notify template slug (e.g. form-submission)",
)
@click.option(
    "--settings",
    "-s",
    default=None,
    help="Settings as JSON string",
)
@click.option(
    "--settings-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to JSON file containing settings",
)
@click.pass_context
def create(
    ctx: click.Context,
    name: str,
    field_schema: str | None,
    field_schema_file: str | None,
    notification_emails: tuple[str, ...],
    notify_template_id: str | None,
    settings: str | None,
    settings_file: str | None,
) -> None:
    """Create a new form template."""
    check_command_identity("forms", "templates.create", ctx.obj.get("resolved_agent"))

    payload = _template_payload(
        name,
        field_schema,
        field_schema_file,
        notification_emails,
        notify_template_id,
        settings,
        settings_file,
    )
    if payload is None:
        return

    result = forms_post("/templates/", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Form template created: {result['id']} (v{result.get('version', 1)})")
    else:
        print_error(str(result))


@templates.command()
@click.option("--limit", "-l", default=20, type=int, help="Max results")
@click.pass_context
def list(ctx: click.Context, limit: int) -> None:
    """List form templates."""
    check_command_identity("forms", "templates.list", ctx.obj.get("resolved_agent"))
    result = forms_get("/templates/", params={"limit": str(limit)})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    templates_list = _template_rows(result)
    if not templates_list:
        click.echo("No form templates found.")
        return

    rows = []
    for template in templates_list:
        rows.append(
            [
                template.get("id", ""),
                template.get("name", "")[:50],
                template.get("version", ""),
                template.get("notify_template_id", ""),
            ]
        )
    print_table(["ID", "Name", "Version", "Notify Template"], rows, title="Form Templates")


@templates.command("show")
@click.argument("template_id")
@click.pass_context
def show_template(ctx: click.Context, template_id: str) -> None:
    """Show a form template."""
    check_command_identity("forms", "templates.show", ctx.obj.get("resolved_agent"))
    result = forms_get(f"/templates/{template_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
    else:
        _print_template_detail(result)


@templates.command("update")
@click.argument("template_id")
@click.option("--name", "-n", default=None, help="New template name")
@click.option(
    "--field-schema",
    "-f",
    default=None,
    help='Field schema as JSON (e.g. \'[{"name":"email","type":"email"}]\')',
)
@click.option(
    "--field-schema-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to JSON file containing field_schema array",
)
@click.option(
    "--notification-email",
    "-e",
    "notification_emails",
    multiple=True,
    default=[],
    help="Notification email address (repeatable; replaces existing value)",
)
@click.option(
    "--notify-template-id",
    default=None,
    help="Notify template slug (e.g. form-submission)",
)
@click.option("--settings", "-s", default=None, help="Settings as JSON string")
@click.option(
    "--settings-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to JSON file containing settings",
)
@click.pass_context
def update_template(
    ctx: click.Context,
    template_id: str,
    name: str | None,
    field_schema: str | None,
    field_schema_file: str | None,
    notification_emails: tuple[str, ...],
    notify_template_id: str | None,
    settings: str | None,
    settings_file: str | None,
) -> None:
    """Update a form template."""
    check_command_identity("forms", "templates.update", ctx.obj.get("resolved_agent"))
    payload = _template_payload(
        name,
        field_schema,
        field_schema_file,
        notification_emails,
        notify_template_id,
        settings,
        settings_file,
    )
    if payload is None:
        return
    if not payload:
        print_error(
            "Nothing to update. Provide --name, --field-schema, --field-schema-file, "
            "--notification-email, --notify-template-id, --settings, or --settings-file."
        )
        return

    result = forms_patch(f"/templates/{template_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Form template {template_id} updated")
    else:
        print_error(str(result))


@templates.command("delete")
@click.argument("template_id")
@click.confirmation_option(prompt="Delete this form template?")
@click.pass_context
def delete_template(ctx: click.Context, template_id: str) -> None:
    """Delete a form template."""
    check_command_identity("forms", "templates.delete", ctx.obj.get("resolved_agent"))
    result = forms_delete(f"/templates/{template_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
    else:
        print_success(f"Form template {template_id} deleted")


@forms.group()
def submissions() -> None:
    """Manage form submissions."""
    pass


@submissions.command()
@click.argument("submission_id")
@click.pass_context
def show(ctx: click.Context, submission_id: str) -> None:
    """Show a submission's payload and metadata."""
    check_command_identity("forms", "submissions.show", ctx.obj.get("resolved_agent"))
    result = forms_get(f"/submissions/{submission_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
    else:
        print_key_value(result)


@submissions.command()
@click.argument("submission_id")
@click.confirmation_option(prompt="Delete this submission?")
@click.pass_context
def delete(ctx: click.Context, submission_id: str) -> None:
    """Soft-delete a submission."""
    check_command_identity("forms", "submissions.delete", ctx.obj.get("resolved_agent"))
    forms_delete(f"/submissions/{submission_id}")
    if ctx.obj.get("output_json"):
        print_json({"status": "deleted"})
    else:
        print_success(f"Submission {submission_id} deleted")


@submissions.command()
@click.argument("submission_id")
@click.option(
    "--field",
    "-f",
    "fields",
    multiple=True,
    default=[],
    help="Payload field as key=value (repeatable)",
)
@click.option(
    "--payload-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to JSON file with payload fields to update",
)
@click.option(
    "--contact-id",
    default=None,
    help="Set core_contact_id on the submission",
)
@click.option(
    "--ticket-id",
    default=None,
    help="Set core_ticket_id on the submission",
)
@click.option(
    "--submitted-by",
    default=None,
    help="Set submitted_by_contact_id on the submission",
)
@click.pass_context
def update(
    ctx: click.Context,
    submission_id: str,
    fields: tuple[str, ...],
    payload_file: str | None,
    contact_id: str | None,
    ticket_id: str | None,
    submitted_by: str | None,
) -> None:
    """Update a submission's payload and/or top-level fields."""
    check_command_identity("forms", "submissions.update", ctx.obj.get("resolved_agent"))

    payload_update: dict = {}
    if fields and payload_file:
        print_error("Provide either --field or --payload-file, not both.")
        return

    if payload_file:
        with open(payload_file) as f:
            payload_update = json.load(f)
    else:
        for f in fields:
            if "=" not in f:
                print_error(f"Invalid field format: {f} (expected key=value)")
                return
            key, _, value = f.partition("=")
            payload_update[key] = value

    body: dict = {}
    if payload_update:
        body["payload"] = payload_update
    if contact_id:
        body["core_contact_id"] = contact_id
    if ticket_id:
        body["core_ticket_id"] = ticket_id
    if submitted_by:
        body["submitted_by_contact_id"] = submitted_by

    if not body:
        print_error(
            "Nothing to update. Provide --field, --payload-file, "
            "--contact-id, --ticket-id, or --submitted-by."
        )
        return

    result = forms_patch(f"/submissions/{submission_id}", json=body)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Submission {submission_id} updated")
    else:
        print_error(str(result))


@submissions.command()
@click.argument("submission_id")
@click.pass_context
def share_token(ctx: click.Context, submission_id: str) -> None:
    """Generate a share link for a submission (admin only).

    The share link lets anyone with the URL view the submission
    without authentication. Tokens expire on server restart.
    """
    check_command_identity("forms", "submissions.share-token", ctx.obj.get("resolved_agent"))
    result = forms_post(f"/submissions/{submission_id}/share-token")
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "share_url" in result:
        print_success(f"Share link: {result['share_url']}")
    else:
        print_error(str(result))


@templates.command()
@click.argument("template_id")
@click.option("--name", "-n", required=True, help="Instance name")
@click.option("--slug", default=None, help="URL slug (auto-generated from name if omitted)")
@click.option("--project-id", default=None, help="Core project UUID")
@click.option(
    "--allowed-origin",
    "allowed_origins",
    multiple=True,
    default=[],
    help="Allowed CORS origin (repeatable)",
)
@click.option(
    "--status",
    type=click.Choice(["active", "paused", "archived"]),
    default="active",
    help="Instance status",
)
@click.pass_context
def deploy(
    ctx: click.Context,
    template_id: str,
    name: str,
    slug: str | None,
    project_id: str | None,
    allowed_origins: tuple[str, ...],
    status: str,
) -> None:
    """Deploy a form instance from a template."""
    check_command_identity("forms", "templates.deploy", ctx.obj.get("resolved_agent"))

    payload: dict = {"name": name, "status": status}
    if slug:
        payload["slug"] = slug
    if project_id:
        payload["project_id"] = project_id
    if allowed_origins:
        payload["allowed_origins"] = builtins.list(allowed_origins)

    result = forms_post(f"/templates/{template_id}/deploy", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(
            f"Form instance deployed: {result['id']}\n"
            f"  Name: {result.get('name', '')}\n"
            f"  Slug: {result.get('slug', '')}\n"
            f"  Status: {result.get('status', '')}\n"
            f"  Endpoint: https://forms.digitalsanctum.com.au/f/{result.get('endpoint_id', '')}"
        )
    else:
        print_error(str(result))
