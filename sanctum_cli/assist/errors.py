"""Deterministic CLI assist error explanation."""

from __future__ import annotations

import re
import shlex
from dataclasses import asdict, dataclass, field
from typing import Any

import click

from sanctum_cli.assist.events import RecoveryEvent, record_event, redact_command
from sanctum_cli.assist.router_client import (
    RouterClient,
    RouterClientError,
    RouterInterpretResponse,
    RouterOperationPlanStep,
)
from sanctum_cli.assist.schema import build_cli_schema

GLOBAL_FLAGS = {
    "--json",
    "--debug",
    "--yes",
    "--agent",
    "-a",
    "--user",
    "-u",
    "--env",
    "-e",
    "--assist",
}
VALUE_FLAGS = {"--agent", "-a", "--user", "-u", "--env", "-e"}
READ_ACTIONS = {"list", "show", "search", "health", "status", "lint"}
DOMAIN_DEFAULT_AGENTS = {
    "articles": "scribe",
    "artefacts": "surgeon",
    "contacts": "surgeon",
    "flow": "architect",
    "forms": "surgeon",
    "invoices": "oracle",
    "milestones": "surgeon",
    "mockups": "surgeon",
    "notify": "scribe",
    "products": "oracle",
    "projects": "surgeon",
    "rate-cards": "oracle",
    "search": "oracle",
    "templates": "surgeon",
    "tickets": "surgeon",
    "time-entries": "surgeon",
    "workbench": "surgeon",
}
SINGULAR_GROUPS = {
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

OPTION_ALIASES: dict[tuple[str, str, str], str] = {
    ("tickets", "create", "--title"): "--subject",
}

ENUM_VALUE_ALIASES: dict[tuple[str, str, str], dict[str, str]] = {
    ("tickets", "create", "--priority"): {"medium": "normal", "moderate": "normal"},
    ("tickets", "update", "--priority"): {"medium": "normal", "moderate": "normal"},
}


@dataclass(frozen=True)
class AssistExplanation:
    """Structured response for an explained CLI failure."""

    status: str
    error_class: str
    inferred_intent: str
    generated_command: str | None
    risk: str
    confidence: float
    needs_confirmation: bool
    message: str
    validation: str = "not_validated"
    missing_fields: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParsedCliError:
    """Structured representation of a Click/API error line."""

    error_class: str
    message: str
    option: str | None = None
    suggestion: str | None = None
    command: str | None = None
    argument: str | None = None
    choices: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_cli_error(error_output: str) -> ParsedCliError:
    """Parse common Sanctum/Click error output into a stable structure."""

    output = error_output.strip()
    no_option = re.search(r"No such option: (?P<option>--?[\w-]+)", output)
    if no_option:
        did_you_mean = re.search(r"Did you mean ['\"](?P<option>--?[\w-]+)['\"]", output)
        return ParsedCliError(
            error_class="no_such_option",
            message=output,
            option=no_option.group("option"),
            suggestion=did_you_mean.group("option") if did_you_mean else None,
        )

    no_command = re.search(r"No such command ['\"](?P<command>[\w-]+)['\"]", output)
    if no_command:
        return ParsedCliError(
            error_class="no_such_command",
            message=output,
            command=no_command.group("command"),
        )

    missing_option = re.search(r"Missing option ['\"](?P<option>--?[\w-]+)['\"]", output)
    if missing_option:
        return ParsedCliError(
            error_class="missing_required_option",
            message=output,
            option=missing_option.group("option"),
        )

    option_requires_arg = re.search(
        r"Option ['\"](?P<option>--?[\w-]+)['\"] requires an argument", output
    )
    if option_requires_arg:
        return ParsedCliError(
            error_class="option_requires_argument",
            message=output,
            option=option_requires_arg.group("option"),
        )

    extra_argument = re.search(r"Got unexpected extra argument \((?P<argument>[^)]+)\)", output)
    if extra_argument:
        return ParsedCliError(
            error_class="unexpected_extra_argument",
            message=output,
            argument=extra_argument.group("argument"),
        )

    invalid_argument = re.search(
        r"Invalid value for ['\"](?P<argument>[A-Z_]+)['\"]: (?P<detail>.+)", output
    )
    if invalid_argument:
        return ParsedCliError(
            error_class="invalid_argument",
            message=output,
            argument=invalid_argument.group("argument").lower(),
        )

    invalid_choice = re.search(
        r"Invalid value for ['\"](?P<option>--?[\w-]+)['\"]: "
        r"['\"][^'\"]+['\"] is not one of (?P<choices>[^.]+)",
        output,
    )
    if invalid_choice:
        choices = tuple(re.findall(r"['\"]([^'\"]+)['\"]", invalid_choice.group("choices")))
        return ParsedCliError(
            error_class="invalid_choice",
            message=output,
            option=invalid_choice.group("option"),
            choices=choices,
        )

    return ParsedCliError(error_class="unknown", message=output)


def _derive_match_type(status: str) -> str:
    if status.startswith("router_"):
        return "router"
    if status == "assist_unsupported":
        return "unsupported"
    return "deterministic"


def _get_schema_digest(root: click.Group | None) -> str | None:
    if root is None:
        return None
    try:
        schema = build_cli_schema(root)
        return schema.digest
    except Exception:
        return None


def explain_error(
    failed_command: str,
    error_output: str,
    *,
    root: click.Group | None = None,
    calling_agent: str | None = None,
    router: RouterClient | None = None,
    schema_digest: str | None = None,
) -> AssistExplanation:
    """Explain a failed Sanctum command using deterministic repair patterns.

    When deterministic repair cannot produce a result the Router is consulted
    as a fallback for LLM-backed error interpretation.
    """

    tokens = _command_tokens(failed_command)
    parsed = parse_cli_error(error_output)
    explanation = (
        _explain_global_flag(tokens, parsed)
        or _explain_did_you_mean(tokens, parsed)
        or _explain_option_alias(tokens, parsed, root)
        or _explain_schema_unknown_flag(tokens, parsed, root)
        or _explain_singular_group(tokens, parsed)
        or _explain_missing_option(parsed)
        or _explain_missing_identity(tokens, error_output)
        or _explain_flow_api_key(tokens, error_output)
        or _explain_content_flag(tokens, parsed, error_output)
        or _explain_time_entry_positionals(tokens, parsed)
        or _explain_unexpected_extra_argument(tokens, parsed)
        or _explain_invalid_choice(parsed, tokens)
        or _explain_invalid_argument(parsed)
        or _explain_missing_template_sections(error_output)
        or _explain_billable_item_gate(failed_command, error_output)
        or _explain_minimum_increment(failed_command, error_output)
        or _explain_status_transition(failed_command, error_output)
        or _explain_api_422_generic(error_output)
        or _unsupported(error_output)
    )
    if explanation.status == "assist_unsupported" and router is not None and calling_agent:
        try:
            router_response = router.interpret_error(
                failed_command=failed_command,
                error_output=error_output,
                calling_agent=calling_agent,
                root=root,
            )
            explanation = _router_response_to_explanation(router_response, calling_agent)
        except RouterClientError:
            pass
    if root is not None and explanation.generated_command:
        validation = _validate_command(root, explanation.generated_command)
        result = AssistExplanation(**{**explanation.to_dict(), "validation": validation})
    else:
        result = explanation

    _record_recovery_event(
        result,
        calling_agent,
        tokens,
        failed_command_redacted=redact_command(failed_command) if failed_command else None,
        match_type=_derive_match_type(result.status),
        schema_digest=_get_schema_digest(root) if schema_digest is None else schema_digest,
        cli_version=_get_cli_version(),
    )
    return result


def render_explanation_text(explanation: AssistExplanation) -> str:
    """Render a human-readable assist response."""

    lines = [
        "Sanctum CLI Assist detected a malformed command.",
        "",
        f"Inferred intent: {explanation.inferred_intent}",
    ]
    if explanation.generated_command:
        lines.extend(["", "Corrected command:", explanation.generated_command])
    lines.extend(
        [
            "",
            f"Risk: {explanation.risk}",
            f"Confidence: {explanation.confidence:.2f}",
            f"Validation: {explanation.validation}",
            "",
            explanation.message,
        ]
    )
    return "\n".join(lines)


def _get_cli_version() -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version("sanctum-cli")
    except (ImportError, ModuleNotFoundError):
        return "dev"


def _record_recovery_event(
    explanation: AssistExplanation,
    calling_agent: str | None,
    tokens: list[str],
    *,
    failed_command_redacted: str | None = None,
    match_type: str = "deterministic",
    schema_digest: str | None = None,
    cli_version: str = "dev",
) -> None:
    import contextlib
    import uuid

    domain: str | None = None
    action: str | None = None
    for _i, token in enumerate(tokens):
        if token in ("--agent", "-a", "--user", "-u", "--env", "-e"):
            continue
        if token.startswith("-"):
            continue
        if domain is None:
            domain = token
        elif action is None:
            action = token
            break
    with contextlib.suppress(Exception):
        record_event(
            RecoveryEvent(
                event_id=uuid.uuid4().hex,
                pattern=explanation.error_class,
                error_class=explanation.error_class,
                inferred_intent=explanation.inferred_intent,
                risk=explanation.risk,
                confidence=explanation.confidence,
                generated_command=explanation.generated_command,
                status=explanation.status,
                calling_agent=calling_agent,
                domain=domain,
                action=action,
                failed_command_redacted=failed_command_redacted,
                corrected_operation=explanation.generated_command,
                accepted=None,
                match_type=match_type,
                cli_version=cli_version,
                schema_digest=schema_digest,
                execution_risk=explanation.risk,
            )
        )


def _command_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    if tokens and tokens[0].endswith("sanctum"):
        return tokens[1:]
    return tokens


def _explain_global_flag(tokens: list[str], parsed: ParsedCliError) -> AssistExplanation | None:
    flag = parsed.option
    if flag not in GLOBAL_FLAGS or flag not in tokens:
        return None

    corrected = _move_global_flag(tokens, flag)
    if corrected == tokens:
        return None

    command_path = _command_path(corrected)
    command_label = " ".join(command_path) or "the command"
    return AssistExplanation(
        status="assist_suggestion",
        error_class="misplaced_global_flag",
        inferred_intent=f"Run {command_label} with {flag} as a global flag.",
        generated_command=_format_command(corrected),
        risk="read" if flag == "--json" else "unknown",
        confidence=0.98,
        needs_confirmation=False,
        message=f"Move {flag} before the command group.",
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_option_alias(
    tokens: list[str], parsed: ParsedCliError, root: click.Group | None
) -> AssistExplanation | None:
    if not root:
        return None

    path = _command_path(tokens)
    if len(path) < 2:
        return None
    domain, action = path[0], path[1]

    corrected = list(tokens)
    made_changes = False

    for i, token in enumerate(corrected):
        if not token.startswith("--"):
            continue
        key = (domain, action, token)
        if key in OPTION_ALIASES:
            corrected[i] = OPTION_ALIASES[key]
            made_changes = True

    for i, token in enumerate(corrected):
        if not token.startswith("--"):
            continue
        enum_key = (domain, action, token)
        if enum_key in ENUM_VALUE_ALIASES and i + 1 < len(corrected):
            value = corrected[i + 1]
            aliases = ENUM_VALUE_ALIASES[enum_key]
            if value in aliases:
                corrected[i + 1] = str(aliases[value])
                made_changes = True

    if not made_changes:
        return None

    risk = "write"
    if len(path) >= 2:
        action_part = path[1]
        if action_part in READ_ACTIONS:
            risk = "read"

    return AssistExplanation(
        status="assist_suggestion",
        error_class="option_alias",
        inferred_intent=f"Run {domain} {action} with canonical option names.",
        generated_command=_format_command(corrected),
        risk=risk,
        confidence=0.95,
        needs_confirmation=False,
        message=f"Replaced known option aliases in {domain} {action}.",
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_schema_unknown_flag(
    tokens: list[str], parsed: ParsedCliError, root: click.Group | None
) -> AssistExplanation | None:
    if parsed.error_class != "no_such_option" or parsed.suggestion or not root:
        return None

    flag = parsed.option
    if not flag or flag in GLOBAL_FLAGS or flag not in tokens:
        return None

    flag_idx = tokens.index(flag)
    if flag_idx + 1 >= len(tokens):
        return None

    value = tokens[flag_idx + 1]
    if value.startswith("-"):
        return None

    path = _command_path(tokens)
    if len(path) < 2:
        return None

    domain, action = path[0], path[1]

    schema = build_cli_schema(root)
    target_cmd = None
    for cmd in schema.commands:
        if len(cmd.path) >= 2 and cmd.path[0] == domain and cmd.path[1] == action:
            target_cmd = cmd
            break

    if not target_cmd:
        return None

    for param in target_cmd.parameters:
        if value in param.choices:
            long_flag = param.opts[0] if param.opts else f"--{param.name}"
            corrected = list(tokens)
            corrected[flag_idx] = long_flag
            return AssistExplanation(
                status="assist_suggestion",
                error_class="schema_unknown_flag",
                inferred_intent=(
                    f"Replace {flag} with {long_flag} — "
                    f"the value {value!r} is a valid choice for {long_flag}."
                ),
                generated_command=_format_command(corrected),
                risk="unknown",
                confidence=0.92,
                needs_confirmation=False,
                message=(
                    f"Schema match: {flag} with value {value!r} matched parameter {long_flag}."
                ),
                details={
                    "parsed_error": parsed.to_dict(),
                    "schema_match": {
                        "command": f"{domain} {action}",
                        "unknown_flag": flag,
                        "value": value,
                        "matched_param": long_flag,
                    },
                },
            )

    return None


def _explain_did_you_mean(tokens: list[str], parsed: ParsedCliError) -> AssistExplanation | None:
    missing = parsed.option
    replacement = parsed.suggestion
    if not missing or not replacement or missing not in tokens:
        return None
    corrected = [replacement if token == missing else token for token in tokens]
    return AssistExplanation(
        status="assist_suggestion",
        error_class="did_you_mean_option",
        inferred_intent=f"Use {replacement} instead of {missing}.",
        generated_command=_format_command(corrected),
        risk="unknown",
        confidence=0.95,
        needs_confirmation=False,
        message=(
            f"Substitute Click's suggested option {replacement} and validate the command shape."
        ),
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_singular_group(tokens: list[str], parsed: ParsedCliError) -> AssistExplanation | None:
    if parsed.error_class != "no_such_command" or not parsed.command:
        return None
    singular = parsed.command
    plural = SINGULAR_GROUPS.get(singular)
    if not plural or singular not in tokens:
        return None
    corrected = [plural if token == singular else token for token in tokens]
    return AssistExplanation(
        status="assist_suggestion",
        error_class="singular_command_group",
        inferred_intent=f"Use the {plural} command group.",
        generated_command=_format_command(corrected),
        risk="unknown",
        confidence=0.96,
        needs_confirmation=False,
        message=f"Replace singular command group {singular!r} with {plural!r}.",
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_missing_option(parsed: ParsedCliError) -> AssistExplanation | None:
    if parsed.error_class != "missing_required_option" or not parsed.option:
        return None
    option = parsed.option
    return AssistExplanation(
        status="assist_missing_fields",
        error_class="missing_required_option",
        inferred_intent=f"Provide required option {option}.",
        generated_command=None,
        risk="unknown",
        confidence=0.9,
        needs_confirmation=True,
        message=f"The command is missing {option}; provide the value before retrying.",
        missing_fields=(option,),
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_missing_identity(tokens: list[str], error_output: str) -> AssistExplanation | None:
    if "--agent <name> or --user <email> is required" not in error_output:
        return None
    if any(token in {"--agent", "-a", "--user", "-u"} for token in tokens):
        return None

    command_path = _command_path(tokens)
    domain = command_path[0] if command_path else None
    agent = DOMAIN_DEFAULT_AGENTS.get(domain or "")
    if not agent:
        return AssistExplanation(
            status="assist_missing_fields",
            error_class="missing_identity",
            inferred_intent="Provide an agent or user identity before running the command.",
            generated_command=None,
            risk="unknown",
            confidence=0.9,
            needs_confirmation=True,
            message="Sanctum commands require --agent <name> or --user <email>.",
            missing_fields=("--agent",),
        )

    corrected = ["--agent", agent, *tokens]
    command_label = " ".join(command_path) or "the command"
    return AssistExplanation(
        status="assist_suggestion",
        error_class="missing_identity",
        inferred_intent=f"Run {command_label} using the default {agent} identity for {domain}.",
        generated_command=_format_command(corrected),
        risk=_risk_for_path(command_path),
        confidence=0.92,
        needs_confirmation=False,
        message=f"Add --agent {agent} before the command group.",
        details={"domain": domain, "agent": agent},
    )


def _explain_flow_api_key(tokens: list[str], error_output: str) -> AssistExplanation | None:
    command_path = _command_path(tokens)
    if not command_path or command_path[0] != "flow":
        return None
    normalized = error_output.lower()
    if not any(term in normalized for term in ("api key", "x-api-key", "audience", "unauthorized")):
        return None
    return AssistExplanation(
        status="assist_missing_fields",
        error_class="missing_flow_api_key",
        inferred_intent=(
            "Authenticate the Flow command with a Flow API key, not a Core bearer token."
        ),
        generated_command=None,
        risk=_risk_for_path(command_path),
        confidence=0.93,
        needs_confirmation=True,
        message=(
            "Provide --api-key or set SANCTUM_FLOW_API_KEY/FLOW_API_KEY. Do not paste or log "
            "the key in assist output."
        ),
        missing_fields=("--api-key",),
    )


def _explain_content_flag(
    tokens: list[str], parsed: ParsedCliError, error_output: str
) -> AssistExplanation | None:
    if parsed.option != "--content" or "requires an argument" not in error_output.lower():
        return None
    command_path = _command_path(tokens)
    return AssistExplanation(
        status="assist_missing_fields",
        error_class="content_flag_missing_value",
        inferred_intent=(
            "Provide content text for --content or use the file option where supported."
        ),
        generated_command=None,
        risk=_risk_for_path(command_path),
        confidence=0.88,
        needs_confirmation=True,
        message=(
            "--content requires a value on write commands such as artefacts/mockups. For articles, "
            "prefer --file when creating or updating body content."
        ),
        missing_fields=("--content",),
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_time_entry_positionals(
    tokens: list[str], parsed: ParsedCliError
) -> AssistExplanation | None:
    if parsed.error_class != "unexpected_extra_argument":
        return None
    command_path = _command_path(tokens)
    if command_path != ["time-entries", "create"]:
        return None

    start = _first_non_option_index_after_path(tokens, command_path)
    if start is None:
        return None
    positional_values = [token for token in tokens[start:] if not token.startswith("-")]
    if len(positional_values) < 3:
        return None

    corrected = tokens[:start] + [
        "--ticket-id",
        positional_values[0],
        "--start",
        positional_values[1],
        "--end",
        positional_values[2],
    ]
    if len(positional_values) > 3:
        corrected.extend(["--description", " ".join(positional_values[3:])])

    return AssistExplanation(
        status="assist_suggestion",
        error_class="positional_values_for_options",
        inferred_intent="Create a time entry using option flags instead of positional values.",
        generated_command=_format_command(corrected),
        risk="write",
        confidence=0.86,
        needs_confirmation=True,
        message=(
            "Map positional time-entry values to --ticket-id, --start, --end, and --description."
        ),
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_unexpected_extra_argument(
    tokens: list[str], parsed: ParsedCliError
) -> AssistExplanation | None:
    if parsed.error_class != "unexpected_extra_argument" or not parsed.argument:
        return None
    corrected = tokens[:]
    if parsed.argument in corrected:
        corrected.remove(parsed.argument)
    return AssistExplanation(
        status="assist_confirmation_required",
        error_class="unexpected_extra_argument",
        inferred_intent=f"Run the command without unexpected argument {parsed.argument!r}.",
        generated_command=_format_command(corrected) if corrected != tokens else None,
        risk="unknown",
        confidence=0.72,
        needs_confirmation=True,
        message=(
            f"Click rejected extra argument {parsed.argument!r}; confirm whether it should be "
            "removed or supplied through an option."
        ),
        details={"parsed_error": parsed.to_dict()},
    )


def _closest_choice(value: str, choices: tuple[str, ...]) -> str | None:
    value_lower = value.lower()
    for c in choices:
        if c.lower() == value_lower:
            return c
    for c in choices:
        if c.lower().startswith(value_lower) or value_lower.startswith(c.lower()):
            return c
    for c in choices:
        if len(set(value_lower) & set(c.lower())) / max(len(value_lower), len(c.lower()), 1) > 0.6:
            return c
    return None


def _explain_invalid_choice(
    parsed: ParsedCliError, tokens: list[str] | None = None
) -> AssistExplanation | None:
    if parsed.error_class != "invalid_choice" or not parsed.option:
        return None
    choices = ", ".join(parsed.choices) if parsed.choices else "the listed choices"
    generated: str | None = None
    suggestion: str | None = None
    if parsed.choices and tokens and parsed.option in tokens:
        idx = tokens.index(parsed.option)
        if idx + 1 < len(tokens):
            bad_value = tokens[idx + 1]
            closest = _closest_choice(bad_value, parsed.choices)
            if closest:
                suggestion = closest
                corrected = tokens[:]
                corrected[idx + 1] = closest
                generated = _format_command(corrected)
    if generated:
        return AssistExplanation(
            status="assist_suggestion",
            error_class="invalid_choice",
            inferred_intent=f"Replace invalid value with closest valid choice '{suggestion}'.",
            generated_command=generated,
            risk="unknown",
            confidence=0.88,
            needs_confirmation=True,
            message=f"{parsed.option} must be one of: {choices}. Closest match: {suggestion}.",
            details={"parsed_error": parsed.to_dict()},
        )
    return AssistExplanation(
        status="assist_missing_fields",
        error_class="invalid_choice",
        inferred_intent=f"Choose a valid value for {parsed.option}.",
        generated_command=None,
        risk="unknown",
        confidence=0.9,
        needs_confirmation=True,
        message=f"{parsed.option} must be one of: {choices}.",
        missing_fields=(parsed.option,),
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_invalid_argument(parsed: ParsedCliError) -> AssistExplanation | None:
    if parsed.error_class != "invalid_argument" or not parsed.argument:
        return None
    return AssistExplanation(
        status="assist_missing_fields",
        error_class="invalid_identifier",
        inferred_intent=f"Provide a valid value for {parsed.argument}.",
        generated_command=None,
        risk="unknown",
        confidence=0.87,
        needs_confirmation=True,
        message=(
            f"{parsed.argument} has the wrong shape or type. Use the numeric ID/UUID expected by "
            "the command, or resolve the entity by name first where supported."
        ),
        missing_fields=(parsed.argument,),
        details={"parsed_error": parsed.to_dict()},
    )


def _explain_missing_template_sections(error_output: str) -> AssistExplanation | None:
    if (
        "missing_sections" not in error_output
        and "missing required sections" not in error_output.lower()
        and "missing section" not in error_output.lower()
    ):
        return None

    sections = _extract_missing_sections(error_output)
    if sections:
        section_list = "\n".join(f"    - {s}" for s in sections)
        return AssistExplanation(
            status="assist_suggestion",
            error_class="missing_template_sections",
            inferred_intent=f"Add {len(sections)} missing template section(s) to the ticket.",
            generated_command=None,
            risk="write",
            confidence=0.92,
            needs_confirmation=True,
            message=(
                f"The ticket template requires {len(sections)} missing section(s):\n"
                f"{section_list}\n\n"
                "Append the missing headers to the --description value and retry."
            ),
        )

    return AssistExplanation(
        status="assist_suggestion",
        error_class="missing_template_sections",
        inferred_intent="Add missing template sections to the ticket description.",
        generated_command=None,
        risk="write",
        confidence=0.92,
        needs_confirmation=True,
        message="The ticket template requires additional sections. Append the missing headers "
        "to the --description value and retry.",
    )


def _extract_missing_sections(error_output: str) -> list[str]:
    """Extract all missing section names from a template validation error output."""
    _found: set[str] = set()
    patterns = [
        r"Missing required section:\s*(.+)",
        r"missing section:\s*(.+)",
        r"section ['\"](.+?)['\"] (?:is required|not found|missing)",
        r"'msg':\s*'Missing(?: required)? section:\s*(.+?)'",
        r"'msg':\s*'missing section:\s*(.+?)'",
        r"\"msg\":\s*\"Missing(?: required)? section:\s*(.+?)\"",
        r"\"msg\":\s*\"missing section:\s*(.+?)\"",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, error_output, re.IGNORECASE):
            section_name = match.group(1).strip().strip("'\"")
            if section_name:
                _found.add(section_name)

    return sorted(_found)


def _explain_billable_item_gate(failed_command: str, error_output: str) -> AssistExplanation | None:
    if "billable_item_required" not in error_output and "billable" not in error_output.lower():
        return None
    tokens = _command_tokens(failed_command)
    ticket_id: str | None = None
    for i, token in enumerate(tokens):
        if token in ("--ticket-id", "-t") and i + 1 < len(tokens):
            ticket_id = tokens[i + 1]
            break
        if token.isdigit():
            ticket_id = token
    if not ticket_id:
        return AssistExplanation(
            status="assist_missing_fields",
            error_class="billable_item_gate",
            inferred_intent="Add a time entry to satisfy the billable item requirement.",
            generated_command=None,
            risk="write",
            confidence=0.9,
            needs_confirmation=True,
            message="This ticket requires a time entry or material before resolution. "
            "Use 'sanctum time-entries create -t <id> -s <start> -e <end> -d \"<description>\"'.",
        )
    return AssistExplanation(
        status="assist_suggestion",
        error_class="billable_item_gate",
        inferred_intent=f"Create a 15-minute time entry on ticket {ticket_id} to pass the gate.",
        generated_command=(
            f"sanctum time-entries create -t {ticket_id} "
            "-s $(date -u +%Y-%m-%dT%H:%M:%S) "
            "-e $(date -u -d '+15 minutes' +%Y-%m-%dT%H:%M:%S) "
            '-d "Auto-created time entry for billable item gate"'
        ),
        risk="write",
        confidence=0.93,
        needs_confirmation=True,
        message=f"Ticket #{ticket_id} needs a time entry or material before resolution.",
    )


def _explain_minimum_increment(failed_command: str, error_output: str) -> AssistExplanation | None:
    if "minimum_increment" not in error_output and "minimum" not in error_output.lower():
        return None
    tokens = _command_tokens(failed_command)
    end_val: str | None = None
    for i, token in enumerate(tokens):
        if token in ("--end", "-e") and i + 1 < len(tokens):
            end_val = tokens[i + 1]
            break
    if end_val:
        import datetime

        try:
            dt = datetime.datetime.fromisoformat(end_val)
            dt += datetime.timedelta(minutes=15)
            corrected = tokens[:]
            for i, token in enumerate(tokens):
                if token in ("--end", "-e") and i + 1 < len(tokens):
                    corrected[i + 1] = dt.isoformat()
                    break
            return AssistExplanation(
                status="assist_suggestion",
                error_class="minimum_increment",
                inferred_intent="Extend the time entry to meet the minimum 15-minute increment.",
                generated_command=_format_command(corrected),
                risk="write",
                confidence=0.9,
                needs_confirmation=True,
                message=f"Time entry min 15 minutes. Extended end to {dt.isoformat()}.",
            )
        except (ValueError, TypeError):
            pass
    return AssistExplanation(
        status="assist_missing_fields",
        error_class="minimum_increment",
        inferred_intent="Adjust time entry duration to meet the minimum increment.",
        generated_command=None,
        risk="write",
        confidence=0.85,
        needs_confirmation=True,
        message="Time entries require a minimum 15-minute duration. Extend the --end time.",
    )


def _explain_status_transition(failed_command: str, error_output: str) -> AssistExplanation | None:
    if (
        "invalid transition" not in error_output.lower()
        and "cannot transition" not in error_output.lower()
    ):
        return None
    return AssistExplanation(
        status="assist_missing_fields",
        error_class="invalid_status_transition",
        inferred_intent="Use a valid status transition path.",
        generated_command=None,
        risk="write",
        confidence=0.87,
        needs_confirmation=True,
        message="The requested status transition is not allowed. Check available_transitions "
        "on the ticket, milestone, or project and use a valid intermediate status.",
    )


def _explain_api_422_generic(error_output: str) -> AssistExplanation | None:
    if "422" not in error_output and "unprocessable" not in error_output.lower():
        return None
    return AssistExplanation(
        status="assist_missing_fields",
        error_class="api_422_error",
        inferred_intent="Fix the validation error in the API request.",
        generated_command=None,
        risk="write",
        confidence=0.7,
        needs_confirmation=True,
        message=f"API validation error: {error_output.strip()[:200]}. "
        "Check required fields and value types before retrying.",
    )


def _unsupported(error_output: str) -> AssistExplanation:
    return AssistExplanation(
        status="assist_unsupported",
        error_class="unsupported_error",
        inferred_intent="Unable to infer a safe correction.",
        generated_command=None,
        risk="unknown",
        confidence=0.0,
        needs_confirmation=True,
        message=error_output.strip() or "No error output was supplied.",
    )


def _move_global_flag(tokens: list[str], flag: str) -> list[str]:
    remaining = tokens[:]
    value: str | None = None
    index = remaining.index(flag)
    remaining.pop(index)
    if flag in VALUE_FLAGS and index < len(remaining):
        value = remaining.pop(index)

    insertion = 0
    while insertion < len(remaining):
        token = remaining[insertion]
        if token in VALUE_FLAGS and insertion + 1 < len(remaining):
            insertion += 2
            continue
        if token in GLOBAL_FLAGS:
            insertion += 1
            continue
        break

    corrected = remaining[:insertion] + [flag] + remaining[insertion:]
    if value is not None:
        corrected.insert(insertion + 1, value)
    return corrected


def _command_path(tokens: list[str]) -> list[str]:
    path: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in VALUE_FLAGS:
            index += 2
            continue
        if token in GLOBAL_FLAGS:
            index += 1
            continue
        if token.startswith("-"):
            break
        path.append(token)
        if len(path) == 2:
            break
        index += 1
    return path


def _first_non_option_index_after_path(tokens: list[str], path: list[str]) -> int | None:
    path_index = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in VALUE_FLAGS:
            index += 2
            continue
        if token in GLOBAL_FLAGS:
            index += 1
            continue
        if path_index < len(path) and token == path[path_index]:
            path_index += 1
            index += 1
            if path_index == len(path):
                return index
            continue
        index += 1
    return None


def _risk_for_path(path: list[str]) -> str:
    if not path:
        return "unknown"
    action = path[1] if len(path) > 1 else path[0]
    if action in READ_ACTIONS:
        return "read"
    if action in {"send", "send-receipt", "publish", "instance-action"}:
        return "external_effect"
    if action in {"delete", "revoke", "rotate"}:
        return "destructive"
    return "write"


def _format_command(tokens: list[str]) -> str:
    return "sanctum " + shlex.join(tokens)


def _router_response_to_explanation(
    response: RouterInterpretResponse,
    calling_agent: str,
) -> AssistExplanation:
    """Convert a Router interpretation response into an AssistExplanation."""
    generated: str | None = None
    risk: str = response.operation_plan[0].risk if response.operation_plan else "unknown"

    if response.operation_plan:
        step = response.operation_plan[0]
        tokens = _operation_step_to_tokens(step, calling_agent)
        generated = _format_command(tokens) if tokens else None

    return AssistExplanation(
        status=f"router_{response.status}",
        error_class=f"router_{response.match_type}",
        inferred_intent=response.inferred_intent,
        generated_command=generated,
        risk=risk,
        confidence=response.confidence,
        needs_confirmation=response.needs_confirmation,
        message=response.message,
        details={"router_response": response.to_dict()},
    )


def _operation_step_to_tokens(
    step: RouterOperationPlanStep,
    calling_agent: str,
) -> list[str]:
    """Convert a Router operation plan step to CLI command tokens."""
    tokens: list[str] = ["--agent", calling_agent, step.domain, step.action]
    for key, value in step.parameters.items():
        flag = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                tokens.append(flag)
        else:
            tokens.extend([flag, str(value)])
    return tokens


def _validate_command(root: click.Group, command: str) -> str:
    tokens = _command_tokens(command)
    try:
        with root.make_context("sanctum", tokens, resilient_parsing=False):
            return "valid"
    except click.ClickException as exc:
        return f"invalid: {exc.format_message()}"
