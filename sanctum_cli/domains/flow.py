"""Sanctum Flow domain commands."""

import builtins
import json

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_cli.group import HelpfulGroup
from sanctum_client.client import flow_get, flow_patch, flow_post, set_flow_api_key


@click.group(cls=HelpfulGroup)
@click.option(
    "--api-key",
    envvar=["SANCTUM_FLOW_API_KEY", "FLOW_API_KEY"],
    default=None,
    help="Flow API key (defaults to $SANCTUM_FLOW_API_KEY or $FLOW_API_KEY)",
)
@click.pass_context
def flow(ctx: click.Context, api_key: str | None) -> None:
    """Manage Sanctum Flow definitions, instances, steps, and simulations.

    Requires --api-key, $SANCTUM_FLOW_API_KEY, or $FLOW_API_KEY for production.
    Core agent bearer tokens are NOT accepted by the Flow API.
    """
    ctx.ensure_object(dict)
    if api_key:
        set_flow_api_key(api_key)


def _load_json(value: str | None, file_path: str | None, option_name: str) -> object | None:
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


def _definition_rows(result: object) -> list[dict]:
    if isinstance(result, builtins.list):
        return result
    if isinstance(result, dict):
        for key in ("definitions", "items", "results"):
            value = result.get(key)
            if isinstance(value, builtins.list):
                return value
    return []


def _print_result(ctx: click.Context, result: object, success: str) -> None:
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and result.get("error"):
        print_error(str(result))
    else:
        print_success(success)


@flow.command("list")
@click.option("--definition-key", default=None, help="Filter by definition key")
@click.option("--status", default=None, help="Filter by status")
@click.option("--account-id", default=None, help="Filter by account UUID")
@click.option("--category", default=None, help="Filter by category")
@click.option("--limit", "limit", default=50, type=click.IntRange(1, 200), help="Max results")
@click.option("--offset", default=0, type=int, help="Pagination offset")
@click.pass_context
def list_definitions(
    ctx: click.Context,
    definition_key: str | None,
    status: str | None,
    account_id: str | None,
    category: str | None,
    limit: int,
    offset: int,
) -> None:
    """List process definitions (MCP: process_list)."""
    check_command_identity("flow", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit), "offset": str(offset)}
    if definition_key:
        params["definition_key"] = definition_key
    if status:
        params["status"] = status
    if account_id:
        params["account_id"] = account_id
    if category:
        params["category"] = category

    result = flow_get("/process-definitions/", params=params)
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    definitions = _definition_rows(result)
    if not definitions:
        click.echo("No process definitions found.")
        return

    rows = [
        [
            d.get("id", ""),
            d.get("definition_key", ""),
            d.get("version", ""),
            d.get("name", "")[:50],
            d.get("status", ""),
            d.get("category", ""),
        ]
        for d in definitions
    ]
    print_table(
        ["ID", "Key", "Version", "Name", "Status", "Category"], rows, title="Flow Definitions"
    )


@flow.command("show")
@click.argument("resource_id")
@click.option(
    "--type",
    "resource_type",
    type=click.Choice(["definition", "instance"]),
    default="definition",
    help="Resource type to show",
)
@click.option("--include-steps", is_flag=True, help="Include instance steps")
@click.option("--include-events", is_flag=True, help="Include instance events")
@click.pass_context
def show(
    ctx: click.Context,
    resource_id: str,
    resource_type: str,
    include_steps: bool,
    include_events: bool,
) -> None:
    """Show a definition or instance (MCP: process_show)."""
    check_command_identity("flow", "show", ctx.obj.get("resolved_agent"))
    if resource_type == "definition":
        result = flow_get(f"/process-definitions/{resource_id}")
    else:
        result = flow_get(f"/process-instances/{resource_id}")
        if include_steps:
            result["steps"] = flow_get(f"/process-instances/{resource_id}/steps")
        if include_events:
            result["events"] = flow_get(f"/process-instances/{resource_id}/events")

    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value(
        {
            "ID": result.get("id"),
            "Name": result.get("name"),
            "Key": result.get("definition_key"),
            "Version": result.get("version"),
            "Status": result.get("status"),
            "Account": result.get("account_id"),
            "Definition": result.get("definition_id"),
            "Entity": result.get("entity_id"),
            "Created": result.get("created_at"),
            "Updated": result.get("updated_at"),
        },
        title=f"Flow {resource_type}: {resource_id}",
    )


