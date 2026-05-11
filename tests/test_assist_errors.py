"""Tests for deterministic CLI assist error explanations."""

from click.testing import CliRunner

from sanctum_cli.assist.errors import explain_error, parse_cli_error
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

    assert explanation.status == "assist_missing_fields"
    assert explanation.error_class == "invalid_choice"
    assert explanation.missing_fields == ("--status",)
    assert "new, open" in explanation.message


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
