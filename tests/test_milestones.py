"""Tests for milestone CLI commands."""

from click.testing import CliRunner

import sanctum_cli.domains.projects as projects_domain
from sanctum_cli.domains import milestones as milestones_domain
from sanctum_cli.domains.milestones import milestones


def test_list_milestones_by_project_name_paginates(monkeypatch):
    project_id = "22222222-2222-2222-2222-222222222222"
    calls = []

    def fake_project_get(path, params=None):
        calls.append(("GET", path, params))
        offset = int(params.get("offset", "0"))
        if offset == 0:
            return {"projects": [{"id": "old-id", "name": "Some Other Project"}] * 100}
        return {"projects": [{"id": project_id, "name": "Form Template & Instance Restructure"}]}

    def fake_milestone_get(path, params=None):
        calls.append(("GET", path, params))
        return {"milestones": []}

    monkeypatch.setattr(projects_domain, "get", fake_project_get)
    monkeypatch.setattr(milestones_domain, "get", fake_milestone_get)

    result = CliRunner().invoke(
        milestones,
        ["list", "--project-id", "Form Template & Instance Restructure"],
        obj={"output_json": False, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    assert calls == [
        ("GET", "/projects", {"limit": "100", "offset": "0"}),
        ("GET", "/projects", {"limit": "100", "offset": "100"}),
        ("GET", "/milestones", {"project_id": project_id}),
    ]


def test_complete_milestone_accepts_status(monkeypatch):
    milestone_id = "33333333-3333-3333-3333-333333333333"
    calls = []

    def fake_put(path, json=None):
        calls.append(("PUT", path, json))
        return {"id": milestone_id, "status": "active"}

    monkeypatch.setattr(milestones_domain, "put", fake_put)

    result = CliRunner().invoke(
        milestones,
        ["complete", milestone_id, "--status", "active"],
        obj={"output_json": False, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    assert calls == [("PUT", f"/milestones/{milestone_id}", {"status": "active"})]