@flow.command("definition-create")
@click.option("--account-id", required=True, help="Owning account UUID")
@click.option("--definition-key", required=True, help="Stable process key")
@click.option("--name", required=True, help="Definition name")
@click.option("--description", default=None, help="Definition description")
@click.option("--schema", "schema_json", default=None, help="Definition schema JSON")
@click.option(
    "--schema-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to definition schema JSON",
)
@click.option("--bpmn-xml", default=None, help="Raw BPMN XML")
@click.option(
    "--bpmn-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to BPMN XML file",
)
@click.option("--category", default=None, help="Definition category")
@click.option("--created-by", default=None, help="Creator identifier")
@click.option("--skip-lint", is_flag=True, help="Bypass Flow lint validation")
@click.pass_context
def definition_create(
    ctx: click.Context,
    account_id: str,
    definition_key: str,
    name: str,
    description: str | None,
    schema_json: str | None,
    schema_file: str | None,
    bpmn_xml: str | None,
    bpmn_file: str | None,
    category: str | None,
    created_by: str | None,
    skip_lint: bool,
) -> None:
    """Create a draft process definition."""
    check_command_identity("flow", "definition-create", ctx.obj.get("resolved_agent"))
    if bpmn_xml and bpmn_file:
        print_error("Provide either --bpmn-xml or --bpmn-file, not both.")
        return
    schema = _load_json(schema_json, schema_file, "schema")
    if (schema_json or schema_file) and schema is None:
        return
    payload: dict = {"account_id": account_id, "definition_key": definition_key, "name": name}
    if description:
        payload["description"] = description
    if schema is not None:
        payload["schema_"] = schema
    if bpmn_file:
        with open(bpmn_file) as f:
            payload["bpmn_xml"] = f.read()
    elif bpmn_xml:
        payload["bpmn_xml"] = bpmn_xml
    if category:
        payload["category"] = category
    if created_by:
        payload["created_by"] = created_by

    params = {"skip_lint": "true"} if skip_lint else None
    result = flow_post("/process-definitions/", json=payload, params=params)
    definition_id = result.get("id") if isinstance(result, dict) else None
    _print_result(ctx, result, f"Flow definition created: {definition_id or definition_key}")


@flow.command("definition-update")
@click.argument("definition_id")
@click.option("--definition-key", default=None, help="New definition key")
@click.option("--name", default=None, help="New definition name")
@click.option("--description", default=None, help="New description")
@click.option("--schema", "schema_json", default=None, help="Definition schema JSON")
@click.option(
    "--schema-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to definition schema JSON",
)
@click.option("--bpmn-xml", default=None, help="Raw BPMN XML")
@click.option(
    "--bpmn-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to BPMN XML file",
)
@click.option("--category", default=None, help="New category")
@click.option("--skip-lint", is_flag=True, help="Bypass Flow lint validation")
@click.pass_context
def definition_update(
    ctx: click.Context,
    definition_id: str,
    definition_key: str | None,
    name: str | None,
    description: str | None,
    schema_json: str | None,
    schema_file: str | None,
    bpmn_xml: str | None,
    bpmn_file: str | None,
    category: str | None,
    skip_lint: bool,
) -> None:
    """Update a draft process definition."""
    check_command_identity("flow", "definition-update", ctx.obj.get("resolved_agent"))
    if bpmn_xml and bpmn_file:
        print_error("Provide either --bpmn-xml or --bpmn-file, not both.")
        return
    schema = _load_json(schema_json, schema_file, "schema")
    if (schema_json or schema_file) and schema is None:
        return
    payload: dict = {}
    if definition_key:
        payload["definition_key"] = definition_key
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    if schema is not None:
        payload["schema_"] = schema
    if bpmn_file:
        with open(bpmn_file) as f:
            payload["bpmn_xml"] = f.read()
    elif bpmn_xml:
        payload["bpmn_xml"] = bpmn_xml
    if category:
        payload["category"] = category
    if not payload:
        print_error("Nothing to update. Provide at least one field option.")
        return

    params = {"skip_lint": "true"} if skip_lint else None
    result = flow_patch(f"/process-definitions/{definition_id}", json=payload, params=params)
    _print_result(ctx, result, f"Flow definition updated: {definition_id}")


