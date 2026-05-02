"""Tests for artefacts domain commands."""

from click.testing import CliRunner

from sanctum_cli.cli import main

_API_BASE = "https://core.digitalsanctum.com.au/api"


class TestArtefactsCreate:
    def test_create_minimal(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_API_BASE}/artefacts",
            json={"id": "artefact-uuid", "name": "Test Artefact", "artefact_type": "document"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "create",
                "--name",
                "Test Artefact",
                "--type",
                "document",
            ],
        )
        assert result.exit_code == 0
        assert "Artefact created: artefact-uuid" in result.output

    def test_create_with_content(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_API_BASE}/artefacts",
            json={"id": "artefact-uuid", "name": "Content Artefact", "artefact_type": "document"},
        )
        httpx_mock.add_response(
            method="PUT",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={"id": "artefact-uuid"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "create",
                "--name",
                "Content Artefact",
                "--type",
                "document",
                "--content",
                "test content",
            ],
        )
        assert result.exit_code == 0
        assert "Artefact created: artefact-uuid" in result.output


class TestArtefactsList:
    def test_list_artefacts(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/artefacts?limit=20",
            json={
                "artefacts": [
                    {
                        "name": "Artefact A",
                        "artefact_type": "document",
                        "status": "active",
                        "links_count": 1,
                    },
                    {
                        "name": "Artefact B",
                        "artefact_type": "url",
                        "status": "active",
                        "links_count": 0,
                    },
                ]
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "list",
            ],
        )
        assert result.exit_code == 0
        assert "Artefact A" in result.output
        assert "Artefact B" in result.output


class TestArtefactsShow:
    def test_show_artefact(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={
                "name": "Test Artefact",
                "artefact_type": "document",
                "status": "active",
                "category": "test",
                "account_name": "Test Account",
                "links_count": 1,
                "created_at": "2026-04-30T00:00:00Z",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "show",
                "artefact-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Test Artefact" in result.output

    def test_show_artefact_with_content(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/artefacts/artefact-uuid?expand=content",
            json={
                "name": "Test Artefact",
                "artefact_type": "document",
                "status": "active",
                "category": "test",
                "account_name": "Test Account",
                "links_count": 1,
                "created_at": "2026-04-30T00:00:00Z",
                "content": "# Document\n\nBody content",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "show",
                "artefact-uuid",
                "--content",
            ],
        )
        assert result.exit_code == 0
        assert "Test Artefact" in result.output
        assert "--- Content ---" in result.output
        assert "# Document" in result.output
        assert "Body content" in result.output

    def test_show_artefact_with_content_json(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/artefacts/artefact-uuid?expand=content",
            json={
                "name": "Test Artefact",
                "artefact_type": "document",
                "content": "Body content",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "artefacts",
                "show",
                "artefact-uuid",
                "--content",
            ],
        )
        assert result.exit_code == 0
        assert '"content": "Body content"' in result.output


class TestArtefactsLink:
    def test_link_via_project_id(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_API_BASE}/artefacts/artefact-uuid/link",
            json={"status": "linked"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "link",
                "artefact-uuid",
                "--project-id",
                "proj-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "linked to project proj-uuid" in result.output

    def test_link_via_entity_type_id(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_API_BASE}/artefacts/artefact-uuid/link",
            json={"status": "linked"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "link",
                "artefact-uuid",
                "--entity-type",
                "ticket",
                "--entity-id",
                "12345",
            ],
        )
        assert result.exit_code == 0
        assert "linked to ticket 12345" in result.output

    def test_link_project_id_and_entity_conflict(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "link",
                "artefact-uuid",
                "--project-id",
                "proj-uuid",
                "--entity-type",
                "ticket",
                "--entity-id",
                "12345",
            ],
        )
        assert result.exit_code == 0
        assert "Provide either --project-id or --entity-type" in result.output

    def test_link_missing_entity_args(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "link",
                "artefact-uuid",
                "--entity-type",
                "ticket",
            ],
        )
        assert result.exit_code == 0
        assert "Provide --project-id or both" in result.output

    def test_link_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_API_BASE}/artefacts/artefact-uuid/link",
            json={
                "status": "linked",
                "artefact_id": "artefact-uuid",
                "entity_id": "proj-uuid",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "artefacts",
                "link",
                "artefact-uuid",
                "--project-id",
                "proj-uuid",
            ],
        )
        assert result.exit_code == 0
        assert '"status": "linked"' in result.output

    def test_link_error(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_API_BASE}/artefacts/artefact-uuid/link",
            status_code=422,
            json={"detail": "Invalid project ID"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "link",
                "artefact-uuid",
                "--project-id",
                "proj-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Invalid project ID" in result.output


class TestArtefactsUnlink:
    def test_unlink_via_project_id(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{_API_BASE}/artefacts/artefact-uuid/link/project/proj-uuid",
            json={"status": "unlinked"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "unlink",
                "artefact-uuid",
                "--project-id",
                "proj-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "unlinked from project proj-uuid" in result.output

    def test_unlink_via_entity_type_id(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{_API_BASE}/artefacts/artefact-uuid/link/ticket/12345",
            json={"status": "unlinked"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "unlink",
                "artefact-uuid",
                "--entity-type",
                "ticket",
                "--entity-id",
                "12345",
            ],
        )
        assert result.exit_code == 0
        assert "unlinked from ticket 12345" in result.output

    def test_unlink_project_id_and_entity_conflict(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "unlink",
                "artefact-uuid",
                "--project-id",
                "proj-uuid",
                "--entity-type",
                "ticket",
                "--entity-id",
                "12345",
            ],
        )
        assert result.exit_code == 0
        assert "Provide either --project-id or --entity-type" in result.output

    def test_unlink_missing_entity_args(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "unlink",
                "artefact-uuid",
                "--entity-type",
                "ticket",
            ],
        )
        assert result.exit_code == 0
        assert "Provide --project-id or both" in result.output

    def test_unlink_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{_API_BASE}/artefacts/artefact-uuid/link/project/proj-uuid",
            json={"status": "unlinked"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "artefacts",
                "unlink",
                "artefact-uuid",
                "--project-id",
                "proj-uuid",
            ],
        )
        assert result.exit_code == 0
        assert '"status": "unlinked"' in result.output


