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