@flow.command("definition-publish")
@click.argument("definition_id")
@click.option("--skip-lint", is_flag=True, help="Bypass Flow lint validation")
@click.pass_context
def definition_publish(ctx: click.Context, definition_id: str, skip_lint: bool) -> None:
    """Publish a draft process definition."""
    check_command_identity("flow", "definition-publish", ctx.obj.get("resolved_agent"))
    params = {"skip_lint": "true"} if skip_lint else None
    result = flow_post(f"/process-definitions/{definition_id}/publish", params=params)
    _print_result(ctx, result, f"Flow definition published: {definition_id}")


@flow.command("lint")
@click.option("--schema", "schema_json", default=None, help="Definition schema JSON")
@click.option(
    "--schema-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to definition schema JSON",
)
@click.pass_context
def lint(ctx: click.Context, schema_json: str | None, schema_file: str | None) -> None:
    """Dry-run Flow BPMN/schema lint validation."""
    check_command_identity("flow", "lint", ctx.obj.get("resolved_agent"))
    schema = _load_json(schema_json, schema_file, "schema")
    if schema is None:
        print_error("Provide --schema or --schema-file.")
        return
    result = flow_post("/process-definitions/lint", json={"schema_": schema})
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and result.get("passed"):
        print_success("Flow lint passed")
    else:
        print_error(str(result))


@flow.command("instance-create")
@click.option("--definition-id", required=True, help="Published definition UUID")
@click.option("--account-id", required=True, help="Owning account UUID")
@click.option("--started-by", default=None, help="Actor creating the instance")
@click.option("--entity-type", default=None, help="Linked entity type")
@click.option("--entity-id", default=None, help="Linked entity UUID")
@click.option("--context", "context_json", default=None, help="Instance context JSON")
@click.option(
    "--context-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to instance context JSON",
)
@click.pass_context
def instance_create(
    ctx: click.Context,
    definition_id: str,
    account_id: str,
    started_by: str | None,
    entity_type: str | None,
    entity_id: str | None,
    context_json: str | None,
    context_file: str | None,
) -> None:
    """Create a process instance (MCP: process_instance_create)."""
    check_command_identity("flow", "instance-create", ctx.obj.get("resolved_agent"))
    context = _load_json(context_json, context_file, "context")
    if (context_json or context_file) and context is None:
        return
    payload: dict = {"definition_id": definition_id, "account_id": account_id}
    if started_by:
        payload["started_by"] = started_by
    if entity_type:
        payload["entity_type"] = entity_type
    if entity_id:
        payload["entity_id"] = entity_id
    if context is not None:
        payload["context"] = context
    result = flow_post("/process-instances/", json=payload)
    instance_id = result.get("id") if isinstance(result, dict) else None
    _print_result(ctx, result, f"Flow instance created: {instance_id or definition_id}")


@flow.command("context-update")
@click.argument("instance_id")
@click.option("--context", "context_json", default=None, help="Context merge patch JSON")
@click.option(
    "--context-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to context merge patch JSON",
)
@click.pass_context
def context_update(
    ctx: click.Context,
    instance_id: str,
    context_json: str | None,
    context_file: str | None,
) -> None:
    """Merge-patch an instance context."""
    check_command_identity("flow", "context-update", ctx.obj.get("resolved_agent"))
    context = _load_json(context_json, context_file, "context")
    if context is None:
        print_error("Provide --context or --context-file.")
        return
    result = flow_patch(f"/process-instances/{instance_id}/context", json={"context": context})
    _print_result(ctx, result, f"Flow instance context updated: {instance_id}")


