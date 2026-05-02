"""Tests for templates domain commands."""

from click.testing import CliRunner

from sanctum_cli.cli import main

_TEMPLATES_URL = "https://core.digitalsanctum.com.au/api/templates"


class TestTemplateCreate:
    def test_create_template_minimal(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_TEMPLATES_URL}",
            json={
                "id": "tpl-123",
                "name": "Test Template",
                "template_type": "project",
                "is_active": True,
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "create",
                "--name",
                "Test Template",
                "--type",
                "project",
            ],
        )
        assert result.exit_code == 0
        assert "Template created: tpl-123" in result.output
        assert "Name:   Test Template" in result.output
        assert "Type:   project" in result.output

    def test_create_template_with_description_and_icon(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_TEMPLATES_URL}",
            json={
                "id": "tpl-456",
                "name": "Feature Template",
                "template_type": "project",
                "description": "A template for features",
                "icon": "🚀",
                "is_active": True,
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "create",
                "--name",
                "Feature Template",
                "--type",
                "project",
                "--description",
                "A template for features",
                "--icon",
                "🚀",
            ],
        )
        assert result.exit_code == 0
        assert "Template created: tpl-456" in result.output

    def test_create_template_with_tags(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=f"{_TEMPLATES_URL}",
            json={
                "id": "tpl-789",
                "name": "Tagged Template",
                "template_type": "task",
                "tags": ["frontend", "ui"],
                "is_active": True,
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "create",
                "--name",
                "Tagged Template",
                "--type",
                "task",
                "--tag",
                "frontend",
                "--tag",
                "ui",
            ],
        )
        assert result.exit_code == 0
        assert "Template created: tpl-789" in result.output

    def test_create_template_with_sections_json(self, httpx_mock, mock_agent_tokens):
        sections_json = (
            '[{"name": "Setup", "items": [{"name": "Initialize repo", "ticket_type": "task"}]}]'
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{_TEMPLATES_URL}",
            json={
                "id": "tpl-sections",
                "name": "Sectioned Template",
                "template_type": "project",
                "sections": [
                    {"name": "Setup", "items": [{"name": "Initialize repo", "ticket_type": "task"}]}
                ],
                "is_active": True,
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "create",
                "--name",
                "Sectioned Template",
                "--type",
                "project",
                "--sections-json",
                sections_json,
            ],
        )
        assert result.exit_code == 0
        assert "Template created: tpl-sections" in result.output

    def test_create_template_errors_on_both_json_options(self, tmp_path, mock_agent_tokens):
        sections_file = tmp_path / "sections.json"
        sections_file.write_text("[]")
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "create",
                "--name",
                "Test",
                "--type",
                "project",
                "--sections-json",
                "[]",
                "--sections-file",
                str(sections_file),
            ],
        )
        assert result.exit_code == 0
        assert "Provide either --sections-json or --sections-file, not both." in result.output

    def test_create_template_invalid_sections_json(self, httpx_mock, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "create",
                "--name",
                "Test",
                "--type",
                "project",
                "--sections-json",
                "not valid json",
            ],
        )
        assert result.exit_code == 0
        assert "Invalid --sections-json JSON:" in result.output


class TestTemplateUpdate:
    def test_update_template_metadata(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_TEMPLATES_URL}/tpl-existing",
            json={
                "id": "tpl-existing",
                "name": "Updated Name",
                "description": "Updated description",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "update",
                "tpl-existing",
                "--name",
                "Updated Name",
                "--description",
                "Updated description",
            ],
        )
        assert result.exit_code == 0
        assert "Template tpl-existing updated" in result.output

    def test_update_template_with_tags(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PUT",
            url=f"{_TEMPLATES_URL}/tpl-tagged",
            json={"id": "tpl-tagged", "tags": ["backend", "api"]},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "update",
                "tpl-tagged",
                "--tag",
                "backend",
                "--tag",
                "api",
            ],
        )
        assert result.exit_code == 0
        assert "Template tpl-tagged updated" in result.output

    def test_update_template_sections_json(self, httpx_mock, mock_agent_tokens):
        sections_json = '[{"name": "Deploy", "items": [{"name": "Run migrations"}]}]'
        httpx_mock.add_response(
            method="PUT",
            url=f"{_TEMPLATES_URL}/tpl-updated",
            json={
                "id": "tpl-updated",
                "sections": [{"name": "Deploy", "items": [{"name": "Run migrations"}]}],
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "templates",
                "update",
                "tpl-updated",
                "--sections-json",
                sections_json,
            ],
        )
        assert result.exit_code == 0
        assert "Template tpl-updated updated" in result.output

    def test_update_template_nothing_to_do(self, httpx_mock, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "templates", "update", "tpl-123"],
        )
        assert result.exit_code == 0
        assert "Nothing to update. Provide at least one option to change." in result.output


class TestTemplateShow:
    def test_show_template_with_sections(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_TEMPLATES_URL}/tpl-with-sections",
            json={
                "id": "tpl-with-sections",
                "name": "Sectioned Template",
                "template_type": "project",
                "sections": [
                    {
                        "name": "Backend",
                        "items": [
                            {"name": "Setup database", "ticket_type": "task"},
                            {"name": "Create API", "ticket_type": "feature"},
                        ],
                    },
                    {
                        "name": "Frontend",
                        "items": [
                            {"name": "Create UI", "ticket_type": "task"},
                            {"name": "Add tests", "ticket_type": "task"},
                        ],
                    },
                ],
                "is_active": True,
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main, ["--agent", "surgeon", "templates", "show", "tpl-with-sections"]
        )
        assert result.exit_code == 0
        assert "Sectioned Template" in result.output
        assert "## Backend" in result.output
        assert "  - [task] Setup database" in result.output
        assert "  - [feature] Create API" in result.output
        assert "## Frontend" in result.output
        assert "  - [task] Create UI" in result.output
        assert "  - [task] Add tests" in result.output


class TestTemplateList:
    def test_list_templates_empty(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(method="GET", url=f"{_TEMPLATES_URL}?limit=20", json=[])
        runner = CliRunner()
        result = runner.invoke(main, ["--agent", "surgeon", "templates", "list"])
        assert result.exit_code == 0
        assert "No templates found." in result.output

    def test_list_templates_with_data(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_TEMPLATES_URL}?limit=20",
            json=[
                {
                    "id": "tpl-1",
                    "name": "First Template",
                    "template_type": "project",
                    "category": "architecture",
                    "is_active": True,
                },
                {
                    "id": "tpl-2",
                    "name": "Second Template",
                    "template_type": "task",
                    "category": "development",
                    "is_active": False,
                },
            ],
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--agent", "surgeon", "templates", "list"])
        assert result.exit_code == 0
        assert "First Template" in result.output
        assert "Second Template" in result.output
        assert "architecture" in result.output
        assert "✓" in result.output  # Active template
        assert "—" in result.output  # Inactive template
