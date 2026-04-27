"""Tests for the shared HTTP client."""

import pytest
import httpx
from sanctum_client.client import (
    get,
    post,
    put,
    delete,
    set_api_token,
    set_api_base,
    close_client,
)


class TestClient:
    def test_get_request(self, httpx_mock):
        httpx_mock.add_response(
            method="GET",
            url="https://core.digitalsanctum.com.au/api/test",
            json={"status": "ok"},
        )
        result = get("/test")
        assert result == {"status": "ok"}

    def test_post_request(self, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://core.digitalsanctum.com.au/api/tickets",
            json={"id": 9999, "subject": "test"},
        )
        result = post("/tickets", json={"subject": "test"})
        assert result["id"] == 9999

    def test_auth_header(self, httpx_mock):
        set_api_token("sntm_test123")
        httpx_mock.add_response(
            method="GET",
            url="https://core.digitalsanctum.com.au/api/projects",
            json=[],
        )

        get("/projects")

        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "Bearer sntm_test123"

    def test_retry_on_502(self, httpx_mock):
        httpx_mock.add_response(status_code=502)
        httpx_mock.add_response(
            method="GET",
            url="https://core.digitalsanctum.com.au/api/retry-test",
            json={"recovered": True},
        )

        result = get("/retry-test")
        assert result == {"recovered": True}
        assert len(httpx_mock.get_requests()) == 2

    def test_422_returns_error_dict(self, httpx_mock):
        httpx_mock.add_response(
            method="POST",
            url="https://core.digitalsanctum.com.au/api/tickets",
            status_code=422,
            json={"detail": [{"msg": "Field required"}]},
        )
        result = post("/tickets", json={})
        assert result.get("error") is True
        assert result.get("status_code") == 422

    def test_put_request(self, httpx_mock):
        httpx_mock.add_response(
            method="PUT",
            url="https://core.digitalsanctum.com.au/api/tickets/123",
            json={"id": 123, "status": "recon"},
        )
        result = put("/tickets/123", json={"status": "recon"})
        assert result["status"] == "recon"

    def test_delete_request(self, httpx_mock):
        httpx_mock.add_response(
            method="DELETE",
            url="https://core.digitalsanctum.com.au/api/tickets/123",
            status_code=204,
        )
        result = delete("/tickets/123")
        assert result == {"status": "deleted"}

    def test_api_base_switch(self, httpx_mock):
        set_api_base("http://localhost:8000")
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:8000/test",
            json={"local": True},
        )
        result = get("/test")
        assert result == {"local": True}
        set_api_base("https://core.digitalsanctum.com.au/api")
