"""Tests for product CLI commands."""

from click.testing import CliRunner

from sanctum_cli.domains import products as products_domain
from sanctum_cli.domains.products import products

PRODUCT_ID = "ebd26214-e8b0-4e45-b1dd-d028be5e5d8c"

SAMPLE_PRODUCT = {
    "id": PRODUCT_ID,
    "name": "Test Product",
    "description": "A test product",
    "type": "service",
    "unit_price": "99.00",
    "is_recurring": True,
    "billing_frequency": "monthly",
    "is_active": True,
    "created_at": "2026-01-01T00:00:00Z",
}


def test_show_product(monkeypatch):
    calls = []

    def fake_get(path):
        calls.append(("GET", path))
        return SAMPLE_PRODUCT

    monkeypatch.setattr(products_domain, "get", fake_get)

    result = CliRunner().invoke(
        products,
        ["show", PRODUCT_ID],
        obj={"output_json": False, "resolved_agent": "surgeon"},
    )

    assert result.exit_code == 0
    assert calls == [("GET", f"/products/{PRODUCT_ID}")]
    assert "Test Product" in result.output
    assert "99.00" in result.output
    assert "service" in result.output


def test_show_product_json(monkeypatch):
    calls = []

    def fake_get(path):
        calls.append(("GET", path))
        return SAMPLE_PRODUCT

    monkeypatch.setattr(products_domain, "get", fake_get)

    result = CliRunner().invoke(
        products,
        ["show", PRODUCT_ID],
        obj={"output_json": True, "resolved_agent": "surgeon"},
    )

    assert result.exit_code == 0
    assert calls == [("GET", f"/products/{PRODUCT_ID}")]
    assert '"id"' in result.output
    assert '"Test Product"' in result.output


def test_show_product_not_found(monkeypatch):
    def fake_get(path):
        raise Exception("404: Not Found")

    monkeypatch.setattr(products_domain, "get", fake_get)

    result = CliRunner().invoke(
        products,
        ["show", "nonexistent-id"],
        obj={"output_json": False, "resolved_agent": "surgeon"},
    )

    assert result.exit_code != 0


def test_update_product_single_field(monkeypatch):
    calls = []

    def fake_put(path, json=None):
        calls.append(("PUT", path, json))
        return {**SAMPLE_PRODUCT, "name": "Renamed Product"}

    monkeypatch.setattr(products_domain, "put", fake_put)

    result = CliRunner().invoke(
        products,
        ["update", PRODUCT_ID, "--name", "Renamed Product"],
        obj={"output_json": False, "resolved_agent": "surgeon"},
    )

    assert result.exit_code == 0
    assert calls == [("PUT", f"/products/{PRODUCT_ID}", {"name": "Renamed Product"})]
    assert "updated" in result.output


def test_update_product_multiple_fields(monkeypatch):
    calls = []

    def fake_put(path, json=None):
        calls.append(("PUT", path, json))
        return {
            **SAMPLE_PRODUCT,
            "name": "Updated",
            "description": "New desc",
            "unit_price": "149.00",
        }

    monkeypatch.setattr(products_domain, "put", fake_put)

    result = CliRunner().invoke(
        products,
        [
            "update",
            PRODUCT_ID,
            "--name", "Updated",
            "--description", "New desc",
            "--unit-price", "149.00",
        ],
        obj={"output_json": False, "resolved_agent": "surgeon"},
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "PUT",
            f"/products/{PRODUCT_ID}",
            {"name": "Updated", "description": "New desc", "unit_price": "149.00"},
        )
    ]
    assert "updated" in result.output


def test_update_product_json_output(monkeypatch):
    calls = []

    def fake_put(path, json=None):
        calls.append(("PUT", path, json))
        return {**SAMPLE_PRODUCT, "name": "JSON Updated"}

    monkeypatch.setattr(products_domain, "put", fake_put)

    result = CliRunner().invoke(
        products,
        ["update", PRODUCT_ID, "--name", "JSON Updated"],
        obj={"output_json": True, "resolved_agent": "surgeon"},
    )

    assert result.exit_code == 0
    assert calls == [("PUT", f"/products/{PRODUCT_ID}", {"name": "JSON Updated"})]
    assert '"JSON Updated"' in result.output


def test_update_product_no_fields(monkeypatch):
    def fake_put(path, json=None):
        raise AssertionError("should not be called")

    monkeypatch.setattr(products_domain, "put", fake_put)

    result = CliRunner().invoke(
        products,
        ["update", PRODUCT_ID],
        obj={"output_json": False, "resolved_agent": "surgeon"},
    )

    assert result.exit_code == 0
    assert "Nothing to update" in result.output


def test_update_product_api_error(monkeypatch):
    def fake_put(path, json=None):
        return {"error": True, "status_code": 422, "detail": "Validation failed"}

    monkeypatch.setattr(products_domain, "put", fake_put)

    result = CliRunner().invoke(
        products,
        ["update", PRODUCT_ID, "--name", "Bad"],
        obj={"output_json": False, "resolved_agent": "surgeon"},
    )

    assert result.exit_code == 0
    assert "Validation failed" in result.output
