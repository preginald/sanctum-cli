"""Tests for sanctum_cli.assist.events — sanitized telemetry store."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from sanctum_cli.assist.events import (
    RecoveryEvent,
    _get_cli_version,
    get_pattern_stats,
    query_events,
    record_correction_feedback,
    record_event,
    redact_command,
    set_events_dir,
)


def _make_event(
    event_id: str | None = None,
    pattern: str = "test_pattern",
    **overrides: object,
) -> RecoveryEvent:
    return RecoveryEvent(
        event_id=event_id or uuid.uuid4().hex,
        pattern=pattern,
        error_class=str(overrides.get("error_class", "test_error")),
        inferred_intent=str(overrides.get("inferred_intent", "test intent")),
        risk=str(overrides.get("risk", "read")),
        confidence=float(overrides.get("confidence", 0.9)),
        generated_command=str(overrides.get("generated_command", "sanctum --agent test list")),
        status=str(overrides.get("status", "assist_suggestion")),
        calling_agent=str(overrides.get("calling_agent", "test_agent")),
        domain=str(overrides.get("domain", "test")),
        action=str(overrides.get("action", "list")),
        failed_command_redacted=overrides.get("failed_command_redacted"),
        corrected_operation=overrides.get("corrected_operation"),
        accepted=overrides.get("accepted"),
        match_type=str(overrides.get("match_type", "deterministic")),
        cli_version=str(overrides.get("cli_version", _get_cli_version())),
        schema_digest=overrides.get("schema_digest"),
        execution_risk=overrides.get("execution_risk"),
    )


def test_redact_command_redacts_api_key():
    result = redact_command("sanctum --agent architect flow --api-key sk-1234 list")
    assert "sk-1234" not in result
    assert "--api-key ***" in result


def test_redact_command_redacts_jwt_in_output():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNqPndcyFdTZ3N3Rg"
    result = redact_command(f"sanctum --agent surgeon tickets show 1 response: {jwt}")
    assert jwt not in result
    assert "***.***.***" in result


def test_redact_command_redacts_env_token():
    result = redact_command("SANCTUM_TOKEN_SURGEON=sntm_secret sanctum tickets list")
    assert "sntm_secret" not in result
    assert "SANCTUM_TOKEN_SURGEON=***" in result


def test_redact_command_keeps_agent_and_user():
    result = redact_command("sanctum --agent surgeon --user peter@test.com tickets list")
    assert "--agent" in result
    assert "surgeon" in result
    assert "--user" in result
    assert "peter@test.com" in result


def test_redact_command_none():
    assert redact_command(None) is None


def test_redact_command_empty():
    assert redact_command("") == ""


def test_recovery_event_default_fields():
    eid = uuid.uuid4().hex
    ev = _make_event(event_id=eid)
    assert ev.event_id == eid
    assert ev.accepted is None
    assert ev.match_type == "deterministic"
    assert ev.failed_command_redacted is None


def test_recovery_event_to_dict_roundtrip():
    ev = _make_event(
        failed_command_redacted="sanctum tickets list",
        corrected_operation="sanctum --agent test tickets list",
        accepted=True,
        match_type="router",
        schema_digest="abc123",
        execution_risk="read",
    )
    d = ev.to_dict()
    restored = RecoveryEvent.from_dict(d)
    assert restored.event_id == ev.event_id
    assert restored.accepted is True
    assert restored.match_type == "router"
    assert restored.schema_digest == "abc123"
    assert restored.execution_risk == "read"
    assert restored.failed_command_redacted == "sanctum tickets list"


def test_recovery_event_from_dict_missing_fields():
    data = {
        "event_id": "e1",
        "pattern": "p1",
        "error_class": "err",
        "inferred_intent": "intent",
        "risk": "read",
        "confidence": 0.9,
        "generated_command": "cmd",
        "status": "assist_suggestion",
        "calling_agent": "test",
        "domain": "test",
        "action": "list",
    }
    ev = RecoveryEvent.from_dict(data)
    assert ev.accepted is None
    assert ev.match_type == "deterministic"
    assert ev.failed_command_redacted is None
    assert ev.cli_version == "dev"
    assert ev.schema_digest is None


def test_record_and_query_events(temp_home):
    set_events_dir(temp_home / "events")
    ev = _make_event()
    record_event(ev)
    results = query_events(period_days=30)
    assert len(results) == 1
    assert results[0].event_id == ev.event_id
    assert results[0].accepted is None


def test_record_and_query_events_with_filters(temp_home):
    set_events_dir(temp_home / "events")
    ev1 = _make_event(pattern="pat_a", domain="tickets")
    ev2 = _make_event(event_id=uuid.uuid4().hex, pattern="pat_b", domain="articles")
    record_event(ev1)
    record_event(ev2)
    results = query_events(period_days=30, domain="tickets")
    assert len(results) == 1
    assert results[0].pattern == "pat_a"


def test_record_correction_feedback_updates_accepted(temp_home):
    set_events_dir(temp_home / "events")
    ev = _make_event(accepted=None)
    record_event(ev)
    record_correction_feedback(ev.event_id, accepted=True, execution_risk="read")
    results = query_events(period_days=30)
    assert len(results) == 1
    assert results[0].accepted is True
    assert results[0].execution_risk == "read"


def test_record_correction_feedback_rejected(temp_home):
    set_events_dir(temp_home / "events")
    ev = _make_event(accepted=None)
    record_event(ev)
    record_correction_feedback(ev.event_id, accepted=False)
    results = query_events(period_days=30)
    assert results[0].accepted is False


def test_get_pattern_stats_includes_acceptance(temp_home):
    set_events_dir(temp_home / "events")
    ev1 = _make_event(event_id=uuid.uuid4().hex, pattern="pat_a", accepted=True)
    ev2 = _make_event(event_id=uuid.uuid4().hex, pattern="pat_a", accepted=False)
    ev3 = _make_event(event_id=uuid.uuid4().hex, pattern="pat_a", accepted=True)
    for ev in (ev1, ev2, ev3):
        record_event(ev)
    stats = get_pattern_stats(period_days=30)
    assert stats["total_events"] == 3
    acc = stats["acceptance"]
    assert acc["accepted"] == 2
    assert acc["rejected"] == 1


def test_get_pattern_stats_empty(temp_home):
    set_events_dir(temp_home / "events_no_data")
    Path(temp_home / "events_no_data").mkdir(exist_ok=True)
    stats = get_pattern_stats(period_days=30)
    assert stats["total_events"] == 0
    assert stats["acceptance"]["accepted"] == 0


def test_feedback_noop_for_unknown_event_id(temp_home):
    set_events_dir(temp_home / "events")
    record_correction_feedback("nonexistent", accepted=True)
    results = query_events(period_days=30)
    assert len(results) == 0


def test_jsonl_file_is_writable_and_readable(temp_home):
    set_events_dir(temp_home / "events")
    ev = _make_event()
    record_event(ev)
    event_file = list(Path(temp_home / "events").glob("*.jsonl"))[0]
    content = event_file.read_text()
    parsed = json.loads(content.strip())
    assert parsed["event_id"] == ev.event_id
    assert parsed["match_type"] == "deterministic"
    assert parsed["cli_version"] != ""


def test_pattern_effectiveness_includes_acceptance_rate(temp_home):
    set_events_dir(temp_home / "events")
    eid1 = uuid.uuid4().hex
    eid2 = uuid.uuid4().hex
    ev1 = _make_event(event_id=eid1, pattern="pat_a", accepted=True)
    ev2 = _make_event(event_id=eid2, pattern="pat_a", accepted=False)
    record_event(ev1)
    record_event(ev2)
    stats = get_pattern_stats(period_days=30)
    pat = stats["patterns"]["pat_a"]
    assert pat["acceptance_rate"] == 0.5
