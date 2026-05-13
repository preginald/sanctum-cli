"""Tests for the TicketCreateResolver logic."""

import json

import click
import pytest
from click.testing import CliRunner

from sanctum_cli.cli import main
from sanctum_cli.domains.ticket_resolver import AmbiguousEntity, TicketCreateResolver

_API_BASE = "https://core.digitalsanctum.com.au/api"
_PROJECT_UUID = "11111111-1111-4111-8111-111111111111"
_ACCOUNT_UUID = "22222222-2222-4222-8222-222222222222"
_MILESTONE_UUID = "33333333-3333-4333-8333-333333333333"
_PRODUCT_UUID = "44444444-4444-4444-8444-444444444444"
_PRODUCT2_UUID = "55555555-5555-5555-8555-555555555555"


def _resolver() -> TicketCreateResolver:
    """Build a TicketCreateResolver with a minimal Click context."""
    ctx = click.Context(main, info_name="sanctum")
    ctx.ensure_object(dict)
    ctx.obj["output_json"] = False
    ctx.obj["resolved_agent"] = "surgeon"
    return TicketCreateResolver(ctx)


def _mock_account_inference_project(httpx_mock) -> None:
    """Mock the account-inference GET for a known project UUID."""
    httpx_mock.add_response(
        method="GET",
        url=f"{_API_BASE}/projects/{_PROJECT_UUID}",
        json={"id": _PROJECT_UUID, "name": "My Project", "account_id": _ACCOUNT_UUID},
        is_optional=True,
    )


def _mock_account_inference_product(httpx_mock) -> None:
    """Mock the account-inference GET for a known product UUID."""
    httpx_mock.add_response(
        method="GET",
        url=f"{_API_BASE}/products/{_PRODUCT_UUID}",
        json={"id": _PRODUCT_UUID, "name": "Sanctum CLI", "account_id": _ACCOUNT_UUID},
        is_optional=True,
    )


# ---------------------------------------------------------------------------
# Project resolution
# ---------------------------------------------------------------------------


class TestResolverProject:
    def test_project_uuid_passes_through(self, httpx_mock):
        _mock_account_inference_project(httpx_mock)
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=_PROJECT_UUID,
            milestone_id=None,
            product_ids=None,
            subject="Test ticket",
            description="",
        )
        assert result["project_id"] == _PROJECT_UUID

    def test_project_name_resolves_via_search(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/search?q=My+Project&type=project&limit=10",
            json={
                "results": [
                    {
                        "type": "project",
                        "title": "My Project",
                        "id": _PROJECT_UUID,
                        "score": 0.95,
                    }
                ]
            },
        )
        _mock_account_inference_project(httpx_mock)
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id="My Project",
            milestone_id=None,
            product_ids=None,
            subject="Test",
            description="",
        )
        assert result["project_id"] == _PROJECT_UUID

    def test_unknown_project_raises_error(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/search?q=Nonesuch&type=project&limit=10",
            json={"results": []},
        )
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/projects?limit=100&offset=0",
            json={"projects": []},
            is_optional=True,
        )
        resolver = _resolver()
        with pytest.raises(click.ClickException, match="Project not found"):
            resolver.resolve(
                account_id=None,
                project_id="Nonesuch",
                milestone_id=None,
                product_ids=None,
                subject="Test",
                description="",
            )


# ---------------------------------------------------------------------------
# Milestone resolution
# ---------------------------------------------------------------------------


class TestResolverMilestone:
    def test_milestone_uuid_passes_through(self):
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=None,
            milestone_id=_MILESTONE_UUID,
            product_ids=None,
            subject="Test",
            description="",
        )
        assert result["milestone_id"] == _MILESTONE_UUID

    def test_milestone_name_resolves_with_project(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/milestones?project_id={_PROJECT_UUID}",
            json={"milestones": [{"id": _MILESTONE_UUID, "name": "Phase 2", "status": "active"}]},
        )
        _mock_account_inference_project(httpx_mock)
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=_PROJECT_UUID,
            milestone_id="Phase 2",
            product_ids=None,
            subject="Test",
            description="",
        )
        assert result["milestone_id"] == _MILESTONE_UUID

    def test_milestone_name_requires_project(self):
        resolver = _resolver()
        with pytest.raises(click.ClickException, match="without a project"):
            resolver.resolve(
                account_id=None,
                project_id=None,
                milestone_id="Phase 2",
                product_ids=None,
                subject="Test",
                description="",
            )