@flow.command("instance-action")
@click.argument("instance_id")
@click.option(
    "--action",
    required=True,
    type=click.Choice(["suspend", "resume", "cancel", "fail"]),
    help="Instance lifecycle action",
)
@click.option("--actor", required=True, help="Actor performing the action")
@click.option("--comment", default=None, help="Optional action comment")
@click.pass_context
def instance_action(
    ctx: click.Context,
    instance_id: str,
    action: str,
    actor: str,
    comment: str | None,
) -> None:
    """Run an instance lifecycle action."""
    check_command_identity("flow", "instance-action", ctx.obj.get("resolved_agent"))
    payload = {"action": action, "actor": actor}
    if comment:
        payload["comment"] = comment
    result = flow_post(f"/process-instances/{instance_id}/actions", json=payload)
    _print_result(ctx, result, f"Flow instance action applied: {action}")


@flow.command("update-step")
@click.argument("instance_id")
@click.argument("step_id")
@click.option(
    "--action",
    required=True,
    type=click.Choice(
        ["start", "complete", "approve", "reject", "skip", "block", "unblock", "assign"]
    ),
    help="Step action",
)
@click.option("--actor", required=True, help="Actor performing the action")
@click.option("--assignee", default=None, help="Required for assign")
@click.option("--comment", default=None, help="Optional action comment")
@click.option("--detail", "detail_json", default=None, help="Action detail JSON")
@click.option(
    "--detail-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to action detail JSON",
)
@click.pass_context
def update_step(
    ctx: click.Context,
    instance_id: str,
    step_id: str,
    action: str,
    actor: str,
    assignee: str | None,
    comment: str | None,
    detail_json: str | None,
    detail_file: str | None,
) -> None:
    """Execute a step action (MCP: process_instance_update_step)."""
    check_command_identity("flow", "update-step", ctx.obj.get("resolved_agent"))
    detail = _load_json(detail_json, detail_file, "detail")
    if (detail_json or detail_file) and detail is None:
        return
    payload: dict = {"action": action, "actor": actor}
    if assignee:
        payload["assignee"] = assignee
    if comment:
        payload["comment"] = comment
    if detail is not None:
        payload["detail"] = detail
    result = flow_post(f"/process-instances/{instance_id}/steps/{step_id}/actions", json=payload)
    _print_result(ctx, result, f"Flow step action applied: {action}")


@flow.command("simulate")
@click.argument("definition_id")
@click.option("--n-runs", default=1000, type=click.IntRange(1, 10000), help="Simulation runs")
@click.option("--seed", default=None, type=int, help="Simulation seed")
@click.pass_context
def simulate(ctx: click.Context, definition_id: str, n_runs: int, seed: int | None) -> None:
    """Run a Monte Carlo simulation (MCP: process_simulate)."""
    check_command_identity("flow", "simulate", ctx.obj.get("resolved_agent"))
    payload: dict = {"n_runs": n_runs}
    if seed is not None:
        payload["seed"] = seed
    result = flow_post(f"/process-definitions/{definition_id}/simulate", json=payload)
    run_id = result.get("id") if isinstance(result, dict) else None
    _print_result(ctx, result, f"Flow simulation started: {run_id or definition_id}")


@flow.command("simulation-results")
@click.argument("run_id")
@click.option(
    "--include-results/--no-include-results", default=True, help="Include per-step results"
)
@click.option(
    "--include-recommendations/--no-include-recommendations",
    default=True,
    help="Include AI recommendations",
)
@click.pass_context
def simulation_results(
    ctx: click.Context,
    run_id: str,
    include_results: bool,
    include_recommendations: bool,
) -> None:
    """Show simulation results (MCP: simulation_results_show)."""
    check_command_identity("flow", "simulation-results", ctx.obj.get("resolved_agent"))
    result = flow_get(f"/simulation-runs/{run_id}")
    if include_results:
        result["results"] = flow_get(f"/simulation-runs/{run_id}/results")
    if include_recommendations:
        result["recommendations"] = flow_get(f"/simulation-runs/{run_id}/recommendations")

    if ctx.obj.get("output_json"):
        print_json(result)
        return
    print_key_value(
        {
            "ID": result.get("id"),
            "Definition": result.get("definition_id"),
            "Status": result.get("status"),
            "Runs": result.get("n_runs"),
            "P50": result.get("cycle_time_p50_s"),
            "P95": result.get("cycle_time_p95_s"),
            "Created": result.get("created_at"),
        },
        title=f"Flow Simulation: {run_id}",
    )
