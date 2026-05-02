"""Tests for mockups domain commands."""

from click.testing import CliRunner

from sanctum_cli.cli import main
from sanctum_cli.domains.mockups import _content_hash

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


class TestMockupsShow:
    def test_show_mockup(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}/42d0e351-28a9-44dc-9b1d-d2962a9138ea",
            json={
                "id": "42d0e351-28a9-44dc-9b1d-d2962a9138ea",
                "name": "Version History Card",
                "status": "active",
                "ticket_id": 3175,
                "links_count": 1,
                "created_at": "2026-01-01",
                "mime_type": "text/html",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "mockups",
                "show",
                "42d0e351-28a9-44dc-9b1d-d2962a9138ea",
            ],
        )
        assert result.exit_code == 0
        assert "Version History Card" in result.output
        assert "3175" in result.output
        assert "text/html" in result.output

    def test_show_mockup_json(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}/mockup-uuid-1",
            json={
                "id": "mockup-uuid-1",
                "name": "JSON Mockup",
                "status": "active",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "oracle", "--json", "mockups", "show", "mockup-uuid-1"],
        )
        assert result.exit_code == 0
        assert '"name": "JSON Mockup"' in result.output


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

    def test_update_mockup_ticket(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_MOCKUP_URL}/mockup-uuid-1",
            json={"id": "mockup-uuid-1", "ticket_id": 3175},
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
                "--ticket-id",
                "3175",
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

    def test_update_content_invalidates_lint_metadata(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}/mockup-uuid-1?expand=content",
            json={
                "id": "mockup-uuid-1",
                "category": "mockup",
                "mime_type": "text/html",
                "content": "old",
                "metadata": {"version_label": "v1", "annotations": [{"id": "a1"}]},
            },
        )
        httpx_mock.add_response(
            method="PUT",
            url=f"{_MOCKUP_URL}/mockup-uuid-1",
            json={"id": "mockup-uuid-1"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "mockups", "update", "mockup-uuid-1", "--content", "new"],
        )
        assert result.exit_code == 0
        request = httpx_mock.get_request(method="PUT", url=f"{_MOCKUP_URL}/mockup-uuid-1")
        payload = request.read().decode()
        assert '"status":"not_run"' in payload.replace(" ", "")
        assert '"published":false' in payload.replace(" ", "")
        assert '"annotations":[{"id":"a1"}]' in payload.replace(" ", "")


class TestMockupsGate:
    def test_lint_persists_result_and_preserves_metadata(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}/mockup-uuid-1?expand=content",
            json={
                "id": "mockup-uuid-1",
                "category": "mockup",
                "mime_type": "text/html",
                "content": "<main>Ready</main>",
                "metadata": {"version_label": "v1", "annotations": [{"id": "a1"}]},
            },
        )
        httpx_mock.add_response(
            method="PUT",
            url=f"{_MOCKUP_URL}/mockup-uuid-1",
            json={"id": "mockup-uuid-1"},
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--agent", "surgeon", "mockups", "lint", "mockup-uuid-1"])
        assert result.exit_code == 0
        assert "lint passed" in result.output
        request = httpx_mock.get_request(method="PUT", url=f"{_MOCKUP_URL}/mockup-uuid-1")
        payload = request.read().decode().replace(" ", "")
        assert '"mockup_lint"' in payload
        assert '"status":"pass"' in payload
        assert '"annotations":[{"id":"a1"}]' in payload

    def test_lint_dry_run_does_not_write(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}/mockup-uuid-1?expand=content",
            json={
                "id": "mockup-uuid-1",
                "category": "mockup",
                "mime_type": "text/html",
                "content": "<main>Ready</main>",
                "metadata": {},
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "--json", "mockups", "lint", "mockup-uuid-1", "--dry-run"],
        )
        assert result.exit_code == 0
        assert '"persisted": false' in result.output
        assert len(httpx_mock.get_requests()) == 1

    def test_lint_rejects_non_mockup_without_write(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}/article-1?expand=content",
            json={"id": "article-1", "category": "article", "metadata": {}},
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--agent", "surgeon", "mockups", "lint", "article-1"])
        assert result.exit_code == 0
        assert "non-mockup" in result.output
        assert len(httpx_mock.get_requests()) == 1

    def test_publish_rejects_stale_hash_without_write(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}/mockup-uuid-1?expand=content",
            json={
                "id": "mockup-uuid-1",
                "category": "mockup",
                "mime_type": "text/html",
                "content": "current",
                "metadata": {
                    "mockup_lint": {
                        "status": "pass",
                        "content_hash": "sha256:stale",
                        "issues": [],
                    }
                },
            },
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--agent", "surgeon", "mockups", "publish", "mockup-uuid-1"])
        assert result.exit_code == 0
        assert "stale" in result.output
        assert len(httpx_mock.get_requests()) == 1

    def test_publish_success(self, httpx_mock, mock_agent_tokens):
        content = "<main>Ready</main>"
        lint = {"status": "pass", "content_hash": _content_hash("text/html", content), "issues": []}
        httpx_mock.add_response(
            method="GET",
            url=f"{_MOCKUP_URL}/mockup-uuid-1?expand=content",
            json={
                "id": "mockup-uuid-1",
                "category": "mockup",
                "mime_type": "text/html",
                "content": content,
                "metadata": {"version_label": "v1", "mockup_lint": lint},
            },
        )
        httpx_mock.add_response(
            method="PUT",
            url=f"{_MOCKUP_URL}/mockup-uuid-1",
            json={"id": "mockup-uuid-1"},
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--agent", "surgeon", "mockups", "publish", "mockup-uuid-1"])
        assert result.exit_code == 0
        assert "published" in result.output
        request = httpx_mock.get_request(method="PUT", url=f"{_MOCKUP_URL}/mockup-uuid-1")
        payload = request.read().decode().replace(" ", "")
        assert '"published":true' in payload
        assert '"version_label":"v1"' in payload


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