class TestArtefactsUpdate:
    def test_update_name(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={"id": "artefact-uuid", "name": "New Name"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "update",
                "artefact-uuid",
                "--name",
                "New Name",
            ],
        )
        assert result.exit_code == 0
        assert "Artefact artefact-uuid updated" in result.output

    def test_update_multiple_fields(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={"id": "artefact-uuid", "name": "New Name", "description": "New Desc"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "update",
                "artefact-uuid",
                "--name",
                "New Name",
                "--description",
                "New Desc",
                "--status",
                "review",
            ],
        )
        assert result.exit_code == 0
        assert "Artefact artefact-uuid updated" in result.output

    def test_update_nothing(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "update",
                "artefact-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Nothing to update" in result.output

    def test_update_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={"id": "artefact-uuid", "name": "New Name"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "artefacts",
                "update",
                "artefact-uuid",
                "--name",
                "New Name",
            ],
        )
        assert result.exit_code == 0
        assert '"name": "New Name"' in result.output

    def test_update_error(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            status_code=422,
            json={"detail": "Invalid status"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "update",
                "artefact-uuid",
                "--status",
                "bad",
            ],
        )
        assert result.exit_code == 0
        assert "Invalid status" in result.output


class TestArtefactsTransition:
    def test_transition_success(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={
                "id": "artefact-uuid",
                "name": "Test Artefact",
                "status": "draft",
                "available_transitions": ["review", "archived"],
            },
        )
        httpx_mock.add_response(
            method="PUT",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={"id": "artefact-uuid", "status": "review"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "transition",
                "artefact-uuid",
                "--to",
                "review",
            ],
        )
        assert result.exit_code == 0
        assert "transitioned to review" in result.output

    def test_transition_invalid(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={
                "id": "artefact-uuid",
                "name": "Test Artefact",
                "status": "draft",
                "available_transitions": ["review", "archived"],
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "transition",
                "artefact-uuid",
                "--to",
                "published",
            ],
        )
        assert result.exit_code == 0
        assert "Cannot transition" in result.output
        assert "published" in result.output
        assert "review" in result.output

    def test_transition_fetch_error(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            status_code=404,
            json={"detail": "Not found"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "artefacts",
                "transition",
                "artefact-uuid",
                "--to",
                "review",
            ],
        )
        assert result.exit_code == 0
        assert "Failed to fetch artefact" in result.output

    def test_transition_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={
                "id": "artefact-uuid",
                "name": "Test Artefact",
                "status": "draft",
                "available_transitions": ["review", "archived"],
            },
        )
        httpx_mock.add_response(
            method="PUT",
            url=f"{_API_BASE}/artefacts/artefact-uuid",
            json={"id": "artefact-uuid", "status": "review"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "artefacts",
                "transition",
                "artefact-uuid",
                "--to",
                "review",
            ],
        )
        assert result.exit_code == 0
        assert '"status": "review"' in result.output