# ---------------------------------------------------------------------------
# Product resolution & inference
# ---------------------------------------------------------------------------


class TestResolverProduct:
    def test_product_uuid_passes_through(self, httpx_mock):
        _mock_account_inference_product(httpx_mock)
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=None,
            milestone_id=None,
            product_ids=_PRODUCT_UUID,
            subject="Test",
            description="",
        )
        assert result["product_ids"] == _PRODUCT_UUID

    def test_product_name_resolves(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products?limit=200",
            json={
                "products": [
                    {
                        "id": _PRODUCT_UUID,
                        "name": "Sanctum CLI",
                        "type": "platform",
                        "is_active": True,
                    },
                    {
                        "id": _PRODUCT2_UUID,
                        "name": "Sanctum Forms",
                        "type": "platform",
                        "is_active": True,
                    },
                ]
            },
        )
        _mock_account_inference_product(httpx_mock)
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=None,
            milestone_id=None,
            product_ids="Sanctum CLI",
            subject="Test",
            description="",
        )
        assert result["product_ids"] == _PRODUCT_UUID

    def test_product_inferred_from_subject(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products?limit=100",
            json={
                "products": [
                    {
                        "id": _PRODUCT_UUID,
                        "name": "Sanctum CLI",
                        "type": "platform",
                        "description": "CLI tool for Sanctum Core",
                        "is_active": True,
                    },
                    {
                        "id": _PRODUCT2_UUID,
                        "name": "Sanctum Forms",
                        "type": "platform",
                        "description": "Form builder and submission",
                        "is_active": True,
                    },
                ]
            },
        )
        _mock_account_inference_product(httpx_mock)
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=None,
            milestone_id=None,
            product_ids=None,
            subject="Adding new CLI command for project management",
            description="This is a feature for the Sanctum CLI tool.",
        )
        assert result["product_ids"] == _PRODUCT_UUID

    def test_no_product_inference_when_project_given(self, httpx_mock):
        _mock_account_inference_project(httpx_mock)
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=_PROJECT_UUID,
            milestone_id=None,
            product_ids=None,
            subject="Some ticket with project",
            description="",
        )
        assert result["product_ids"] is None

    def test_ambiguous_product_raises_error(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products?limit=100",
            json={
                "products": [
                    {
                        "id": _PRODUCT_UUID,
                        "name": "Sanctum CLI",
                        "type": "platform",
                        "description": "CLI tool",
                        "is_active": True,
                    },
                    {
                        "id": _PRODUCT2_UUID,
                        "name": "Sanctum Router",
                        "type": "platform",
                        "description": "Router service",
                        "is_active": True,
                    },
                ]
            },
        )
        resolver = _resolver()
        with pytest.raises(AmbiguousEntity, match="Multiple products match"):
            resolver.resolve(
                account_id=None,
                project_id=None,
                milestone_id=None,
                product_ids=None,
                subject="General question about the platform",
                description="Not specific to any product.",
            )


# ---------------------------------------------------------------------------
# Account inference
# ---------------------------------------------------------------------------


class TestResolverAccount:
    def test_account_inferred_from_project(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/projects/{_PROJECT_UUID}",
            json={
                "id": _PROJECT_UUID,
                "name": "My Project",
                "account_id": _ACCOUNT_UUID,
            },
        )
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=_PROJECT_UUID,
            milestone_id=None,
            product_ids=None,
            subject="Test",
            description="",
        )
        assert result["account_id"] == _ACCOUNT_UUID

    def test_account_inferred_from_product(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products/{_PRODUCT_UUID}",
            json={
                "id": _PRODUCT_UUID,
                "name": "Sanctum CLI",
                "account_id": _ACCOUNT_UUID,
            },
        )
        resolver = _resolver()
        result = resolver.resolve(
            account_id=None,
            project_id=None,
            milestone_id=None,
            product_ids=_PRODUCT_UUID,
            subject="Test",
            description="",
        )
        assert result["account_id"] == _ACCOUNT_UUID

    def test_explicit_account_takes_precedence(self):
        other_account = "66666666-6666-4666-8666-666666666666"
        resolver = _resolver()
        result = resolver.resolve(
            account_id=other_account,
            project_id=_PROJECT_UUID,
            milestone_id=None,
            product_ids=None,
            subject="Test",
            description="",
        )
        assert result["account_id"] == other_account


