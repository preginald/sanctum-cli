"""Tests for Sanctum Flow domain commands."""

import json

from click.testing import CliRunner

from sanctum_cli.cli import main

_FLOW_URL = "https://flow.digitalsanctum.com.au/api/v1"
_ACCOUNT_ID = "a1b2c3d4-0001-4000-8000-000000000001"
_DEFINITION_ID = "11111111-1111-4111-8111-111111111111"
_INSTANCE_ID = "22222222-2222-4222-8222-222222222222"
_STEP_ID = "33333333-3333-4333-8333-333333333333"
_RUN_ID = "44444444-4444-4444-8444-444444444444"


def test_flow_list_definitions(httpx_mock, mock_agent_tokens):
    httpx_mock.add_response(
        method="GET",
        url=f"{_FLOW_URL}/process-definitions/?limit=50&offset=0&status=published",
        json=[
            {
                "id": _DEFINITION_ID,
                "definition_key": "client-onboarding",
                "version": 1,
                "name": "Client Onboarding",
                "status": "published",
                "category": "operations",
            }
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--json", "--agent", "oracle", "flow", "list", "--status", "published"],
    )

    assert result.exit_code == 0
    assert "client-onboarding" in result.output


def test_flow_definition_create_posts_schema(httpx_mock, mock_agent_tokens):
    httpx_mock.add_response(
        method="POST",
        url=f"{_FLOW_URL}/process-definitions/",
        json={"id": _DEFINITION_ID, "definition_key": "hello", "status": "draft"},
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--agent",
            "architect",
            "flow",
            "definition-create",
            "--account-id",
            _ACCOUNT_ID,
            "--definition-key",
            "hello",
            "--name",
            "Hello Flow",
            "--schema",
            '{"steps":[{"key":"start","name":"Start","type":"start_event"}]}',
        ],
    )

    assert result.exit_code == 0
    assert "Flow definition created" in result.output
    request = httpx_mock.get_request()
    assert request is not None
    payload = json.loads(request.read())
    assert payload["account_id"] == _ACCOUNT_ID
    assert payload["definition_key"] == "hello"
    assert payload["schema_"]["steps"][0]["key"] == "start"


def test_flow_show_instance_expands_steps_and_events(httpx_mock, mock_agent_tokens):
    httpx_mock.add_response(
        method="GET",
        url=f"{_FLOW_URL}/process-instances/{_INSTANCE_ID}",
        json={"id": _INSTANCE_ID, "definition_id": _DEFINITION_ID, "status": "running"},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{_FLOW_URL}/process-instances/{_INSTANCE_ID}/steps",
        json=[{"id": _STEP_ID, "step_key": "review", "status": "active"}],
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{_FLOW_URL}/process-instances/{_INSTANCE_ID}/events",
        json=[{"event_type": "instance_started"}],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--json",
            "--agent",
            "oracle",
            "flow",
            "show",
            _INSTANCE_ID,
            "--type",
            "instance",
            "--include-steps",
            "--include-events",
        ],
    )

    assert result.exit_code == 0
    assert '"steps"' in result.output
    assert '"events"' in result.output


def test_flow_update_step_posts_action_detail(httpx_mock, mock_agent_tokens):
    httpx_mock.add_response(
        method="POST",
        url=f"{_FLOW_URL}/process-instances/{_INSTANCE_ID}/steps/{_STEP_ID}/actions",
        json={"id": _STEP_ID, "status": "completed"},
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--agent",
            "architect",
            "flow",
            "update-step",
            _INSTANCE_ID,
            _STEP_ID,
            "--action",
            "complete",
            "--actor",
            "architect",
            "--detail",
            '{"selected_edge":"approved"}',
        ],
    )

    assert result.exit_code == 0
    assert "Flow step action applied" in result.output
    request = httpx_mock.get_request()
    assert request is not None
    assert json.loads(request.read()) == {
        "action": "complete",
        "actor": "architect",
        "detail": {"selected_edge": "approved"},
    }


def test_flow_simulation_results_fetches_related_resources(httpx_mock, mock_agent_tokens):
    httpx_mock.add_response(
        method="GET",
        url=f"{_FLOW_URL}/simulation-runs/{_RUN_ID}",
        json={
            "id": _RUN_ID,
            "definition_id": _DEFINITION_ID,
            "status": "completed",
            "n_runs": 1000,
        },
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{_FLOW_URL}/simulation-runs/{_RUN_ID}/results",
        json=[{"step_key": "review", "mean_duration_s": 10}],
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{_FLOW_URL}/simulation-runs/{_RUN_ID}/recommendations",
        json=[{"title": "Reduce bottleneck"}],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--json", "--agent", "oracle", "flow", "simulation-results", _RUN_ID],
    )

    assert result.exit_code == 0
    assert '"results"' in result.output
    assert '"recommendations"' in result.output
