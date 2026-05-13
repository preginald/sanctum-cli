"""Tests for the natural-language assist CLI command.

Phase 3: Verify Router-backed intent interpretation, plan validation,
safety classification, and output formatting.
"""

import base64
import json
import time

from click.testing import CliRunner

from sanctum_cli.cli import main
from sanctum_cli.domains.assist_ import assist


def _valid_jwt() -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"exp": int(time.time()) + 3600, "sub": "test"}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


def _assist_obj(agent: str = "oracle", output_json: bool = False) -> dict:
    return {
        "resolved_agent": agent,
        "output_json": output_json,
        "assist": False,
        "root_group": main,
    }


def test_assist_json_output_with_valid_read_plan(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.95,
            "match_type": "inferred",
            "inferred_intent": "List all tickets",
            "operation_plan": [
                {
                    "domain": "tickets",
                    "action": "list",
                    "parameters": {},
                    "risk": "read",
                }
            ],
            "needs_confirmation": False,
            "message": "This is a read-only query.",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["find all tickets"],
        obj=_assist_obj(agent="oracle", output_json=True),
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "validated"
    assert data["intent"] == "find all tickets"
    assert data["inferred_intent"] == "List all tickets"
    assert data["confidence"] == 0.95
    assert data["needs_confirmation"] is False
    assert len(data["operations"]) == 1
    assert data["operations"][0]["domain"] == "tickets"
    assert data["operations"][0]["action"] == "list"
    assert data["operations"][0]["risk"] == "read"
    assert len(data["safety_checks"]) == 1


def test_assist_text_output_with_read_plan(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.92,
            "match_type": "inferred",
            "inferred_intent": "List milestones for Sanctum Router project",
            "operation_plan": [
                {
                    "domain": "milestones",
                    "action": "list",
                    "parameters": {"project_id": "abc-123"},
                    "risk": "read",
                }
            ],
            "needs_confirmation": False,
            "message": "Run this read-only operation to list milestones.",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["find milestones for Sanctum Router"],
        obj=_assist_obj(agent="oracle", output_json=False),
    )

    assert result.exit_code == 0
    assert "find milestones for Sanctum Router" in result.output
    assert "List milestones for Sanctum Router project" in result.output
    assert "92%" in result.output
    assert "milestones" in result.output
    assert "list" in result.output


def test_assist_requires_router_token(monkeypatch, temp_home):
    monkeypatch.delenv("SANCTUM_ROUTER_TOKEN", raising=False)
    monkeypatch.delenv("SANCTUM_ROUTER_JWT", raising=False)
    monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_ID", raising=False)
    monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OIDC_CLIENT_ID", raising=False)
    monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["find tickets"],
        obj=_assist_obj(agent="oracle", output_json=False),
    )

    assert result.exit_code == 1
    assert "SANCTUM_ROUTER_TOKEN" in result.output


def test_assist_json_router_token_missing(monkeypatch, temp_home):
    monkeypatch.delenv("SANCTUM_ROUTER_TOKEN", raising=False)
    monkeypatch.delenv("SANCTUM_ROUTER_JWT", raising=False)
    monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_ID", raising=False)
    monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OIDC_CLIENT_ID", raising=False)
    monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["find tickets"],
        obj=_assist_obj(agent="oracle", output_json=True),
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["status"] == "router_unavailable"


def test_assist_handles_router_http_error(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        status_code=500,
        json={"error": {"message": "Internal server error"}},
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["find tickets"],
        obj=_assist_obj(agent="oracle", output_json=False),
    )

    assert result.exit_code == 1
    assert "Router interpretation failed" in result.output


