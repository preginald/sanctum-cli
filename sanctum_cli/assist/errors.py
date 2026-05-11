"""Deterministic CLI assist error explanation."""

from __future__ import annotations

import re
import shlex
from dataclasses import asdict, dataclass, field
from typing import Any

import click

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

    extra_argument = re.search(r"Got unexpected extra argument \((?P<argument>[^)]+)\)", output)
    if extra_argument:
        return ParsedCliError(
            error_class="unexpected_extra_argument",
            message=output,
            argument=extra_argument.group("argument"),
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


def explain_error(
    failed_command: str,
    error_output: str,
    *,
    root: click.Group | None = None,
) -> AssistExplanation:
    """Explain a failed Sanctum command using deterministic repair patterns."""

    tokens = _command_tokens(failed_command)
    parsed = parse_cli_error(error_output)
    explanation = (
        _explain_global_flag(tokens, parsed)
        or _explain_did_you_mean(tokens, parsed)
        or _explain_singular_group(tokens, parsed)
        or _explain_missing_option(parsed)
        or _explain_unexpected_extra_argument(tokens, parsed)
        or _explain_invalid_choice(parsed)
        or _unsupported(error_output)
    )
    if root is not None and explanation.generated_command:
        validation = _validate_command(root, explanation.generated_command)
        return AssistExplanation(**{**explanation.to_dict(), "validation": validation})
    return explanation


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


def _explain_invalid_choice(parsed: ParsedCliError) -> AssistExplanation | None:
    if parsed.error_class != "invalid_choice" or not parsed.option:
        return None
    choices = ", ".join(parsed.choices) if parsed.choices else "the listed choices"
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


def _format_command(tokens: list[str]) -> str:
    return "sanctum " + shlex.join(tokens)


def _validate_command(root: click.Group, command: str) -> str:
    tokens = _command_tokens(command)
    try:
        with root.make_context("sanctum", tokens, resilient_parsing=False):
            return "valid"
    except click.ClickException as exc:
        return f"invalid: {exc.format_message()}"
