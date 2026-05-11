"""Tests for operation plan models and validation."""

from sanctum_cli.assist.intent import (
    OperationPlan,
    OperationStep,
    ValidationError,
    classify_risk,
    validate_operation_plan,
)
from sanctum_cli.assist.schema import build_cli_schema
from sanctum_cli.cli import main


def test_operation_step_serialization():
    step = OperationStep(
        id="resolve_project",
        domain="projects",
        action="resolve_by_name",
        parameters={"name": "Sanctum Router"},
        risk="read",
        needs_confirmation=False,
    )
    data = step.to_dict()
    assert data["id"] == "resolve_project"
    assert data["domain"] == "projects"
    assert data["parameters"] == {"name": "Sanctum Router"}
    assert data["risk"] == "read"

    restored = OperationStep.from_dict(data)
    assert restored.id == step.id
    assert restored.parameters == step.parameters
    assert restored.risk == step.risk
    assert restored.needs_confirmation == step.needs_confirmation


def test_operation_plan_serialization():
    plan = OperationPlan(
        intent="Find unresolved tickets for Sanctum Router",
        operations=(
            OperationStep(
                id="list_tickets",
                domain="tickets",
                action="list",
                parameters={"project_id": "abc-123"},
                risk="read",
                needs_confirmation=False,
            ),
        ),
        resolved_entities={"project": {"id": "abc-123", "name": "Sanctum Router"}},
    )
    data = plan.to_dict()
    assert data["intent"] == "Find unresolved tickets for Sanctum Router"
    assert len(data["operations"]) == 1
    assert data["resolved_entities"]["project"]["name"] == "Sanctum Router"

    restored = OperationPlan.from_dict(data)
    assert restored.intent == plan.intent
    assert restored.resolved_entities == plan.resolved_entities


def test_classify_risk_read_action():
    assert classify_risk("tickets", "list") == "read"
    assert classify_risk("projects", "show") == "read"
    assert classify_risk("search", "search") == "read"
    assert classify_risk("monitor", "status") == "read"


def test_classify_risk_write_action():
    assert classify_risk("tickets", "create") == "write"
    assert classify_risk("articles", "update") == "write"
    assert classify_risk("time-entries", "create") == "write"
    assert classify_risk("mockups", "create") == "write"


def test_classify_risk_external_effect_action():
    assert classify_risk("invoices", "send") == "external_effect"
    assert classify_risk("notify", "send") == "external_effect"
    assert classify_risk("articles", "publish") == "external_effect"


def test_classify_risk_destructive_action():
    assert classify_risk("mockups", "delete") == "destructive"
    assert classify_risk("any", "revoke") == "destructive"
    assert classify_risk("any", "rotate") == "destructive"


def test_classify_risk_unknown_action():
    assert classify_risk("unknown", "foobar") == "unknown"


def test_validate_valid_read_plan():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="List all tickets",
        operations=(
            OperationStep(
                id="list_tickets",
                domain="tickets",
                action="list",
                risk="read",
                needs_confirmation=False,
            ),
            OperationStep(
                id="show_ticket",
                domain="tickets",
                action="show",
                parameters={"ticket_id": 1},
                risk="read",
                needs_confirmation=False,
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is True
    assert len(result.errors) == 0


def test_validate_invalid_domain():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Test invalid domain",
        operations=(
            OperationStep(
                id="bad_domain",
                domain="nonexistent",
                action="list",
                risk="read",
                needs_confirmation=False,
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is False
    assert any("No command found" in err.message for err in result.errors)


def test_validate_invalid_action():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Test invalid action",
        operations=(
            OperationStep(
                id="bad_action",
                domain="tickets",
                action="nonexistent_action",
                risk="read",
                needs_confirmation=False,
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is False
    assert any("No command found" in err.message for err in result.errors)


def test_validate_unknown_risk():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Test unclassified risk",
        operations=(
            OperationStep(
                id="unclassified",
                domain="tickets",
                action="list",
                risk="unknown",
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is False
    assert any("Risk level must be classified" in err.message for err in result.errors)


def test_validate_destructive_operation_rejected():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Test destructive",
        operations=(
            OperationStep(
                id="delete_mockup",
                domain="mockups",
                action="delete",
                parameters={"mockup_id": "abc-123"},
                risk="destructive",
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is False
    assert any("Destructive operations require" in err.message for err in result.errors)


def test_validate_singular_domain_normalized():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="List all tickets using singular domain name",
        operations=(
            OperationStep(
                id="list_tickets",
                domain="ticket",
                action="list",
                risk="read",
                needs_confirmation=False,
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is True


def test_validate_broken_reference():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Test broken reference",
        operations=(
            OperationStep(
                id="list_tickets",
                domain="tickets",
                action="list",
                parameters={"project_id": "${resolve_project.id}"},
                risk="read",
                needs_confirmation=False,
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is False
    assert any("does not match any operation id" in err.message for err in result.errors)


def test_validate_empty_operation_id():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Test empty id",
        operations=(
            OperationStep(
                id="",
                domain="tickets",
                action="list",
                risk="read",
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is False
    assert any("Operation id is empty" in err.message for err in result.errors)


def test_validate_agent_mismatch():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Create a ticket with wrong agent",
        operations=(
            OperationStep(
                id="create_ticket",
                domain="tickets",
                action="create",
                parameters={"subject": "Test", "description": "Test"},
                risk="write",
            ),
        ),
    )
    result = validate_operation_plan(plan, schema, calling_agent="oracle")
    assert result.valid is False
    assert any("expects agent" in err.message for err in result.errors)


def test_validate_agent_match_passes():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Create a ticket with correct agent",
        operations=(
            OperationStep(
                id="create_ticket",
                domain="tickets",
                action="create",
                parameters={"subject": "Test", "description": "Test"},
                risk="write",
            ),
        ),
    )
    result = validate_operation_plan(plan, schema, calling_agent="surgeon")
    assert result.valid is True


def test_validate_missing_required_parameter():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Create ticket without subject",
        operations=(
            OperationStep(
                id="create_ticket",
                domain="tickets",
                action="create",
                parameters={"description": "Something"},
                risk="write",
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is False
    assert any("subject" in err.field for err in result.errors)
    assert any("missing" in err.message for err in result.errors)


def test_validate_invalid_enum_choice():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="Update ticket with invalid status",
        operations=(
            OperationStep(
                id="update_ticket",
                domain="tickets",
                action="update",
                parameters={"ticket_id": 1, "status": "banana"},
                risk="write",
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is False
    status_errors = [e for e in result.errors if "valid choice" in e.message]
    assert len(status_errors) > 0


def test_validation_result_to_dict():
    result = ValidationError(
        step_id="step1",
        field="domain",
        message="Domain not found",
    )
    data = result.__dict__  # dataclass asdict
    assert data["step_id"] == "step1"
    assert data["field"] == "domain"


def test_validate_plan_with_reference_resolution():
    schema = build_cli_schema(main)
    plan = OperationPlan(
        intent="List tickets for a resolved project",
        operations=(
            OperationStep(
                id="resolve_project",
                domain="projects",
                action="list",
                risk="read",
                needs_confirmation=False,
            ),
            OperationStep(
                id="list_tickets",
                domain="tickets",
                action="list",
                parameters={"project_id": "${resolve_project.id}"},
                risk="read",
                needs_confirmation=False,
            ),
        ),
    )
    result = validate_operation_plan(plan, schema)
    assert result.valid is True
