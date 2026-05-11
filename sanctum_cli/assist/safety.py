"""Safety classifier, confirmation requirements, and destructive-operation rules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class SafetyRisk(Enum):
    """Execution risk classification for assisted operations."""

    READ = "read"
    WRITE = "write"
    EXTERNAL_EFFECT = "external_effect"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"


RISK_EXECUTION_RULES: dict[SafetyRisk, str] = {
    SafetyRisk.READ: "May auto-execute in assist mode after validation.",
    SafetyRisk.WRITE: (
        "Requires explicit confirmation unless caller provides a trusted non-interactive "
        "confirmation flag."
    ),
    SafetyRisk.EXTERNAL_EFFECT: (
        "Requires explicit confirmation and expected outcome summary."
    ),
    SafetyRisk.DESTRUCTIVE: (
        "Refuse by default; requires explicit operator-level confirmation."
    ),
    SafetyRisk.UNKNOWN: "Requires confirmation before execution.",
}

READ_ACTIONS: set[str] = {"list", "show", "search", "health", "status", "lint"}
EXTERNAL_EFFECT_ACTIONS: set[str] = {
    "send",
    "send-receipt",
    "publish",
    "instance-action",
    "deploy",
}
DESTRUCTIVE_ACTIONS: set[str] = {"delete", "revoke", "rotate"}
WRITE_ACTIONS: set[str] = {
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


def classify_risk(domain: str, action: str) -> SafetyRisk:
    """Classify the safety risk of a CLI domain action."""
    if action in READ_ACTIONS:
        return SafetyRisk.READ
    if action in EXTERNAL_EFFECT_ACTIONS:
        return SafetyRisk.EXTERNAL_EFFECT
    if action in DESTRUCTIVE_ACTIONS:
        return SafetyRisk.DESTRUCTIVE
    if action in WRITE_ACTIONS:
        return SafetyRisk.WRITE
    return SafetyRisk.UNKNOWN


def needs_confirmation(
    risk: SafetyRisk | str,
    *,
    non_interactive_confirmed: bool = False,
) -> bool:
    """Determine if an operation requires confirmation before execution.

    Args:
        risk: The classified risk level.
        non_interactive_confirmed: True when the caller has already provided a trusted
            non-interactive confirmation flag.

    Returns:
        True if confirmation is required.
    """
    if isinstance(risk, str):
        try:
            risk = SafetyRisk(risk)
        except ValueError:
            risk = SafetyRisk.UNKNOWN

    if risk == SafetyRisk.READ:
        return False
    if risk == SafetyRisk.DESTRUCTIVE:
        return True
    if risk == SafetyRisk.UNKNOWN:
        return True
    return not non_interactive_confirmed


def is_rejected(risk: SafetyRisk | str) -> bool:
    """Check if an operation should be refused entirely.

    Destructive operations are refused by default.
    """
    if isinstance(risk, str):
        try:
            risk = SafetyRisk(risk)
        except ValueError:
            return False
    return risk == SafetyRisk.DESTRUCTIVE


def execution_rule(risk: SafetyRisk | str) -> str:
    """Return the execution rule text for a given risk level."""
    if isinstance(risk, str):
        try:
            risk = SafetyRisk(risk)
        except ValueError:
            return RISK_EXECUTION_RULES[SafetyRisk.UNKNOWN]
    return RISK_EXECUTION_RULES.get(risk, RISK_EXECUTION_RULES[SafetyRisk.UNKNOWN])


@dataclass(frozen=True)
class SafetyCheck:
    """Outcome of a safety check for an operation."""

    domain: str
    action: str
    risk: str
    needs_confirmation: bool
    rejected: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_operation(
    domain: str,
    action: str,
    *,
    non_interactive_confirmed: bool = False,
) -> SafetyCheck:
    """Run a full safety check on a proposed operation."""
    risk = classify_risk(domain, action)
    return SafetyCheck(
        domain=domain,
        action=action,
        risk=risk.value,
        needs_confirmation=needs_confirmation(
            risk, non_interactive_confirmed=non_interactive_confirmed
        ),
        rejected=is_rejected(risk),
        reason=execution_rule(risk),
    )
