"""Tests for forms domain commands."""

import json
import os
import tempfile

from click.testing import CliRunner

from sanctum_cli.cli import main

_FORMS_URL = "https://forms.digitalsanctum.com.au/api/v1/templates/"
_ACCOUNT_ID = "a1b2c3d4-0001-4000-8000-000000000001"


class TestFormsTemplatesCreate:
    def test_create_template_minimal(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_FORMS_URL,
            json={"id": "template-uuid", "name": "Contact Form", "version": 1},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "create",
                "--name",
                "Contact Form",
            ],
        )
        assert result.exit_code == 0
        assert "Form template created" in result.output
        assert "template-uuid" in result.output

    def test_create_template_with_fields(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_FORMS_URL,
            json={"id": "template-uuid", "name": "Contact Form", "version": 1},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "create",
                "--name",
                "Contact Form",
                "--field-schema",
                '[{"name":"email","label":"Email","type":"email","required":true}]',
            ],
        )
        assert result.exit_code == 0
        assert "Form template created" in result.output

    def test_create_template_with_notification(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_FORMS_URL,
            json={"id": "template-uuid", "name": "Contact Form", "version": 1},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "create",
                "--name",
                "Contact Form",
                "--notification-email",
                "admin@example.com",
                "--notify-template-id",
                "form-submission",
            ],
        )
        assert result.exit_code == 0
        assert "Form template created" in result.output

    def test_create_template_both_schema_args(self, mock_agent_tokens):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("[]")
            tmp_path = f.name
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--agent",
                    "surgeon",
                    "forms",
                    "--account-id",
                    _ACCOUNT_ID,
                    "templates",
                    "create",
                    "--name",
                    "Test",
                    "--field-schema",
                    "[]",
                    "--field-schema-file",
                    tmp_path,
                ],
            )
            assert result.exit_code == 0
            assert "Provide either --field-schema or --field-schema-file" in result.output
        finally:
            os.unlink(tmp_path)

    def test_create_template_both_settings_args(self, mock_agent_tokens):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write('{"success_message":"OK"}')
            tmp_path = f.name
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--agent",
                    "surgeon",
                    "forms",
                    "--account-id",
                    _ACCOUNT_ID,
                    "templates",
                    "create",
                    "--name",
                    "Test",
                    "--settings",
                    "{}",
                    "--settings-file",
                    tmp_path,
                ],
            )
            assert result.exit_code == 0
            assert "Provide either --settings or --settings-file" in result.output
        finally:
            os.unlink(tmp_path)

    def test_create_template_invalid_json(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "create",
                "--name",
                "Test",
                "--field-schema",
                "not-json",
            ],
        )
        assert result.exit_code == 0
        assert "Invalid --field-schema JSON" in result.output

    def test_create_template_invalid_settings_json(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "create",
                "--name",
                "Test",
                "--settings",
                "not-json",
            ],
        )
        assert result.exit_code == 0
        assert "Invalid --settings JSON" in result.output

    def test_create_template_from_file(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_FORMS_URL,
            json={"id": "template-uuid", "name": "File Template", "version": 1},
        )
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump([{"name": "name", "label": "Name", "type": "text"}], f)
            tmp_path = f.name
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--agent",
                    "surgeon",
                    "forms",
                    "--account-id",
                    _ACCOUNT_ID,
                    "templates",
                    "create",
                    "--name",
                    "File Template",
                    "--field-schema-file",
                    tmp_path,
                ],
            )
            assert result.exit_code == 0
            assert "Form template created" in result.output
        finally:
            os.unlink(tmp_path)

    def test_create_template_with_settings(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_FORMS_URL,
            json={"id": "template-uuid", "name": "Settings Template", "version": 1},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "create",
                "--name",
                "Settings Template",
                "--settings",
                '{"success_message":"Thanks!","auth_mode":"public"}',
            ],
        )
        assert result.exit_code == 0
        assert "Form template created" in result.output

    def test_create_template_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=_FORMS_URL,
            json={"id": "template-uuid", "name": "JSON Template", "version": 1},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "create",
                "--name",
                "JSON Template",
            ],
        )
        assert result.exit_code == 0
        assert '"name": "JSON Template"' in result.output


