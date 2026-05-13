"""Tests for proactive token lifecycle management."""

import json
import os
import time

import pytest

from sanctum_cli.token_provider import (
    REFRESH_MARGIN_S,
    RouterTokenProvider,
    TokenExpiredError,
    TokenUnavailableError,
    _decode_jwt_payload,
    _jwt_expired,
    _jwt_expiry,
    has_router_token_source,
)


def _make_jwt(exp_offset: int = 3600) -> str:
    import base64

    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"exp": int(time.time()) + exp_offset, "sub": "test"}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


class TestJwtHelpers:
    def test_decode_jwt_payload(self):
        token = _make_jwt(3600)
        payload = _decode_jwt_payload(token)
        assert "exp" in payload
        assert payload["sub"] == "test"

    def test_decode_malformed_jwt(self):
        assert _decode_jwt_payload("not.a.jwt") == {}

    def test_decode_empty_string(self):
        assert _decode_jwt_payload("") == {}

    def test_jwt_expiry_returns_exp(self):
        token = _make_jwt(3600)
        exp = _jwt_expiry(token)
        assert exp is not None
        assert exp > time.time()

    def test_jwt_expiry_missing(self):
        assert _jwt_expiry("abc.eyJzdWIiOiJ0ZXN0In0=.sig") is None

    def test_jwt_expired_within_margin(self):
        token = _make_jwt(exp_offset=REFRESH_MARGIN_S - 10)
        assert _jwt_expired(token) is True

    def test_jwt_not_expired(self):
        token = _make_jwt(exp_offset=REFRESH_MARGIN_S + 60)
        assert _jwt_expired(token) is False

    def test_jwt_expired_past(self):
        token = _make_jwt(exp_offset=-100)
        assert _jwt_expired(token) is True

    def test_jwt_expired_non_jwt(self):
        assert _jwt_expired("not-a-jwt") is True


class TestRouterTokenProviderExplicitToken:
    def test_get_token_returns_valid_explicit(self):
        token = _make_jwt(3600)
        provider = RouterTokenProvider(explicit_token=token)
        assert provider.get_token() == token

    def test_get_token_raises_on_expired_explicit(self):
        token = _make_jwt(exp_offset=-100)
        provider = RouterTokenProvider(explicit_token=token)
        with pytest.raises(TokenExpiredError, match="expired"):
            provider.get_token()

    def test_get_token_caches_in_memory(self):
        token = _make_jwt(3600)
        provider = RouterTokenProvider(explicit_token=token)
        first = provider.get_token()
        second = provider.get_token()
        assert first == second
        # Second call should not re-validate
        assert provider.get_token() == token

    def test_force_refresh_fails_with_explicit_only(self):
        token = _make_jwt(3600)
        provider = RouterTokenProvider(explicit_token=token)
        provider.get_token()  # sets current_token
        with pytest.raises(TokenUnavailableError, match="no refresh mechanism"):
            provider.force_refresh()


class TestRouterTokenProviderCache:
    def test_get_token_from_cache(self, monkeypatch, tmp_path):
        token = _make_jwt(3600)
        cache_dir = tmp_path / ".sanctum"
        cache_dir.mkdir()
        cache_file = cache_dir / "router-token-cache.json"
        cache_file.write_text(json.dumps({"access_token": token}))
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)

        provider = RouterTokenProvider()
        assert provider.get_token() == token

    def test_get_token_expired_cache_no_refresh(self, monkeypatch, tmp_path):
        token = _make_jwt(exp_offset=-100)
        cache_dir = tmp_path / ".sanctum"
        cache_dir.mkdir()
        cache_file = cache_dir / "router-token-cache.json"
        cache_file.write_text(json.dumps({"access_token": token}))
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)
        monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_ID", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("OIDC_CLIENT_ID", raising=False)
        monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)

        provider = RouterTokenProvider()
        with pytest.raises(TokenUnavailableError, match="No Router token available"):
            provider.get_token()

    def test_cache_file_permissions(self, monkeypatch, tmp_path):
        """Verify cache file is created with 0600."""

        cache_dir = tmp_path / ".sanctum"
        cache_dir.mkdir()
        cache_file = cache_dir / "router-token-cache.json"
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)

        provider = RouterTokenProvider()
        provider._write_cache({"access_token": "test"})
        assert cache_file.exists()
        mode = os.stat(cache_file).st_mode & 0o777
        assert mode == 0o600

    def test_get_token_refreshes_via_oidc(self, monkeypatch, tmp_path, httpx_mock):
        expired = _make_jwt(exp_offset=-100)
        fresh = _make_jwt(3600)
        cache_dir = tmp_path / ".sanctum"
        cache_dir.mkdir()
        cache_file = cache_dir / "router-token-cache.json"
        cache_file.write_text(json.dumps({"access_token": expired, "refresh_token": "rt1"}))
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)

        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_ID", "test-client")
        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_SECRET", "test-secret")

        httpx_mock.add_response(
            method="POST",
            url="https://auth.digitalsanctum.com.au/oauth/token",
            json={"access_token": fresh, "refresh_token": "rt2"},
        )

        provider = RouterTokenProvider()
        result = provider.get_token()
        assert result == fresh
        assert provider._refresh_token == "rt2"

    def test_force_refresh_uses_refresh_token(self, monkeypatch, tmp_path, httpx_mock):
        expired = _make_jwt(exp_offset=-100)
        fresh = _make_jwt(3600)
        cache_dir = tmp_path / ".sanctum"
        cache_dir.mkdir()
        cache_file = cache_dir / "router-token-cache.json"
        cache_file.write_text(json.dumps({"access_token": expired, "refresh_token": "rt1"}))
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)

        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_ID", "test-client")
        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_SECRET", "test-secret")

        httpx_mock.add_response(
            method="POST",
            url="https://auth.digitalsanctum.com.au/oauth/token",
            json={"access_token": fresh, "refresh_token": "rt2"},
        )

        provider = RouterTokenProvider()
        provider._refresh_token = "rt1"
        result = provider.force_refresh()
        assert result == fresh


