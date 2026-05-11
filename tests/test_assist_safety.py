"""Tests for safety classifier, confirmation, and rejection rules."""

from sanctum_cli.assist.safety import (
    SafetyRisk,
    check_operation,
    classify_risk,
    execution_rule,
    is_rejected,
    needs_confirmation,
)


def test_classify_read_actions():
    assert classify_risk("tickets", "list") == SafetyRisk.READ
    assert classify_risk("tickets", "show") == SafetyRisk.READ
    assert classify_risk("articles", "show") == SafetyRisk.READ
    assert classify_risk("projects", "list") == SafetyRisk.READ
    assert classify_risk("search", "search") == SafetyRisk.READ
    assert classify_risk("monitor", "status") == SafetyRisk.READ


def test_classify_write_actions():
    assert classify_risk("tickets", "create") == SafetyRisk.WRITE
    assert classify_risk("articles", "update") == SafetyRisk.WRITE
    assert classify_risk("time-entries", "create") == SafetyRisk.WRITE
    assert classify_risk("mockups", "update") == SafetyRisk.WRITE
    assert classify_risk("tickets", "resolve") == SafetyRisk.WRITE
    assert classify_risk("tickets", "comment") == SafetyRisk.WRITE
    assert classify_risk("contacts", "set-password") == SafetyRisk.WRITE


def test_classify_external_effect_actions():
    assert classify_risk("invoices", "send") == SafetyRisk.EXTERNAL_EFFECT
    assert classify_risk("invoices", "send-receipt") == SafetyRisk.EXTERNAL_EFFECT
    assert classify_risk("notify", "send") == SafetyRisk.EXTERNAL_EFFECT
    assert classify_risk("articles", "publish") == SafetyRisk.EXTERNAL_EFFECT
    assert classify_risk("flow", "instance-action") == SafetyRisk.EXTERNAL_EFFECT
    assert classify_risk("forms", "deploy") == SafetyRisk.EXTERNAL_EFFECT


def test_classify_destructive_actions():
    assert classify_risk("mockups", "delete") == SafetyRisk.DESTRUCTIVE
    assert classify_risk("any", "revoke") == SafetyRisk.DESTRUCTIVE
    assert classify_risk("any", "rotate") == SafetyRisk.DESTRUCTIVE


def test_classify_unknown_action():
    assert classify_risk("unknown", "foobar") == SafetyRisk.UNKNOWN


def test_needs_confirmation_read():
    assert needs_confirmation(SafetyRisk.READ) is False
    assert needs_confirmation("read") is False


def test_needs_confirmation_write():
    assert needs_confirmation(SafetyRisk.WRITE) is True
    assert needs_confirmation("write") is True


def test_needs_confirmation_write_non_interactive():
    assert needs_confirmation(SafetyRisk.WRITE, non_interactive_confirmed=True) is False


def test_needs_confirmation_external_effect():
    assert needs_confirmation(SafetyRisk.EXTERNAL_EFFECT) is True


def test_needs_confirmation_external_effect_non_interactive():
    assert needs_confirmation(SafetyRisk.EXTERNAL_EFFECT, non_interactive_confirmed=True) is False


def test_needs_confirmation_destructive():
    assert needs_confirmation(SafetyRisk.DESTRUCTIVE) is True
    assert needs_confirmation(SafetyRisk.DESTRUCTIVE, non_interactive_confirmed=True) is True


def test_needs_confirmation_unknown():
    assert needs_confirmation(SafetyRisk.UNKNOWN) is True


def test_needs_confirmation_unknown_string():
    assert needs_confirmation("garbage_risk") is True


def test_is_rejected_destructive():
    assert is_rejected(SafetyRisk.DESTRUCTIVE) is True
    assert is_rejected("destructive") is True


def test_is_rejected_non_destructive():
    assert is_rejected(SafetyRisk.READ) is False
    assert is_rejected(SafetyRisk.WRITE) is False
    assert is_rejected(SafetyRisk.EXTERNAL_EFFECT) is False
    assert is_rejected(SafetyRisk.UNKNOWN) is False
    assert is_rejected("read") is False
    assert is_rejected("unknown_string") is False


def test_execution_rule_read():
    rule = execution_rule(SafetyRisk.READ)
    assert "may auto-execute" in rule.lower()


def test_execution_rule_write():
    rule = execution_rule(SafetyRisk.WRITE)
    assert "confirmation" in rule.lower()


def test_execution_rule_destructive():
    rule = execution_rule(SafetyRisk.DESTRUCTIVE)
    assert "refuse" in rule.lower()


def test_execution_rule_external_effect():
    rule = execution_rule(SafetyRisk.EXTERNAL_EFFECT)
    assert "expected outcome" in rule.lower()


def test_execution_rule_unknown():
    rule = execution_rule(SafetyRisk.UNKNOWN)
    assert "confirmation" in rule.lower()


def test_check_operation_read():
    result = check_operation("tickets", "show")
    assert result.domain == "tickets"
    assert result.action == "show"
    assert result.risk == "read"
    assert result.needs_confirmation is False
    assert result.rejected is False
    assert "auto-execute" in result.reason.lower()


def test_check_operation_destructive():
    result = check_operation("mockups", "delete")
    assert result.risk == "destructive"
    assert result.needs_confirmation is True
    assert result.rejected is True
    assert "refuse" in result.reason.lower()


def test_check_operation_write_non_interactive():
    result = check_operation("tickets", "create", non_interactive_confirmed=True)
    assert result.risk == "write"
    assert result.needs_confirmation is False
    assert result.rejected is False


def test_safety_check_to_dict():
    result = check_operation("tickets", "list")
    data = result.to_dict()
    assert data["domain"] == "tickets"
    assert data["action"] == "list"
    assert data["risk"] == "read"
    assert data["needs_confirmation"] is False
    assert data["rejected"] is False


def test_safety_risk_enum_values():
    assert SafetyRisk.READ.value == "read"
    assert SafetyRisk.WRITE.value == "write"
    assert SafetyRisk.EXTERNAL_EFFECT.value == "external_effect"
    assert SafetyRisk.DESTRUCTIVE.value == "destructive"
    assert SafetyRisk.UNKNOWN.value == "unknown"
