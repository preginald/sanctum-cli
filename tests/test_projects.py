"""Tests for project CLI commands."""

from click.testing import CliRunner

import sanctum_cli.domains.projects as projects_domain
from sanctum_cli.domains.projects import projects


def test_complete_project_by_name_resolves_uuid(monkeypatch):
    project_id = "11111111-1111-1111-1111-111111111111"
    calls = []

    def fake_get(path, params=None):
        calls.append(("GET", path, params))
        return {"projects": [{"id": project_id, "name": "Form Template & Instance Restructure"}]}

    def fake_put(path, json=None):
        calls.append(("PUT", path, json))
        return {"id": project_id, "status": "completed"}

    monkeypatch.setattr(projects_domain, "get", fake_get)
    monkeypatch.setattr(projects_domain, "put", fake_put)

    result = CliRunner().invoke(
        projects,
        ["complete", "Form Template & Instance Restructure"],
        obj={"output_json": False, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    assert calls == [
        ("GET", "/projects", {"limit": "100", "offset": "0"}),
        ("PUT", f"/projects/{project_id}", {"status": "completed"}),
    ]


def test_complete_project_by_name_paginates(monkeypatch):
    project_id = "22222222-2222-2222-2222-222222222222"
    calls = []

    def fake_get(path, params=None):
        calls.append(("GET", path, params))
        offset = int(params.get("offset", "0"))
        if offset == 0:
            return {"projects": [{"id": "old-id", "name": "Some Other Project"}] * 100}
        return {"projects": [{"id": project_id, "name": "Form Template & Instance Restructure"}]}

    def fake_put(path, json=None):
        calls.append(("PUT", path, json))
        return {"id": project_id, "status": "completed"}

    monkeypatch.setattr(projects_domain, "get", fake_get)
    monkeypatch.setattr(projects_domain, "put", fake_put)

    result = CliRunner().invoke(
        projects,
        ["complete", "Form Template & Instance Restructure"],
        obj={"output_json": False, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    assert calls == [
        ("GET", "/projects", {"limit": "100", "offset": "0"}),
        ("GET", "/projects", {"limit": "100", "offset": "100"}),
        ("PUT", f"/projects/{project_id}", {"status": "completed"}),
    ]


def test_update_project_by_uuid_does_not_lookup_projects(monkeypatch):
    project_id = "11111111-1111-1111-1111-111111111111"
    calls = []

    def fake_get(path, params=None):
        calls.append(("GET", path, params))
        return {"projects": []}

    def fake_put(path, json=None):
        calls.append(("PUT", path, json))
        return {"id": project_id, "status": "active"}

    monkeypatch.setattr(projects_domain, "get", fake_get)
    monkeypatch.setattr(projects_domain, "put", fake_put)

    result = CliRunner().invoke(
        projects,
        ["update", project_id, "--status", "active"],
        obj={"output_json": False, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    assert calls == [("PUT", f"/projects/{project_id}", {"status": "active"})]