class TestRouterTokenProviderClientCredentials:
    def test_get_token_uses_client_credentials(self, monkeypatch, tmp_path, httpx_mock):
        token = _make_jwt(3600)
        cache_dir = tmp_path / ".sanctum"
        cache_dir.mkdir()
        cache_file = cache_dir / "router-token-cache.json"
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)

        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_ID", "test-client")
        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_SECRET", "test-secret")

        httpx_mock.add_response(
            method="POST",
            url="https://auth.digitalsanctum.com.au/oauth/token",
            json={"access_token": token, "refresh_token": "rt-new"},
        )

        provider = RouterTokenProvider()
        result = provider.get_token()
        assert result == token
        assert provider._refresh_token == "rt-new"
        # Verify cache was written
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text())
        assert cached["access_token"] == token


class TestHasRouterTokenSource:
    def test_returns_true_with_env_var(self, monkeypatch):
        monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", "test")
        assert has_router_token_source() is True

    def test_returns_true_with_jwt_fallback(self, monkeypatch):
        monkeypatch.delenv("SANCTUM_ROUTER_TOKEN", raising=False)
        monkeypatch.setenv("SANCTUM_ROUTER_JWT", "test-jwt")
        assert has_router_token_source() is True

    def test_returns_true_with_cache(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SANCTUM_ROUTER_TOKEN", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_JWT", raising=False)
        cache_file = tmp_path / "router-token-cache.json"
        cache_file.write_text("{}")
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)
        assert has_router_token_source() is True

    def test_returns_true_with_oidc_creds(self, monkeypatch):
        monkeypatch.delenv("SANCTUM_ROUTER_TOKEN", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_JWT", raising=False)
        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_ID", "cid")
        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_SECRET", "csec")
        assert has_router_token_source() is True

    def test_returns_false_with_no_source(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SANCTUM_ROUTER_TOKEN", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_JWT", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_ID", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("OIDC_CLIENT_ID", raising=False)
        monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)
        cache_file = tmp_path / "router-token-cache.json"
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)
        assert has_router_token_source() is False


