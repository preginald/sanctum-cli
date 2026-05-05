"""Tests for contacts domain commands."""

from click.testing import CliRunner

from sanctum_cli.cli import main


class TestContactsInvite:
    def test_invite_contact(self, monkeypatch, mock_agent_tokens):
        requests = []

        def fake_post(path, json=None):
            requests.append((path, json))
            return {"status": "invited", "email": "louise@example.com"}

        monkeypatch.setattr("sanctum_cli.domains.contacts.post", fake_post)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "contacts",
                "invite",
                "9bbdb22a-a067-44ef-83c0-2e4cd2550522",
            ],
        )

        assert result.exit_code == 0
        assert requests == [("/contacts/9bbdb22a-a067-44ef-83c0-2e4cd2550522/invite", {})]
        assert "Portal invite sent to louise@example.com" in result.output
        assert "invited" in result.output

    def test_invite_contact_json_output(self, monkeypatch, mock_agent_tokens):
        def fake_post(path, json=None):
            return {"status": "invited", "email": "louise@example.com"}

        monkeypatch.setattr("sanctum_cli.domains.contacts.post", fake_post)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "--json", "contacts", "invite", "contact-uuid"],
        )

        assert result.exit_code == 0
        assert '"status": "invited"' in result.output
        assert '"email": "louise@example.com"' in result.output

    def test_invite_contact_validation_error(self, monkeypatch, mock_agent_tokens):
        def fake_post(path, json=None):
            return {"error": True, "status_code": 422, "detail": "Contact has no email address"}

        monkeypatch.setattr("sanctum_cli.domains.contacts.post", fake_post)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "contacts", "invite", "contact-uuid"],
        )

        assert result.exit_code == 1
        assert "Contact has no email address" in result.output


class TestContactsSetPassword:
    def test_set_contact_password(self, monkeypatch, mock_agent_tokens):
        requests = []

        def fake_post(path, json=None):
            requests.append((path, json))
            return {"status": "password_set", "email": "louise@example.com"}

        monkeypatch.setattr("sanctum_cli.domains.contacts.post", fake_post)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "contacts", "set-password", "contact-uuid"],
            input="client-safe-pass\nclient-safe-pass\n",
        )

        assert result.exit_code == 0
        assert requests == [("/contacts/contact-uuid/password", {"password": "client-safe-pass"})]
        assert "Portal password set for louise@example.com" in result.output
        assert "client-safe-pass" not in result.output

    def test_set_contact_password_validation_error(self, monkeypatch, mock_agent_tokens):
        def fake_post(path, json=None):
            return {"error": True, "status_code": 422, "detail": "Password is too short"}

        monkeypatch.setattr("sanctum_cli.domains.contacts.post", fake_post)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "contacts", "set-password", "contact-uuid"],
            input="short-pass\nshort-pass\n",
        )

        assert result.exit_code == 1
        assert "Password is too short" in result.output


class TestContactsUpdate:
    def test_update_contact(self, monkeypatch, mock_agent_tokens):
        requests = []

        def fake_put(path, json=None):
            requests.append((path, json))
            return {
                "id": "contact-uuid",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "phone": "+61 400 000 000",
                "job_title": "Engineer",
                "company_name": "Acme",
            }

        monkeypatch.setattr("sanctum_cli.domains.contacts.put", fake_put)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "contacts",
                "update",
                "contact-uuid",
                "--first-name",
                "Jane",
                "--last-name",
                "Doe",
                "--email",
                "jane@example.com",
                "--phone",
                "+61 400 000 000",
                "--job-title",
                "Engineer",
                "--company-name",
                "Acme",
            ],
        )

        assert result.exit_code == 0
        assert requests == [
            (
                "/contacts/contact-uuid",
                {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@example.com",
                    "phone": "+61 400 000 000",
                    "job_title": "Engineer",
                    "company_name": "Acme",
                },
            )
        ]
        assert "Contact contact-uuid updated" in result.output
        assert "jane@example.com" in result.output

    def test_update_contact_json_output(self, monkeypatch, mock_agent_tokens):
        def fake_put(path, json=None):
            return {"id": "contact-uuid", "first_name": "Jane", "email": "jane@example.com"}

        monkeypatch.setattr("sanctum_cli.domains.contacts.put", fake_put)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "contacts",
                "update",
                "contact-uuid",
                "--email",
                "jane@example.com",
            ],
        )

        assert result.exit_code == 0
        assert '"id": "contact-uuid"' in result.output
        assert '"email": "jane@example.com"' in result.output

    def test_update_contact_validation_error(self, monkeypatch, mock_agent_tokens):
        def fake_put(path, json=None):
            return {"error": True, "status_code": 422, "detail": "Invalid email address"}

        monkeypatch.setattr("sanctum_cli.domains.contacts.put", fake_put)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "contacts", "update", "contact-uuid", "--email", "bad-email"],
        )

        assert result.exit_code == 0  # print_error path
        assert "Invalid email address" in result.output

    def test_update_contact_primary_contact(self, monkeypatch, mock_agent_tokens):
        requests = []

        def fake_put(path, json=None):
            requests.append((path, json))
            return {
                "id": "contact-uuid",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "is_primary_contact": True,
            }

        monkeypatch.setattr("sanctum_cli.domains.contacts.put", fake_put)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "contacts",
                "update",
                "contact-uuid",
                "--primary-contact",
            ],
        )

        assert result.exit_code == 0
        assert requests == [
            (
                "/contacts/contact-uuid",
                {"is_primary_contact": True},
            )
        ]
        assert "Contact contact-uuid updated" in result.output
        assert "True" in result.output

    def test_update_contact_no_fields(self, mock_agent_tokens):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "contacts", "update", "contact-uuid"],
        )

        assert result.exit_code == 0
        assert "Nothing to update. Provide at least one field." in result.output


class TestContactsProvisionCmsSso:
    def test_provision_cms_sso(self, monkeypatch, mock_agent_tokens):
        requests = []

        def fake_put(path, json=None):
            requests.append((path, json))
            return {
                "id": "contact-uuid",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "portal_access": True,
                "provisioning_result": "cms_sso_ok",
            }

        monkeypatch.setattr("sanctum_cli.domains.contacts.put", fake_put)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "contacts", "provision-cms-sso", "contact-uuid"],
        )

        assert result.exit_code == 0
        assert requests == [("/contacts/contact-uuid", {"provision_cms_sso": True})]
        assert "CMS SSO provisioned for contact: contact-uuid" in result.output
        assert "cms_sso_ok" in result.output

    def test_provision_cms_sso_json_output(self, monkeypatch, mock_agent_tokens):
        def fake_put(path, json=None):
            return {
                "id": "contact-uuid",
                "email": "jane@example.com",
                "provisioning_result": "cms_sso_ok",
            }

        monkeypatch.setattr("sanctum_cli.domains.contacts.put", fake_put)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "--json", "contacts", "provision-cms-sso", "contact-uuid"],
        )

        assert result.exit_code == 0
        assert '"id": "contact-uuid"' in result.output
        assert '"provisioning_result": "cms_sso_ok"' in result.output

    def test_provision_cms_sso_error(self, monkeypatch, mock_agent_tokens):
        def fake_put(path, json=None):
            return {"error": True, "status_code": 422, "detail": "Contact not found"}

        monkeypatch.setattr("sanctum_cli.domains.contacts.put", fake_put)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--agent", "surgeon", "contacts", "provision-cms-sso", "contact-uuid"],
        )

        assert result.exit_code == 0  # print_error path
        assert "Contact not found" in result.output
