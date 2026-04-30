"""Tests for articles domain commands."""

import json

import pytest
from click.testing import CliRunner

from sanctum_cli.cli import main
from sanctum_cli.domains.articles import _normalize_section_heading

_ARTICLES_URL = "https://core.digitalsanctum.com.au/api/articles"


class TestNormalizeSectionHeading:
    """Tests for _normalize_section_heading helper."""

    def test_bare_name_adds_h1_prefix(self):
        assert _normalize_section_heading("Introduction") == "# Introduction"

    def test_bare_name_with_whitespace(self):
        assert _normalize_section_heading("  Introduction  ") == "# Introduction"

    def test_already_normalized_h1_unchanged(self):
        assert _normalize_section_heading("# Introduction") == "# Introduction"

    def test_already_normalized_h2_unchanged(self):
        assert _normalize_section_heading("## Setup") == "## Setup"

    def test_already_normalized_h3_unchanged(self):
        assert _normalize_section_heading("### Details") == "### Details"

    def test_empty_string_returns_hash_with_space(self):
        assert _normalize_section_heading("") == "# "


class TestArticlesUpdateSection:
    """Tests for articles update --section command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def article_file(self, tmp_path):
        f = tmp_path / "content.md"
        f.write_text("New content for section")
        return str(f)

    def test_section_normalizes_bare_name(self, article_file, httpx_mock, mock_agent_tokens):
        httpx_mock.add_response(
            method="PATCH",
            url=f"{_ARTICLES_URL}/ART-001/sections",
            json={"id": "ART-001", "heading": "# Intro"},
        )
        runner = CliRunner()
        cmd = ["--agent", "scribe", "articles", "update", "ART-001",
               "--section", "Intro", "--file", article_file]
        result = runner.invoke(main, cmd)
        assert result.exit_code == 0
        # Check the request body was normalized
        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["heading"] == "# Intro"

    def test_section_passes_through_normalized_name(
        self, article_file, httpx_mock, mock_agent_tokens
    ):
        httpx_mock.add_response(
            method="PATCH",
            url=f"{_ARTICLES_URL}/ART-001/sections",
            json={"id": "ART-001", "heading": "## Setup"},
        )
        runner = CliRunner()
        cmd = ["--agent", "scribe", "articles", "update", "ART-001",
               "--section", "## Setup", "--file", article_file]
        result = runner.invoke(main, cmd)
        assert result.exit_code == 0
        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["heading"] == "## Setup"