# ---------------------------------------------------------------------------
# Integration tests — full command path with JSON mode
# ---------------------------------------------------------------------------


class TestResolverIntegrationJsonMode:
    def test_json_mode_ambiguous_product_errors(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products?limit=100",
            json={
                "products": [
                    {
                        "id": _PRODUCT_UUID,
                        "name": "Sanctum CLI",
                        "type": "platform",
                        "description": "Tool",
                    },
                    {
                        "id": _PRODUCT2_UUID,
                        "name": "Sanctum Router",
                        "type": "platform",
                        "description": "Router",
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
                "--json",
                "tickets",
                "create",
                "--subject",
                "Platform improvement ticket",
                "--description",
                "Not specific to a product.",
            ],
        )
        assert result.exit_code != 0
        if result.output:
            data = json.loads(result.output)
            assert data.get("entity_type") == "product"
            assert "candidates" in data

    def test_json_mode_known_product_inferred(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products?limit=100",
            json={
                "products": [
                    {
                        "id": _PRODUCT_UUID,
                        "name": "Sanctum CLI",
                        "type": "platform",
                        "description": "CLI tool",
                    },
                ]
            },
        )
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products/{_PRODUCT_UUID}",
            json={
                "id": _PRODUCT_UUID,
                "name": "Sanctum CLI",
                "account_id": _ACCOUNT_UUID,
            },
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{_API_BASE}/tickets",
            json={"id": 99, "subject": "CLI improvement ticket"},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "tickets",
                "create",
                "--subject",
                "CLI improvement ticket",
                "--description",
                "This is a new feature for Sanctum CLI",
                "--ticket-type",
                "feature",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data.get("id") == 99

    def test_json_mode_missing_account_no_project(self, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products?limit=100",
            json={"products": []},
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "tickets",
                "create",
                "--subject",
                "Orphan ticket",
                "--description",
                "No project, no product context.",
            ],
        )
        assert result.exit_code != 0
        if result.output:
            data = json.loads(result.output)
            assert "error" in data


# ---------------------------------------------------------------------------
# Schema inference metadata
# ---------------------------------------------------------------------------


class TestSchemaInference:
    def test_ticket_create_account_id_is_inferable(self):
        from sanctum_cli.assist.schema import build_cli_schema

        schema = build_cli_schema(main)
        cmd = None
        for c in schema.commands:
            if c.path == ("tickets", "create"):
                cmd = c
                break
        assert cmd is not None, "tickets create not found in schema"
        account_param = None
        for p in cmd.parameters:
            if p.name == "account_id":
                account_param = p
                break
        assert account_param is not None, "account_id param not found"
        assert account_param.inferable is True


# ---------------------------------------------------------------------------
# Description file — shell-safe Markdown transport
# ---------------------------------------------------------------------------


class TestDescriptionFile:
    def test_description_file_ignores_shell_special_chars(
        self, httpx_mock, mock_agent_tokens, tmp_path
    ):
        httpx_mock.add_response(
            method="GET",
            url=f"{_API_BASE}/products?limit=100",
            json={"products": []},
        )
        desc_file = tmp_path / "desc.md"
        desc_file.write_text(
            "**Problem**\nThe `AiAssistant` component renders inconsistently.\n"
            "`fixed right-0` should be applied.\n"
            'Contains `backticks`, $(dollar), and "quotes".'
        )
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--agent",
                "surgeon",
                "--json",
                "tickets",
                "create",
                "--subject",
                "Backtick test",
                "--description-file",
                str(desc_file),
                "--ticket-type",
                "bug",
            ],
        )
        assert "command not found" not in result.output
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert "zsh" not in output_lower
