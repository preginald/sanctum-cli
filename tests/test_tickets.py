"""Tests for tickets domain commands."""

import json
import os
import tempfile

from click.testing import CliRunner

from sanctum_cli.cli import main
from sanctum_cli.domains.tickets import _ensure_template_compliance

_TICKET_URL = "https://core.digitalsanctum.com.au/api/tickets"
_SEARCH_URL = "https://core.digitalsanctum.com.au/api/search"


class TestTicketCreate:
    def test_create_prompts_for_missing_account_uuid(self, httpx_mock, mock_agent_tokens):
        account_id = "11111111-1111-4111-8111-111111111111"
        httpx_mock.add_response(
            method="POST",
            url=_TICKET_URL,
            json={"id": 42, "subject": "Test ticket"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "tickets", "create", "--subject", "Test ticket"],
            input=f"{account_id}\n",
        )

        assert result.exit_code == 0
        assert "Ticket creation needs an account UUID" in result.output
        assert "Ticket #42 created" in result.output
        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.read())["account_id"] == account_id

    def test_create_searches_and_confirms_client_name(self, httpx_mock, mock_agent_tokens):
        account_id = "22222222-2222-4222-8222-222222222222"
        httpx_mock.add_response(
            method="GET",
            url=f"{_SEARCH_URL}?q=Acme&type=client&limit=5",
            json={
                "results": [
                    {
                        "type": "client",
                        "title": "Acme Pty Ltd",
                        "account_id": account_id,
                        "score": 0.97,
                    }
                ]
            },
        )
        httpx_mock.add_response(
            method="POST",
            url=_TICKET_URL,
            json={"id": 43, "subject": "Client lookup ticket"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "tickets", "create", "--subject", "Client lookup ticket"],
            input="Acme\ny\n",
        )

        assert result.exit_code == 0
        assert "Client matches for: Acme" in result.output
        assert "Acme Pty Ltd" in result.output
        assert "Ticket #43 created" in result.output
        requests = httpx_mock.get_requests()
        assert len(requests) == 2
        assert json.loads(requests[1].read())["account_id"] == account_id


class TestTicketShow:
    def test_show_ticket_with_comments(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_TICKET_URL}/3176?expand=comments",
            json={
                "id": 3176,
                "subject": "Test ticket",
                "status": "open",
                "priority": "normal",
                "ticket_type": "task",
                "project_name": "Test Project",
                "account_name": "Test Account",
                "created_at": "2026-04-30",
                "description": "A test ticket.",
                "comments": [
                    {
                        "id": "comment-1",
                        "body": "First comment",
                        "author_name": "Surgeon",
                        "created_at": "2026-04-30T10:00:00Z",
                    },
                    {
                        "id": "comment-2",
                        "body": "Second comment\nwith multiple lines",
                        "author_name": "Architect",
                        "created_at": "2026-04-30T11:00:00Z",
                    },
                ],
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "oracle", "tickets", "show", "3176", "--comments"],
        )
        assert result.exit_code == 0
        assert "Test ticket" in result.output
        assert "Comments (2)" in result.output
        assert "First comment" in result.output
        assert "Second comment" in result.output
        assert "Surgeon" in result.output
        assert "Architect" in result.output

    def test_show_ticket_no_comments_flag(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_TICKET_URL}/3176",
            json={
                "id": 3176,
                "subject": "Test ticket",
                "status": "open",
                "priority": "normal",
                "ticket_type": "task",
                "project_name": "Test Project",
                "account_name": "Test Account",
                "created_at": "2026-04-30",
                "description": "A test ticket.",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "oracle", "tickets", "show", "3176"],
        )
        assert result.exit_code == 0
        assert "Comments" not in result.output


class TestTicketComment:
    def test_add_comment(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url="https://core.digitalsanctum.com.au/api/tickets/3176",
            json={"id": 3176, "status": "new"},
        )
        httpx_mock.add_response(
            method="POST",
            url="https://core.digitalsanctum.com.au/api/comments",
            json={"id": "comment-new", "ticket_id": 3176, "body": "Pushback noted"},
        )
        httpx_mock.add_response(
            method="GET",
            url="https://core.digitalsanctum.com.au/api/tickets/3176",
            json={"id": 3176, "status": "new"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "tickets",
                "comment",
                "3176",
                "--body",
                "Pushback noted",
            ],
        )
        assert result.exit_code == 0
        assert "Comment added to #3176" in result.output
        assert "View full history" in result.output


class TestTicketUpdate:
    def test_update_phase_criteria(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_TICKET_URL}/3176",
            json={"id": 3176, "status": "recon", "phase_criteria": {"recon_complete": True}},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "tickets",
                "update",
                "3176",
                "--phase-criteria",
                "recon_complete",
            ],
        )

        assert result.exit_code == 0
        assert "Ticket #3176 updated" in result.output
        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.read()) == {"phase_criteria": {"recon_complete": True}}

    def test_update_phase_criteria_with_status(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_TICKET_URL}/3176",
            json={"id": 3176, "status": "proposal"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "tickets",
                "update",
                "3176",
                "--phase-criteria",
                "recon_complete=true",
                "--status",
                "proposal",
            ],
        )

        assert result.exit_code == 0
        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.read()) == {
            "status": "proposal",
            "phase_criteria": {"recon_complete": True},
        }

    def test_update_phase_criteria_rejects_non_bool_value(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "tickets",
                "update",
                "3176",
                "--phase-criteria",
                "recon_complete=yes",
            ],
        )

        assert result.exit_code != 0
        assert "phase criteria values must be true or false" in result.output


