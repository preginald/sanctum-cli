"""Typed operation plan models and validation for CLI assist."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from sanctum_cli.assist.schema import CliSchema, CommandSchema, ParameterSchema

RiskLevel = Literal["read", "write", "external_effect", "destructive", "unknown"]

READ_ACTIONS = {"list", "show", "search", "health", "status", "lint"}
EXTERNAL_EFFECT_ACTIONS = {"send", "send-receipt", "publish", "instance-action", "deploy"}
DESTRUCTIVE_ACTIONS = {"delete", "revoke", "rotate"}
WRITE_ACTIONS = {
    "create",
    "update",
    "resolve",
    "comment",
    "transition",
    "complete",
    "link",
    "unlink",
    "apply",
    "pin",
    "unpin",
    "pay",
    "enable-portal",
    "invite",
    "set-password",
    "provision-cms-sso",
    "capture",
    "execute",
    "definition-create",
    "definition-update",
    "definition-publish",
    "instance-create",
    "context-update",
    "update-step",
    "simulate",
    "share-token",
}


@dataclass(frozen=True)
class OperationStep:
    """A single validated operation within a plan."""

    id: str
    domain: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    risk: RiskLevel = "unknown"
    needs_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperationStep:
        return cls(
            id=str(data.get("id", "")),
            domain=str(data.get("domain", "")),
            action=str(data.get("action", "")),
            parameters=dict(data.get("parameters") or {}),
            risk=str(data.get("risk", "unknown")),
            needs_confirmation=bool(data.get("needs_confirmation", True)),
        )


@dataclass(frozen=True)
class OperationPlan:
    """Typed operation plan with ordered steps."""

    intent: str
    operations: tuple[OperationStep, ...]
    resolved_entities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "operations": [op.to_dict() for op in self.operations],
            "resolved_entities": self.resolved_entities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperationPlan:
        return cls(
            intent=str(data.get("intent", "")),
            operations=tuple(
                OperationStep.from_dict(step)
                for step in data.get("operations", [])
                if isinstance(step, dict)
            ),
            resolved_entities=dict(data.get("resolved_entities") or {}),
        )


@dataclass(frozen=True)
class ValidationError:
    """Describes a single validation failure in an operation plan."""

    step_id: str
    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.step_id}: {self.field} — {self.message}"


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of plan validation."""

    valid: bool
    errors: tuple[ValidationError, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [asdict(err) for err in self.errors],
        }


def classify_risk(domain: str, action: str) -> RiskLevel:
    """Classify an operation's risk level from its domain and action."""
    if action in READ_ACTIONS:
        return "read"
    if action in EXTERNAL_EFFECT_ACTIONS:
        return "external_effect"
    if action in DESTRUCTIVE_ACTIONS:
        return "destructive"
    if action in WRITE_ACTIONS:
        return "write"
    return "unknown"


_SINGULAR_TO_PLURAL: dict[str, str] = {
    "ticket": "tickets",
    "article": "articles",
    "project": "projects",
    "milestone": "milestones",
    "invoice": "invoices",
    "contact": "contacts",
    "product": "products",
    "template": "templates",
    "mockup": "mockups",
    "artefact": "artefacts",
    "time-entry": "time-entries",
    "rate-card": "rate-cards",
}


def _canonical_domain(name: str) -> str:
    """Normalize singular/plural domain names to the canonical plural form."""
    return _SINGULAR_TO_PLURAL.get(name, name)


def _find_command(schema: CliSchema, domain: str, action: str) -> CommandSchema | None:
    """Find a command in the schema by domain and action."""
    canonical = _canonical_domain(domain)
    candidates = [domain, canonical]
    for d in candidates:
        for cmd in schema.commands:
            if len(cmd.path) >= 2 and cmd.path[0] == d and cmd.path[1] == action:
                return cmd
    return None


def validate_operation_plan(
    plan: OperationPlan,
    schema: CliSchema,
    *,
    calling_agent: str | None = None,
) -> ValidationResult:
    """Validate an operation plan against the CLI command schema.

    Checks:
    - Domain exists in command registry.
    - Action exists for the domain.
    - Required parameters are present.
    - Parameter types match expected types.
    - Enum values are valid.
    - Calling agent identity is allowed.
    - Risk class is assigned.
    """
    errors: list[ValidationError] = []

    for step in plan.operations:
        _validate_step(step, schema, calling_agent, errors)

    for step in plan.operations:
        for key, value in step.parameters.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                ref_id = value[2:-1].split(".")[0]
                if ref_id not in {op.id for op in plan.operations}:
                    errors.append(
                        ValidationError(
                            step_id=step.id,
                            field=f"parameters.{key}",
                            message=f"Reference {value!r} does not match any operation id",
                        )
                    )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=tuple(errors),
    )


def _validate_step(
    step: OperationStep,
    schema: CliSchema,
    calling_agent: str | None,
    errors: list[ValidationError],
) -> None:
    if not step.id:
        errors.append(ValidationError(step_id=step.id, field="id", message="Operation id is empty"))
        return

    if step.risk == "unknown":
        errors.append(
            ValidationError(
                step_id=step.id,
                field="risk",
                message="Risk level must be classified before execution",
            )
        )

    if step.risk == "destructive":
        errors.append(
            ValidationError(
                step_id=step.id,
                field="risk",
                message="Destructive operations require operator-level confirmation",
            )
        )

    command = _find_command(schema, step.domain, step.action)
    if command is None:
        errors.append(
            ValidationError(
                step_id=step.id,
                field="domain/action",
                message=f"No command found for {step.domain}.{step.action} in the CLI schema",
            )
        )
        return

    if command.expected_agent and calling_agent and calling_agent != command.expected_agent:
        errors.append(
            ValidationError(
                step_id=step.id,
                field="agent",
                message=(
                    f"Command {step.domain}.{step.action} expects agent "
                    f"'{command.expected_agent}' but '{calling_agent}' was specified"
                ),
            )
        )

    _validate_parameters(step, command, errors)


def _validate_parameters(
    step: OperationStep,
    command: CommandSchema,
    errors: list[ValidationError],
) -> None:
    param_map: dict[str, ParameterSchema] = {}
    for param in command.parameters:
        for opt in param.opts:
            name = opt.lstrip("-").replace("-", "_")
            param_map[name] = param
        name = param.name.replace("-", "_")
        param_map[name] = param
    param_map[command.name] = param_map.get(
        command.name,
        ParameterSchema(
            name=command.name, kind="argument", required=False, type="text"
        ),
    )

    for param in command.parameters:
        if param.required:
            found = False
            for opt in param.opts:
                name = opt.lstrip("-").replace("-", "_")
                if name in step.parameters:
                    found = True
                    break
            if param.name and param.name in step.parameters:
                found = True
            if not found:
                errors.append(
                    ValidationError(
                        step_id=step.id,
                        field=f"parameters.{param.name or param.opts[0]}",
                        message=f"Required parameter '{param.name or param.opts[0]}' is missing",
                    )
                )

    for key, value in step.parameters.items():
        if key not in param_map:
            continue
        param = param_map[key]
        if param.choices and str(value) not in param.choices:
            errors.append(
                ValidationError(
                    step_id=step.id,
                    field=f"parameters.{key}",
                    message=(
                        f"Value '{value}' is not a valid choice for {key}; "
                        f"must be one of: {', '.join(param.choices)}"
                    ),
                )
            )
