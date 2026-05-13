"""Tests for deterministic CLI assist error explanations."""

from click.testing import CliRunner

from sanctum_cli.assist.errors import explain_error, parse_cli_error
from sanctum_cli.assist.router_client import RouterClient
from sanctum_cli.cli import main


def test_explain_error_moves_json_global_flag_before_command():
    explanation = explain_error(
        "sanctum --agent surgeon tickets show --json 3293",
        "Error: No such option: --json",
        root=main,
    )

    assert explanation.status == "assist_suggestion"
    assert explanation.error_class == "misplaced_global_flag"
    assert explanation.generated_command == "sanctum --agent surgeon --json tickets show 3293"
    assert explanation.validation == "valid"
    assert explanation.needs_confirmation is False


def test_explain_error_reports_missing_required_option():
    explanation = explain_error(
        "sanctum --agent surgeon tickets create --subject Test",
        "Error: Missing option '--description'.",
        root=main,
    )

    assert explanation.status == "assist_missing_fields"
    assert explanation.missing_fields == ("--description",)
    assert explanation.generated_command is None


def test_parse_cli_error_extracts_did_you_mean_option():
    parsed = parse_cli_error("Error: No such option: --project Did you mean '--project-id'?")

    assert parsed.error_class == "no_such_option"
    assert parsed.option == "--project"
    assert parsed.suggestion == "--project-id"


def test_parse_cli_error_extracts_invalid_choice_values():
    parsed = parse_cli_error(
        "Error: Invalid value for '--status': 'done' is not one of 'new', 'open', 'closed'."
    )

    assert parsed.error_class == "invalid_choice"
    assert parsed.option == "--status"
    assert parsed.choices == ("new", "open", "closed")


def test_explain_error_reports_unexpected_extra_argument():
    explanation = explain_error(
        "sanctum --agent surgeon tickets show 3293 extra",
        "Error: Got unexpected extra argument (extra)",
        root=main,
    )

    assert explanation.status == "assist_confirmation_required"
    assert explanation.error_class == "unexpected_extra_argument"
    assert explanation.generated_command == "sanctum --agent surgeon tickets show 3293"
    assert explanation.needs_confirmation is True


def test_explain_error_reports_invalid_choice_options():
    explanation = explain_error(
        "sanctum --agent surgeon tickets update 3293 --status done",
        "Error: Invalid value for '--status': 'done' is not one of 'new', 'open'.",
        root=main,
    )

    assert explanation.status == "assist_suggestion"
    assert explanation.error_class == "invalid_choice"
    assert "open" in explanation.message


def test_explain_error_adds_default_agent_for_known_domain():
    explanation = explain_error(
        "sanctum tickets list",
        "Error: --agent <name> or --user <email> is required",
        root=main,
    )

    assert explanation.status == "assist_suggestion"
    assert explanation.error_class == "missing_identity"
    assert explanation.generated_command == "sanctum --agent surgeon tickets list"
    assert explanation.risk == "read"
    assert explanation.validation == "valid"


def test_explain_error_reports_flow_api_key_requirement():
    explanation = explain_error(
        "sanctum --agent architect flow list",
        "Error: Unauthorized: Flow requires an X-API-Key; Core bearer audience is invalid.",
        root=main,
    )

    assert explanation.status == "assist_missing_fields"
    assert explanation.error_class == "missing_flow_api_key"
    assert explanation.missing_fields == ("--api-key",)
    assert explanation.generated_command is None
    assert "SANCTUM_FLOW_API_KEY" in explanation.message


def test_explain_error_reports_content_flag_missing_value():
    explanation = explain_error(
        "sanctum --agent surgeon mockups update 123 --content",
        "Error: Option '--content' requires an argument.",
        root=main,
    )

    assert explanation.status == "assist_missing_fields"
    assert explanation.error_class == "content_flag_missing_value"
    assert explanation.missing_fields == ("--content",)
    assert explanation.needs_confirmation is True


def test_explain_error_maps_time_entry_positionals_to_options():
    explanation = explain_error(
        "sanctum --agent surgeon time-entries create 3421 2026-05-11T01:00:00Z "
        "2026-05-11T01:15:00Z deterministic patterns",
        "Error: Got unexpected extra argument (3421)",
        root=main,
    )

    assert explanation.status == "assist_suggestion"
    assert explanation.error_class == "positional_values_for_options"
    assert explanation.generated_command == (
        "sanctum --agent surgeon time-entries create --ticket-id 3421 "
        "--start 2026-05-11T01:00:00Z --end 2026-05-11T01:15:00Z "
        "--description 'deterministic patterns'"
    )
    assert explanation.risk == "write"
    assert explanation.needs_confirmation is True


