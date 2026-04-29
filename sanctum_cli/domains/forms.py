"""Form template domain commands."""

import json

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_success
from sanctum_client.client import forms_delete, forms_patch, forms_post, set_forms_account_id


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


@templates.command()
@click.option("--name", "-n", required=True, help="Template name")
@click.option(
    "--field-schema",
    "-f",
    default=None,
    help="Field schema as JSON (e.g. '[{\"name\":\"email\",\"type\":\"email\"}]')",
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

    if field_schema and field_schema_file:
        print_error("Provide either --field-schema or --field-schema-file, not both.")
        return
    if settings and settings_file:
        print_error("Provide either --settings or --settings-file, not both.")
        return

    payload: dict = {"name": name}

    if field_schema_file:
        with open(field_schema_file) as f:
            payload["field_schema"] = json.load(f)
    elif field_schema:
        try:
            payload["field_schema"] = json.loads(field_schema)
        except json.JSONDecodeError as e:
            print_error(f"Invalid --field-schema JSON: {e}")
            return

    if settings_file:
        with open(settings_file) as f:
            payload["settings"] = json.load(f)
    elif settings:
        try:
            payload["settings"] = json.loads(settings)
        except json.JSONDecodeError as e:
            print_error(f"Invalid --settings JSON: {e}")
            return

    if notification_emails:
        payload["notification_emails"] = list(notification_emails)
    if notify_template_id:
        payload["notify_template_id"] = notify_template_id

    result = forms_post("/templates/", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Form template created: {result['id']} (v{result.get('version', 1)})")
    else:
        print_error(str(result))


@forms.group()
def submissions() -> None:
    """Manage form submissions."""
    pass


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
@click.pass_context
def update(
    ctx: click.Context, submission_id: str, fields: tuple[str, ...], payload_file: str | None
) -> None:
    """Update a submission's payload fields."""
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

    if not payload_update:
        print_error("Nothing to update. Provide --field or --payload-file.")
        return

    result = forms_patch(f"/submissions/{submission_id}", json={"payload": payload_update})
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Submission {submission_id} updated")
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
        payload["allowed_origins"] = list(allowed_origins)

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
