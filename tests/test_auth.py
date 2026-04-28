"""Tests for authentication, identity resolution, and identity map."""

from sanctum_cli.config import load_token, load_user_token, save_token, save_user_token
from sanctum_cli.identity_map import check_agent_for, suggest_agent_for
from sanctum_client.identity import (
    AGENT_TOKEN_MAP,
    load_agent_tokens,
    resolve_agent_token,
)


class TestAgentTokenResolution:
    def test_resolve_known_agent(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token("surgeon")
        assert token == "sntm_surgeon_token"

    def test_resolve_full_agent_name(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token("sanctum-architect")
        assert token == "sntm_arch_token"

    def test_resolve_guardian(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token("guardian")
        assert token == "sntm_guardian_token"

    def test_resolve_guardian_full_name(self, mock_agent_tokens):
        load_agent_tokens()
        token = resolve_agent_token("sanctum-guardian")
        assert token == "sntm_guardian_token"

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
        assert "sanctum-surgeon" in AGENT_TOKEN_MAP
        assert AGENT_TOKEN_MAP["sanctum-surgeon"] == "sntm_surgeon_token"
        assert "sanctum-guardian" in AGENT_TOKEN_MAP

    def test_no_tokens_falls_back_gracefully(self, monkeypatch):
        monkeypatch.delenv("SANCTUM_TOKEN_OPERATOR", raising=False)
        monkeypatch.delenv("SANCTUM_TOKEN_ARCHITECT", raising=False)
        monkeypatch.delenv("SANCTUM_TOKEN_GUARDIAN", raising=False)
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


class TestUserTokenStorage:
    def test_save_and_load_user_token(self, temp_home):
        save_user_token("peter@test.com", "sntm_pat_abc123")
        loaded = load_user_token("peter@test.com")
        assert loaded == "sntm_pat_abc123"

    def test_user_token_load_missing(self, temp_home):
        loaded = load_user_token("nobody@test.com")
        assert loaded is None

    def test_user_token_file_permissions(self, temp_home):
        from sanctum_cli.config import USER_TOKENS_DIR
        save_user_token("peter@test.com", "sntm_pat_secure")
        files = list(USER_TOKENS_DIR.iterdir())
        assert len(files) == 1
        mode = files[0].stat().st_mode & 0o777
        assert mode == 0o600


class TestIdentityMap:

    def test_agent_check_ok_when_matches(self, mock_agent_tokens):
        result = check_agent_for("tickets", "create", "surgeon")
        assert result is None

    def test_agent_check_operator_unknown(self, mock_agent_tokens):
        result = check_agent_for("tickets", "create", "operator")
        assert result is not None
        assert "typically uses" in result.lower()

    def test_agent_check_architect_allowed_on_resolve(self, mock_agent_tokens):
        result = check_agent_for("tickets", "resolve", "architect")
        assert result is None

    def test_agent_check_none_expected_ok(self, mock_agent_tokens):
        result = check_agent_for("tickets", "list", None)
        assert result is None

    def test_agent_check_warns_on_mismatch(self, mock_agent_tokens):
        result = check_agent_for("tickets", "create", "scribe")
        assert result is not None
        assert "typically uses" in result

    def test_suggest_agent_for_create(self):
        assert suggest_agent_for("tickets", "create") == "surgeon"

    def test_suggest_agent_for_resolve(self):
        assert suggest_agent_for("tickets", "resolve") == "architect"

    def test_suggest_agent_for_show(self):
        assert suggest_agent_for("tickets", "show") is None


class TestApiBaseResolution:
    def test_default_profile(self):
        from sanctum_cli.config import get_api_base
        assert "digitalsanctum.com.au" in get_api_base("default")

    def test_local_profile(self):
        from sanctum_cli.config import get_api_base
        assert get_api_base("local") == "http://localhost:8000"
