"""Tests for mockups domain commands."""

from click.testing import CliRunner

from sanctum_cli.cli import main

_MOCKUP_URL = "https://core.digitalsanctum.com.au/api/artefacts"


class TestMockupsList:
    def test_list_mockups(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}?limit=20&category=mockup",
            json={
                "artefacts": [
                    {
                        "name": "Homepage Hero",
                        "status": "active",
                        "links_count": 2,
                        "created_at": "2026-01-01",
                    },
                ]
            },
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--agent", "oracle", "mockups", "list"])
        assert result.exit_code == 0
        assert "Homepage Hero" in result.output

    def test_list_mockups_empty(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}?limit=20&category=mockup",
            json={"artefacts": []},
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--agent", "oracle", "mockups", "list"])
        assert result.exit_code == 0
        assert "No mockups found" in result.output

    def test_list_mockups_filter_by_ticket(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}?limit=20&category=mockup&ticket_id=3132",
            json={
                "artefacts": [
                    {
                        "name": "Ticket Mockup",
                        "status": "active",
                        "links_count": 1,
                        "created_at": "2026-01-01",
                    },
                ]
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "oracle", "mockups", "list", "--ticket-id", "3132"],
        )
        assert result.exit_code == 0
        assert "Ticket Mockup" in result.output


class TestMockupsCreate:
    def test_create_mockup(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_MOCKUP_URL,
            json={"id": "mockup-uuid-1", "name": "New Design", "category": "mockup"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "mockups", "create", "--name", "New Design"],
        )
        assert result.exit_code == 0
        assert "Mockup created" in result.output

    def test_create_mockup_with_ticket(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_MOCKUP_URL,
            json={
                "id": "mockup-uuid-2",
                "name": "Ticket Design",
                "category": "mockup",
                "ticket_id": 3132,
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "mockups",
                "create",
                "--name",
                "Ticket Design",
                "--ticket-id",
                "3132",
            ],
        )
        assert result.exit_code == 0
        assert "Mockup created" in result.output

    def test_create_mockup_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_MOCKUP_URL,
            json={"id": "mockup-uuid-3", "name": "JSON Design", "category": "mockup"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "mockups",
                "create",
                "--name",
                "JSON Design",
            ],
        )
        assert result.exit_code == 0
        assert '"name": "JSON Design"' in result.output


class TestMockupsUpdate:
    def test_update_mockup_name(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_MOCKUP_URL}/mockup-uuid-1",
            json={"id": "mockup-uuid-1", "name": "Renamed Design"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "mockups",
                "update",
                "mockup-uuid-1",
                "--name",
                "Renamed Design",
            ],
        )
        assert result.exit_code == 0
        assert "Mockup mockup-uuid-1 updated" in result.output

    def test_update_mockup_no_fields(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "mockups", "update", "mockup-uuid-1"],
        )
        assert result.exit_code == 0
        assert "Nothing to update" in result.output


class TestMockupsDelete:
    def test_delete_mockup(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{_MOCKUP_URL}/mockup-uuid-1",
            status_code=204,
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "mockups", "delete", "mockup-uuid-1"],
            input="y\n",
        )
        assert result.exit_code == 0
        assert "Mockup mockup-uuid-1 deleted" in result.output

    def test_delete_mockup_abort(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "mockups", "delete", "mockup-uuid-1"],
            input="n\n",
        )
        assert result.exit_code != 0
