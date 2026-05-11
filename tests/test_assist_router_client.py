"""Tests for Router-backed CLI assist interpretation."""

import pytest

from sanctum_cli.assist.router_client import (
    RouterClient,
    RouterClientError,
    build_router_interpret_request,
)
from sanctum_cli.cli import main


def test_build_router_interpret_request_includes_schema_context():
    request = build_router_interpret_request(
        mode="error_repair",
        failed_command="sanctum --agent surgeon tickets show --json 3293",
        error_output="Error: No such option: --json",
        calling_agent="surgeon",
        root=main,
        cwd="/tmp/work",
        sanitized_context={"task_hint": "deliver ticket 3293"},
    )

    payload = request.to_dict()
    assert payload["mode"] == "error_repair"
    assert payload["calling_agent"] == "surgeon"
    assert payload["cwd"] == "/tmp/work"
    assert "tickets" in payload["available_domains"]
    assert payload["schema_digest"].startswith("sha256:")
    assert payload["sanitized_context"] == {"task_hint": "deliver ticket 3293"}


def test_build_router_interpret_request_validates_mode_payload():
    with pytest.raises(ValueError, match="natural_language mode requires intent"):
        build_router_interpret_request(mode="natural_language", calling_agent="surgeon")


def test_router_client_posts_cli_interpret_request(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://router.example.test/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.98,
            "match_type": "exact",
            "inferred_intent": "Show ticket 3293 as JSON",
            "operation_plan": [
                {
                    "domain": "tickets",
                    "action": "show",
                    "parameters": {"ticket_id": 3293, "json": True},
                    "risk": "read",
                }
            ],
            "needs_confirmation": False,
            "message": "Move --json before the command group.",
        },
    )
    client = RouterClient(base_url="https://router.example.test", token="test-router-jwt")

    response = client.interpret_error(
        failed_command="sanctum --agent surgeon tickets show --json 3293",
        error_output="Error: No such option: --json",
        calling_agent="surgeon",
        root=main,
    )

    request = httpx_mock.get_request()
    assert request.headers["Authorization"] == "Bearer test-router-jwt"
    assert request.read()
    assert response.status == "interpreted"
    assert response.operation_plan[0].domain == "tickets"
    assert response.operation_plan[0].parameters == {"ticket_id": 3293, "json": True}
    assert response.needs_confirmation is False


def test_router_client_requires_token():
    client = RouterClient(base_url="https://router.example.test", token="")
    request = build_router_interpret_request(
        mode="natural_language",
        intent="Find unresolved Router tickets",
        calling_agent="surgeon",
    )

    with pytest.raises(RouterClientError, match="SANCTUM_ROUTER_TOKEN"):
        client.interpret(request)


def test_router_client_reports_http_errors(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://router.example.test/v1/cli-interpret",
        status_code=403,
        json={"error": {"message": "Missing required scope: router:invoke"}},
    )
    client = RouterClient(base_url="https://router.example.test", token="test-router-jwt")
    request = build_router_interpret_request(
        mode="natural_language",
        intent="Find unresolved Router tickets",
        calling_agent="surgeon",
    )

    with pytest.raises(RouterClientError) as exc:
        client.interpret(request)

    assert exc.value.status_code == 403
