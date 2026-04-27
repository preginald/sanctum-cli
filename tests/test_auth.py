"""Tests for authentication and identity resolution."""

import os

import pytest
from sanctum_client.identity import (
    resolve_agent_token,
    load_agent_tokens,
    AGENT_TOKEN_MAP,
)
from sanctum_cli.config import save_token, load_token


class TestAgentTokenResolution:
    def test_resolve_known_agent(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token("operator")
        assert token == "sntm_op_token"

    def test_resolve_full_agent_name(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token("sanctum-architect")
        assert token == "sntm_arch_token"

    def test_resolve_unknown_agent(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token("nonexistent")
        assert token == ""

    def test_resolve_none_agent(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token(None)
        assert token == ""

    def test_resolve_empty_agent(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token("")
        assert token == ""

    def test_load_agent_tokens_populates_map(self, mock_agent_tokens):
        load_agent_tokens()
        assert "sanctum-operator" in AGENT_TOKEN_MAP
        assert AGENT_TOKEN_MAP["sanctum-operator"] == "sntm_op_token"

    def test_no_tokens_falls_back_gracefully(self, monkeypatch):
        monkeypatch.delenv("SANCTUM_TOKEN_OPERATOR", raising=False)
        monkeypatch.delenv("SANCTUM_TOKEN_ARCHITECT", raising=False)
        load_agent_tokens()
        assert resolve_agent_token("operator") == ""


class TestTokenStorage:
    def test_save_and_load_token(self, temp_home):
        save_token("default", "test_jwt_token_abc")
        loaded = load_token("default")
        assert loaded == "test_jwt_token_abc"

    def test_load_nonexistent_token(self, temp_home):
        loaded = load_token("nonexistent")
        assert loaded is None

    def test_token_file_permissions(self, temp_home):
        from sanctum_cli.config import get_token_file
        save_token("default", "test_token")
        token_file = get_token_file("default")
        mode = token_file.stat().st_mode & 0o777
        assert mode == 0o600


class TestApiBaseResolution:
    def test_default_profile(self):
        from sanctum_cli.config import get_api_base
        assert "digitalsanctum.com.au" in get_api_base("default")

    def test_local_profile(self):
        from sanctum_cli.config import get_api_base
        assert get_api_base("local") == "http://localhost:8000"