class TestRouterClientWithProvider:
    """Integration tests for RouterClient using a TokenProvider."""

    def test_interpret_uses_provider_token(self, monkeypatch, httpx_mock):
        from sanctum_cli.assist.router_client import RouterClient, build_router_interpret_request

        token = _make_jwt(3600)
        provider = RouterTokenProvider(explicit_token=token)

        httpx_mock.add_response(
            method="POST",
            url="https://router.example.test/v1/cli-interpret",
            json={
                "status": "interpreted",
                "confidence": 0.98,
                "match_type": "exact",
                "inferred_intent": "test",
                "operation_plan": [],
                "needs_confirmation": False,
                "message": "ok",
            },
        )

        client = RouterClient(base_url="https://router.example.test", token_provider=provider)
        request = build_router_interpret_request(
            mode="natural_language", intent="test", calling_agent="surgeon"
        )
        response = client.interpret(request)
        assert response.status == "interpreted"

        sent = httpx_mock.get_request()
        assert sent.headers["Authorization"] == f"Bearer {token}"

    def test_interpret_retries_on_401_with_force_refresh(self, monkeypatch, tmp_path, httpx_mock):
        from sanctum_cli.assist.router_client import RouterClient, build_router_interpret_request

        expired = _make_jwt(exp_offset=-100)
        fresh = _make_jwt(3600)

        cache_dir = tmp_path / ".sanctum"
        cache_dir.mkdir()
        cache_file = cache_dir / "router-token-cache.json"
        cache_file.write_text(json.dumps({"access_token": expired, "refresh_token": "rt1"}))
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)
        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_ID", "test-client")
        monkeypatch.setenv("SANCTUM_ROUTER_CLIENT_SECRET", "test-secret")

        # First call: get_token refreshes expired cache token via OIDC
        httpx_mock.add_response(
            method="POST",
            url="https://auth.digitalsanctum.com.au/oauth/token",
            json={"access_token": fresh, "refresh_token": "rt2"},
        )
        # Router returns 401 first time
        httpx_mock.add_response(
            method="POST",
            url="https://router.example.test/v1/cli-interpret",
            status_code=401,
            json={"error": "Unauthorized"},
        )
        # force_refresh calls _do_refresh with the new refresh_token
        httpx_mock.add_response(
            method="POST",
            url="https://auth.digitalsanctum.com.au/oauth/token",
            json={"access_token": fresh, "refresh_token": "rt3"},
        )
        # After force refresh succeeds, router retry accepts
        httpx_mock.add_response(
            method="POST",
            url="https://router.example.test/v1/cli-interpret",
            json={
                "status": "interpreted",
                "confidence": 0.99,
                "match_type": "exact",
                "inferred_intent": "retried",
                "operation_plan": [],
                "needs_confirmation": False,
                "message": "ok after retry",
            },
        )

        provider = RouterTokenProvider()
        client = RouterClient(base_url="https://router.example.test", token_provider=provider)
        request = build_router_interpret_request(
            mode="natural_language", intent="test", calling_agent="surgeon"
        )

        response = client.interpret(request)
        assert response.status == "interpreted"
        assert response.inferred_intent == "retried"

    def test_interpret_401_without_provider_raises(self, httpx_mock):
        from sanctum_cli.assist.router_client import (
            RouterClient,
            RouterClientError,
            build_router_interpret_request,
        )

        httpx_mock.add_response(
            method="POST",
            url="https://router.example.test/v1/cli-interpret",
            status_code=401,
        )

        client = RouterClient(base_url="https://router.example.test", token="old-token")
        request = build_router_interpret_request(
            mode="natural_language", intent="test", calling_agent="surgeon"
        )

        with pytest.raises(RouterClientError) as exc:
            client.interpret(request)
        assert exc.value.status_code == 401

    def test_interpret_uses_token_fallback_when_no_provider(self, httpx_mock):
        from sanctum_cli.assist.router_client import (
            RouterClient,
            build_router_interpret_request,
        )

        httpx_mock.add_response(
            method="POST",
            url="https://router.example.test/v1/cli-interpret",
            json={
                "status": "interpreted",
                "confidence": 0.98,
                "match_type": "exact",
                "inferred_intent": "fallback",
                "operation_plan": [],
                "needs_confirmation": False,
                "message": "ok",
            },
        )

        client = RouterClient(base_url="https://router.example.test", token="legacy-token")
        request = build_router_interpret_request(
            mode="natural_language", intent="test", calling_agent="surgeon"
        )
        response = client.interpret(request)
        assert response.status == "interpreted"

        sent = httpx_mock.get_request()
        assert sent.headers["Authorization"] == "Bearer legacy-token"

    def test_raises_when_no_token_and_no_provider(self):
        from sanctum_cli.assist.router_client import (
            RouterClient,
            RouterClientError,
            build_router_interpret_request,
        )

        client = RouterClient(base_url="https://router.example.test")
        request = build_router_interpret_request(
            mode="natural_language", intent="test", calling_agent="surgeon"
        )

        with pytest.raises(RouterClientError, match="SANCTUM_ROUTER_TOKEN"):
            client.interpret(request)


class TestGetRouterClient:
    def test_returns_client_with_env_var(self, monkeypatch):
        from sanctum_cli.assist.router_client import get_router_client

        monkeypatch.setenv("SANCTUM_ROUTER_TOKEN", "test-token")
        client = get_router_client()
        assert client is not None
        assert client.token == "test-token"

    def test_returns_none_when_no_source(self, monkeypatch, tmp_path):
        from sanctum_cli.assist.router_client import get_router_client

        monkeypatch.delenv("SANCTUM_ROUTER_TOKEN", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_JWT", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_ID", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("OIDC_CLIENT_ID", raising=False)
        monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)
        cache_file = tmp_path / "router-token-cache.json"
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)

        client = get_router_client()
        assert client is None

    def test_returns_client_with_cache(self, monkeypatch, tmp_path):
        from sanctum_cli.assist.router_client import get_router_client

        token = _make_jwt(3600)
        cache_file = tmp_path / "router-token-cache.json"
        cache_file.write_text(json.dumps({"access_token": token}))
        monkeypatch.setattr("sanctum_cli.token_provider.CACHE_FILE", cache_file)
        monkeypatch.delenv("SANCTUM_ROUTER_TOKEN", raising=False)
        monkeypatch.delenv("SANCTUM_ROUTER_JWT", raising=False)

        client = get_router_client()
        assert client is not None
