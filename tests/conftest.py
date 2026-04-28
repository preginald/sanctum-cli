"""Shared test fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_home(monkeypatch):
    """Redirect ~/.sanctum to a temp directory."""
    with tempfile.TemporaryDirectory() as tmp:
        sanctum_dir = Path(tmp) / ".sanctum"
        monkeypatch.setattr("sanctum_cli.config.DEFAULT_CONFIG_DIR", sanctum_dir)
        monkeypatch.setattr("sanctum_cli.config.DEFAULT_TOKENS_DIR", sanctum_dir / "tokens")
        monkeypatch.setattr("sanctum_cli.config.USER_TOKENS_DIR", sanctum_dir / "users")
        sanctum_dir.mkdir(parents=True, exist_ok=True)
        (sanctum_dir / "tokens").mkdir(exist_ok=True)
        (sanctum_dir / "users").mkdir(exist_ok=True)
        yield sanctum_dir


@pytest.fixture
def mock_api_token(monkeypatch):
    """Set a test API token."""
    token = "sntm_test_token_12345"
    monkeypatch.setenv("SANCTUM_API_TOKEN", token)
    return token


@pytest.fixture
def mock_agent_tokens(monkeypatch):
    """Set test agent tokens."""
    tokens = {
        "SANCTUM_TOKEN_ARCHITECT": "sntm_arch_token",
        "SANCTUM_TOKEN_SURGEON": "sntm_surgeon_token",
        "SANCTUM_TOKEN_SCRIBE": "sntm_scribe_token",
        "SANCTUM_TOKEN_SENTINEL": "sntm_sentinel_token",
        "SANCTUM_TOKEN_GUARDIAN": "sntm_guardian_token",
    }
    for k, v in tokens.items():
        monkeypatch.setenv(k, v)
    return tokens


@pytest.fixture(autouse=True)
def clean_client():
    """Reset the HTTP client between tests."""
    yield
    from sanctum_client.client import close_client
    close_client()