def test_assist_json_router_http_error(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        status_code=403,
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["find tickets"],
        obj=_assist_obj(agent="oracle", output_json=True),
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["status"] == "error"


def test_assist_shows_safety_notes_for_write_plan(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.88,
            "match_type": "inferred",
            "inferred_intent": "Create a ticket for the bug fix",
            "operation_plan": [
                {
                    "domain": "tickets",
                    "action": "create",
                    "parameters": {"subject": "Fix login bug", "description": "Details"},
                    "risk": "write",
                }
            ],
            "needs_confirmation": True,
            "message": "Write operation requires confirmation.",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["create a ticket for fixing the login bug"],
        obj=_assist_obj(agent="surgeon", output_json=False),
    )

    assert result.exit_code == 0
    assert "create a ticket" in result.output
    assert "CONFIRMATION REQUIRED" in result.output
    assert "tickets" in result.output
    assert "create" in result.output


def test_assist_json_safety_checks_for_write(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.85,
            "match_type": "inferred",
            "inferred_intent": "Send the invoice",
            "operation_plan": [
                {
                    "domain": "invoices",
                    "action": "send-receipt",
                    "parameters": {"invoice_id": "inv-001"},
                    "risk": "external_effect",
                }
            ],
            "needs_confirmation": True,
            "message": "External effect requires confirmation.",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["send invoice 001"],
        obj=_assist_obj(agent="oracle", output_json=True),
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "validation_failed"
    assert len(data["validation"]["errors"]) > 0
    assert any("to_email" in err["message"] for err in data["validation"]["errors"])
    assert data["needs_confirmation"] is True
    assert len(data["safety_checks"]) == 1
    assert data["safety_checks"][0]["risk"] == "external_effect"
    assert data["safety_checks"][0]["needs_confirmation"] is True


def test_assist_shows_validation_errors(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.70,
            "match_type": "inferred",
            "inferred_intent": "Call a nonexistent command",
            "operation_plan": [
                {
                    "domain": "nonexistent",
                    "action": "foo",
                    "parameters": {},
                    "risk": "read",
                }
            ],
            "needs_confirmation": False,
            "message": "Unknown domain.",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["do something with a nonexistent domain"],
        obj=_assist_obj(agent="oracle", output_json=False),
    )

    assert result.exit_code == 0
    assert "Validation Errors:" in result.output
    assert "No command found" in result.output


def test_assist_json_validation_errors(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.70,
            "match_type": "inferred",
            "inferred_intent": "Call a nonexistent command",
            "operation_plan": [
                {
                    "domain": "nonexistent",
                    "action": "foo",
                    "parameters": {},
                    "risk": "read",
                }
            ],
            "needs_confirmation": False,
            "message": "Unknown domain.",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["do something invalid"],
        obj=_assist_obj(agent="oracle", output_json=True),
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "validation_failed"
    assert len(data["validation"]["errors"]) > 0


def test_assist_empty_plan_shows_no_operations(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "unsupported",
            "confidence": 0.0,
            "match_type": "none",
            "inferred_intent": "Could not interpret the intent",
            "operation_plan": [],
            "needs_confirmation": False,
            "message": "Your request could not be parsed into CLI operations.",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["do something that makes no sense"],
        obj=_assist_obj(agent="oracle", output_json=True),
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "validated"
    assert len(data["operations"]) == 0
    assert len(data["safety_checks"]) == 0


def test_assist_env_token_not_set_uses_default_url(httpx_mock, monkeypatch, temp_home):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.99,
            "match_type": "exact",
            "inferred_intent": "Show ticket 123",
            "operation_plan": [
                {
                    "domain": "tickets",
                    "action": "show",
                    "parameters": {"ticket_id": 123},
                    "risk": "read",
                }
            ],
            "needs_confirmation": False,
            "message": "",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["show ticket 123"],
        obj=_assist_obj(agent="oracle", output_json=True),
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "validated"


def test_assist_multistep_read_plan_with_safety_classification(
    httpx_mock,
    monkeypatch,
    temp_home,
):
    monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", _valid_jwt())
    monkeypatch.setenv("SANCTUM_API_TOKEN", "sntm_test_token_12345")
    monkeypatch.setenv("SANCTUM_API_BASE", "http://localhost:8000")

    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.90,
            "match_type": "inferred",
            "inferred_intent": "Find open tickets and milestones for project X",
            "operation_plan": [
                {
                    "domain": "milestones",
                    "action": "list",
                    "parameters": {"project_id": "abc-123"},
                    "risk": "read",
                },
                {
                    "domain": "tickets",
                    "action": "list",
                    "parameters": {"project_id": "abc-123"},
                    "risk": "read",
                },
            ],
            "needs_confirmation": False,
            "message": "Multi-step read plan.",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        assist,
        ["find milestones and tickets for project X"],
        obj=_assist_obj(agent="oracle", output_json=True),
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "validated"
    assert len(data["operations"]) == 2
    assert len(data["safety_checks"]) == 2
    assert all(s["risk"] == "read" for s in data["safety_checks"])
    assert all(not s["needs_confirmation"] for s in data["safety_checks"])
    assert all(not s["rejected"] for s in data["safety_checks"])