class TestTemplateCompliance:
    def test_free_form_feature_gets_wrapped(self):
        result = _ensure_template_compliance("Fix the login bug", "feature")
        assert "## Objective" in result
        assert "## Requirements" in result
        assert "## Test Plan" in result
        assert "## Acceptance Criteria" in result
        assert "Fix the login bug" in result

    def test_free_form_task_gets_wrapped(self):
        result = _ensure_template_compliance("Add dark mode toggle", "task")
        assert "## Objective" in result
        assert "Add dark mode toggle" in result

    def test_free_form_test_gets_wrapped(self):
        result = _ensure_template_compliance("Run smoke test", "test")
        assert "## Objective" in result
        assert "## Test Plan" in result
        assert "## Expected Results" in result
        assert "## Acceptance Criteria" in result

    def test_partial_headings_appends_missing_sections(self):
        desc = "## Objective\n\nDo the thing\n\n## Requirements\n\nNone"
        result = _ensure_template_compliance(desc, "feature")
        assert "## Objective" in result
        assert "## Requirements" in result
        assert "## Test Plan" in result
        assert "## Acceptance Criteria" in result
        assert "Do the thing" in result
        assert "None" in result

    def test_empty_description_returns_empty(self):
        assert _ensure_template_compliance("", "feature") == ""
        assert _ensure_template_compliance(None, "feature") == ""

    def test_unknown_type_returns_unchanged(self):
        desc = "Just some text"
        result = _ensure_template_compliance(desc, "support")
        assert result == desc

    def test_bug_template_has_required_sections(self):
        result = _ensure_template_compliance("Button not working", "bug")
        assert "## Bug" in result
        assert "## Root Cause" in result
        assert "## Acceptance Criteria" in result

    def test_bug_with_aliased_heading(self):
        result = _ensure_template_compliance("## Problem\n\nBroken thing", "bug")
        assert "## Bug" in result
        assert "Broken thing" in result

    def test_partial_headings_appends_missing(self):
        result = _ensure_template_compliance(
            "## Bug\n\nThe form crashes\n\n## Root Cause\n\nNull pointer", "bug"
        )
        assert "## Bug" in result
        assert "## Root Cause" in result
        assert "## Acceptance Criteria" in result


class TestTicketCommentBodyFile:
    def test_body_file_reads_content(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url="https://core.digitalsanctum.com.au/api/tickets/3176",
            json={"id": 3176, "status": "new"},
        )
        httpx_mock.add_response(
            method="POST",
            url="https://core.digitalsanctum.com.au/api/comments",
            json={"id": "c1", "ticket_id": 3176, "body": "from file"},
        )
        httpx_mock.add_response(
            method="GET",
            url="https://core.digitalsanctum.com.au/api/tickets/3176",
            json={"id": 3176, "status": "new"},
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("from file")
            f.flush()
            fname = f.name
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--agent",
                    "surgeon",
                    "tickets",
                    "comment",
                    "3176",
                    "--body-file",
                    fname,
                ],
            )
            assert result.exit_code == 0
            assert "Comment added to #3176" in result.output
        finally:
            os.unlink(fname)

    def test_body_file_not_found(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "tickets",
                "comment",
                "3176",
                "--body-file",
                "/nonexistent/file.md",
            ],
        )
        assert result.exit_code != 0
        assert "Body file not found" in result.output

    def test_body_and_body_file_mutually_exclusive(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "tickets",
                "comment",
                "3176",
                "--body",
                "inline text",
                "--body-file",
                "/tmp/foo.md",
            ],
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_neither_body_nor_body_file_raises_error(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "tickets",
                "comment",
                "3176",
            ],
        )
        assert result.exit_code != 0
        assert "Either --body or --body-file is required" in result.output


class TestTicketResolveBodyFile:
    FETCH_URL = "https://core.digitalsanctum.com.au/api/tickets/3176"
    COMMENT_URL = "https://core.digitalsanctum.com.au/api/comments"
    UPDATE_URL = "https://core.digitalsanctum.com.au/api/tickets/3176"

    def test_resolve_body_file(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=self.FETCH_URL,
            json={"id": 3176, "status": "pending", "available_transitions": ["resolved"]},
        )
        httpx_mock.add_response(
            method="POST",
            url=self.COMMENT_URL,
            json={"id": "rc1", "ticket_id": 3176, "body": "from file"},
        )
        httpx_mock.add_response(
            method="PUT",
            url=self.UPDATE_URL,
            json={"id": 3176, "status": "resolved"},
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("from file")
            f.flush()
            fname = f.name
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--agent",
                    "architect",
                    "tickets",
                    "resolve",
                    "3176",
                    "--body-file",
                    fname,
                ],
            )
            assert result.exit_code == 0
            assert "Ticket #3176 resolved" in result.output
        finally:
            os.unlink(fname)

    def test_resolve_neither_body_nor_body_file(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "architect", "tickets", "resolve", "3176"],
        )
        assert result.exit_code != 0
        assert "Either --body or --body-file is required" in result.output