class TestFormsTemplatesManage:
    def test_list_templates(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_FORMS_URL}?limit=20",
            json={
                "templates": [
                    {
                        "id": "tpl-uuid",
                        "name": "Contact Form",
                        "version": 1,
                        "notify_template_id": "form-submission",
                    }
                ]
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "list",
            ],
        )

        assert result.exit_code == 0
        assert "Form Templates" in result.output
        assert "tpl-uuid" in result.output
        assert "Contact Form" in result.output

    def test_list_templates_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_FORMS_URL}?limit=10",
            json=[{"id": "tpl-uuid", "name": "JSON Template"}],
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "list",
                "--limit",
                "10",
            ],
        )

        assert result.exit_code == 0
        assert '"name": "JSON Template"' in result.output
        assert "Form Templates" not in result.output

    def test_show_template(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_FORMS_URL}tpl-uuid",
            json={
                "id": "tpl-uuid",
                "name": "Contact Form",
                "version": 1,
                "field_schema": [{"name": "email", "type": "email"}],
                "settings": {"success_message": "Thanks"},
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "show",
                "tpl-uuid",
            ],
        )

        assert result.exit_code == 0
        assert "Form Template: Contact Form" in result.output
        assert "Field Schema" in result.output
        assert '"email"' in result.output

    def test_update_template(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url=f"{_FORMS_URL}tpl-uuid",
            json={"id": "tpl-uuid", "name": "Updated Form"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "update",
                "tpl-uuid",
                "--name",
                "Updated Form",
                "--field-schema",
                '[{"name":"email","type":"email"}]',
                "--notification-email",
                "admin@example.com",
            ],
        )

        assert result.exit_code == 0
        assert "Form template tpl-uuid updated" in result.output
        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["name"] == "Updated Form"
        assert body["field_schema"] == [{"name": "email", "type": "email"}]
        assert body["notification_emails"] == ["admin@example.com"]

    def test_update_template_no_fields(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "update",
                "tpl-uuid",
            ],
        )

        assert result.exit_code == 0
        assert "Nothing to update" in result.output

    def test_delete_template(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(method="DELETE", url=f"{_FORMS_URL}tpl-uuid", status_code=204)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "delete",
                "tpl-uuid",
            ],
            input="y\n",
        )

        assert result.exit_code == 0
        assert "Form template tpl-uuid deleted" in result.output


class TestFormsTemplatesDeploy:
    _DEPLOY_URL = "https://forms.digitalsanctum.com.au/api/v1/templates/tpl-uuid/deploy"

    def test_deploy_minimal(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=self._DEPLOY_URL,
            json={
                "id": "inst-uuid",
                "name": "Contact Form",
                "slug": "contact-form",
                "status": "active",
                "endpoint_id": "ep-uuid",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "deploy",
                "tpl-uuid",
                "--name",
                "Contact Form",
            ],
        )
        assert result.exit_code == 0
        assert "Form instance deployed" in result.output
        assert "inst-uuid" in result.output
        assert "contact-form" in result.output

    def test_deploy_with_all_options(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=self._DEPLOY_URL,
            json={
                "id": "inst-uuid",
                "name": "Discovery Call",
                "slug": "discovery-call",
                "status": "active",
                "endpoint_id": "ep-uuid",
                "project_id": "proj-uuid",
                "allowed_origins": ["https://example.com"],
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "deploy",
                "tpl-uuid",
                "--name",
                "Discovery Call",
                "--slug",
                "discovery-call",
                "--project-id",
                "proj-uuid",
                "--allowed-origin",
                "https://example.com",
                "--status",
                "active",
            ],
        )
        assert result.exit_code == 0
        assert "Form instance deployed" in result.output

    def test_deploy_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url=self._DEPLOY_URL,
            json={
                "id": "inst-uuid",
                "name": "JSON Instance",
                "slug": "json-instance",
                "status": "active",
                "endpoint_id": "ep-uuid",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "templates",
                "deploy",
                "tpl-uuid",
                "--name",
                "JSON Instance",
            ],
        )
        assert result.exit_code == 0
        assert '"name": "JSON Instance"' in result.output


