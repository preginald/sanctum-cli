"""Tests for tickets domain commands."""

from click.testing import CliRunner

from sanctum_cli.cli import main

_TICKET_URL = "https://core.digitalsanctum.com.au/api/tickets"


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
            method="POST",
            url="https://core.digitalsanctum.com.au/api/comments",
            json={"id": "comment-new", "ticket_id": 3176, "body": "Pushback noted"},
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
