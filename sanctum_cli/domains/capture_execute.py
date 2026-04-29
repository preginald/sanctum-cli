"""Capture-to-Execution pipeline commands."""

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_success
from sanctum_client.client import get, post, put


@click.group(name="capture-execute")
def capture_execute() -> None:
    """Manage the Capture-to-Execution pipeline."""
    pass


@capture_execute.command()
@click.argument("name")
@click.option("--account-id", "-a", required=True, help="Account UUID")
@click.option("--description", "-d", default="", help="Project description")
@click.pass_context
def capture(ctx: click.Context, name: str, account_id: str, description: str) -> None:
    """Capture a new idea in capture status (zero friction)."""
    check_command_identity("capture_execute", "capture", ctx.obj.get("resolved_agent"))

    payload: dict = {"name": name, "account_id": account_id, "status": "capture"}
    if description:
        payload["description"] = description

    result = post("/projects", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Project captured: {result['id']}")
        click.echo(f"  Name:   {result['name']}")
        click.echo(f"  Status: {result['status']}")
    else:
        print_error(str(result))


@capture_execute.command()
@click.argument("project_id")
@click.option("--template-id", "-t", default=None, help="Template UUID to apply")
@click.option(
    "--variable",
    "-v",
    "variables",
    multiple=True,
    default=[],
    help="Template variables as key=value (repeatable)",
)
@click.pass_context
def execute(
    ctx: click.Context,
    project_id: str,
    template_id: str | None,
    variables: tuple[str, ...],
) -> None:
    """Scaffold and activate a captured project."""
    check_command_identity("capture_execute", "execute", ctx.obj.get("resolved_agent"))

    var_dict: dict[str, str] = {}
    for v in variables:
        if "=" not in v:
            print_error(f"Invalid variable format: {v} (expected key=value)")
            return
        key, _, value = v.partition("=")
        var_dict[key] = value

    # Fetch project to get account_id and current status
    project = get(f"/projects/{project_id}")
    account_id = project.get("account_id")
    if not account_id:
        print_error("Project has no account_id")
        return
    current_status = project.get("status", "capture")

    if template_id:
        tmpl_result = post(
            f"/templates/{template_id}/apply",
            json={
                "account_id": account_id,
                "project_id": project_id,
                "variables": var_dict or None,
            },
        )
        if isinstance(tmpl_result, dict) and tmpl_result.get("error"):
            print_error(f"Template apply failed: {tmpl_result}")
            return

    # SYS-030: capture → planning → active (two-step transition)
    if current_status == "capture":
        planning_result = put(f"/projects/{project_id}", json={"status": "planning"})
        if isinstance(planning_result, dict) and planning_result.get("error"):
            print_error(f"Status transition to planning failed: {planning_result}")
            return

    result = put(f"/projects/{project_id}", json={"status": "active"})
    if isinstance(result, dict) and result.get("error"):
        print_error(f"Activation failed: {result}")
        return

    post("/workbench/pin", json={"project_id": project_id})

    if ctx.obj.get("output_json"):
        print_json(result)
    else:
        print_success(f"Project activated: {result.get('name', project_id)}")