def test_explain_error_reports_invalid_identifier_shape():
    explanation = explain_error(
        "sanctum --agent surgeon tickets show abc",
        "Error: Invalid value for 'TICKET_ID': 'abc' is not a valid integer.",
        root=main,
    )

    assert explanation.status == "assist_missing_fields"
    assert explanation.error_class == "invalid_identifier"
    assert explanation.missing_fields == ("ticket_id",)
    assert explanation.generated_command is None


def test_explain_error_command_outputs_json(mock_agent_tokens):
    result = CliRunner().invoke(
        main,
        [
            "--agent",
            "surgeon",
            "--json",
            "explain-error",
            "--failed-command",
            "sanctum --agent surgeon tickets show --json 3293",
            "--error-output",
            "Error: No such option: --json",
        ],
    )

    assert result.exit_code == 0
    assert '"error_class": "misplaced_global_flag"' in result.output
    expected_command = '"generated_command": "sanctum --agent surgeon --json tickets show 3293"'
    assert expected_command in result.output


def test_assist_activation_renders_suggestion_for_malformed_command(mock_agent_tokens):
    result = CliRunner().invoke(
        main,
        ["--assist", "--agent", "surgeon", "tickets", "show", "--json", "3293"],
    )

    assert result.exit_code == 1
    assert "Sanctum CLI Assist detected a malformed command." in result.output
    assert "sanctum --assist --agent surgeon --json tickets show" in result.output


def test_router_fallback_fires_when_deterministic_unsupported(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        json={
            "status": "interpreted",
            "confidence": 0.72,
            "match_type": "partial",
            "inferred_intent": "List all open tickets",
            "operation_plan": [
                {
                    "domain": "tickets",
                    "action": "list",
                    "parameters": {"status": "open"},
                    "risk": "read",
                }
            ],
            "needs_confirmation": False,
            "message": "Interpreted via Router.",
        },
    )

    client = RouterClient(token="test-token")
    explanation = explain_error(
        "sanctum --agent surgeon unknown-command arg1",
        "Error: totally unexpected error format that no parser can match",
        root=main,
        calling_agent="surgeon",
        router=client,
    )

    assert explanation.status == "router_interpreted"
    assert explanation.error_class == "router_partial"
    assert explanation.confidence == 0.72
    assert explanation.generated_command == "sanctum --agent surgeon tickets list --status open"
    assert explanation.inferred_intent == "List all open tickets"
    assert explanation.details.get("router_response") is not None


def test_router_fallback_skipped_when_deterministic_matches(httpx_mock):
    client = RouterClient(token="test-token")
    explanation = explain_error(
        "sanctum --agent surgeon tickets show --json 3293",
        "Error: No such option: --json",
        root=main,
        calling_agent="surgeon",
        router=client,
    )

    assert explanation.status == "assist_suggestion"
    assert explanation.error_class == "misplaced_global_flag"
    assert explanation.generated_command == "sanctum --agent surgeon --json tickets show 3293"


def test_router_fallback_handles_http_error_gracefully(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://router.digitalsanctum.com.au/v1/cli-interpret",
        status_code=500,
    )

    client = RouterClient(token="test-token")
    explanation = explain_error(
        "sanctum --agent surgeon unknown-thing arg",
        "Error: completely unrecognizable error",
        root=main,
        calling_agent="surgeon",
        router=client,
    )

    assert explanation.status == "assist_unsupported"
    assert explanation.error_class == "unsupported_error"


def test_router_fallback_skipped_when_no_router_provided():
    explanation = explain_error(
        "sanctum --agent surgeon unknown-thing arg",
        "Error: completely unrecognizable error",
        root=main,
        calling_agent="surgeon",
        router=None,
    )

    assert explanation.status == "assist_unsupported"
    assert explanation.error_class == "unsupported_error"


def test_router_fallback_skipped_when_no_calling_agent(httpx_mock):
    """Router fallback requires calling_agent to build the operation plan command."""
    client = RouterClient(token="test-token")
    explanation = explain_error(
        "sanctum --agent surgeon unknown-thing arg",
        "Error: completely unrecognizable error",
        root=main,
        calling_agent=None,
        router=client,
    )

    assert explanation.status == "assist_unsupported"
    assert explanation.error_class == "unsupported_error"