class TestFormsSubmissionsDelete:
    _DELETE_URL = "https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid"

    def test_delete_submission(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="DELETE",
            url=self._DELETE_URL,
            status_code=204,
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "delete",
                "sub-uuid",
            ],
            input="y\n",
        )
        assert result.exit_code == 0
        assert "Submission sub-uuid deleted" in result.output

    def test_update_submission_fields(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url="https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid",
            json={"id": "sub-uuid", "payload": {"date": "29-04-2026", "status": "new"}},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "update",
                "sub-uuid",
                "--field",
                "date=29-04-2026",
            ],
        )
        assert result.exit_code == 0
        assert "Submission sub-uuid updated" in result.output

    def test_update_submission_payload_file(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url="https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid",
            json={"id": "sub-uuid", "payload": {"date": "29-04-2026", "status": "new"}},
        )
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"date": "29-04-2026", "success_criteria": "Updated text"}, f)
            tmp_path = f.name
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--agent",
                    "surgeon",
                    "forms",
                    "--account-id",
                    _ACCOUNT_ID,
                    "submissions",
                    "update",
                    "sub-uuid",
                    "--payload-file",
                    tmp_path,
                ],
            )
            assert result.exit_code == 0
            assert "Submission sub-uuid updated" in result.output
        finally:
            os.unlink(tmp_path)

    def test_update_submission_json_output(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url="https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid",
            json={"id": "sub-uuid", "payload": {"date": "29-04-2026"}},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "update",
                "sub-uuid",
                "--field",
                "date=29-04-2026",
            ],
        )
        assert result.exit_code == 0
        assert '"date": "29-04-2026"' in result.output

    def test_update_submission_invalid_field(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "update",
                "sub-uuid",
                "--field",
                "badformat",
            ],
        )
        assert result.exit_code == 0
        assert "Invalid field format" in result.output

    def test_update_submission_no_fields(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "update",
                "sub-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Nothing to update" in result.output

    def test_update_submission_contact_id(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url="https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid",
            json={"id": "sub-uuid", "core_contact_id": "contact-uuid"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "update",
                "sub-uuid",
                "--contact-id",
                "contact-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Submission sub-uuid updated" in result.output

    def test_update_submission_ticket_id(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url="https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid",
            json={"id": "sub-uuid", "core_ticket_id": "ticket-uuid"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "update",
                "sub-uuid",
                "--ticket-id",
                "ticket-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Submission sub-uuid updated" in result.output

    def test_update_submission_submitted_by(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url="https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid",
            json={"id": "sub-uuid", "submitted_by_contact_id": "contact-uuid"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "update",
                "sub-uuid",
                "--submitted-by",
                "contact-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Submission sub-uuid updated" in result.output

    def test_update_submission_payload_and_contact_id(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url="https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid",
            json={
                "id": "sub-uuid",
                "payload": {"status": "new"},
                "core_contact_id": "contact-uuid",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "update",
                "sub-uuid",
                "--field",
                "status=new",
                "--contact-id",
                "contact-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Submission sub-uuid updated" in result.output

    def test_delete_submission_abort(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "delete",
                "sub-uuid",
            ],
            input="n\n",
        )
        assert result.exit_code != 0


class TestFormsSubmissionsShareToken:
    def test_share_token(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="POST",
            url="https://forms.digitalsanctum.com.au/api/v1/submissions/sub-uuid/share-token",
            json={
                "token": "abc123",
                "share_url": "https://forms.digitalsanctum.com.au/api/v1/public/s/abc123",
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "forms",
                "--account-id",
                _ACCOUNT_ID,
                "submissions",
                "share-token",
                "sub-uuid",
            ],
        )
        assert result.exit_code == 0
        assert "Share link:" in result.output
        assert "abc123" in result.output
