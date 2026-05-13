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


def test_overview_open_only_filters_closed_milestones(monkeypatch):
    project_id = "11111111-1111-1111-1111-111111111111"
    api_response = {
        "milestones": [
            {
                "id": "m1",
                "name": "Active Sprint",
                "status": "active",
                "tickets": [
                    {"id": 101, "status": "open", "subject": "Do the thing"},
                ],
            },
            {
                "id": "m2",
                "name": "Done Sprint",
                "status": "completed",
                "tickets": [
                    {"id": 102, "status": "resolved", "subject": "Old thing"},
                ],
            },
        ],
    }

    def fake_get(path, params=None):
        return api_response

    monkeypatch.setattr(projects_domain, "get", fake_get)

    result = CliRunner().invoke(
        projects,
        ["overview", project_id, "--open-only"],
        obj={"output_json": False, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    assert "Active Sprint" in result.output
    assert "Done Sprint" not in result.output


def test_overview_open_only_filters_resolved_tickets(monkeypatch):
    project_id = "22222222-2222-2222-2222-222222222222"
    api_response = {
        "milestones": [
            {
                "id": "m1",
                "name": "Current Sprint",
                "status": "active",
                "tickets": [
                    {"id": 101, "status": "open", "subject": "Task to do"},
                    {"id": 102, "status": "review", "subject": "Task in review"},
                    {"id": 103, "status": "resolved", "subject": "Done task"},
                    {"id": 104, "status": "closed", "subject": "Closed task"},
                ],
            },
        ],
    }

    def fake_get(path, params=None):
        return api_response

    monkeypatch.setattr(projects_domain, "get", fake_get)

    result = CliRunner().invoke(
        projects,
        ["overview", project_id, "--open-only"],
        obj={"output_json": False, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    assert "#101" in result.output
    assert "#102" in result.output
    assert "#103" not in result.output
    assert "#104" not in result.output


def test_overview_open_only_json_output(monkeypatch):
    project_id = "33333333-3333-3333-3333-333333333333"
    api_response = {
        "milestones": [
            {
                "id": "m1",
                "name": "Active Sprint",
                "status": "active",
                "tickets": [
                    {"id": 101, "status": "open", "subject": "Open task"},
                    {"id": 102, "status": "resolved", "subject": "Done task"},
                ],
            },
            {
                "id": "m2",
                "name": "Completed Milestone",
                "status": "completed",
                "tickets": [
                    {"id": 103, "status": "closed", "subject": "Old task"},
                ],
            },
        ],
    }

    calls = []

    def fake_get(path, params=None):
        calls.append(("GET", path, params))
        return api_response

    monkeypatch.setattr(projects_domain, "get", fake_get)

    result = CliRunner().invoke(
        projects,
        ["overview", project_id, "--open-only"],
        obj={"output_json": True, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert len(data["milestones"]) == 1
    assert data["milestones"][0]["id"] == "m1"
    assert len(data["milestones"][0]["tickets"]) == 1
    assert data["milestones"][0]["tickets"][0]["id"] == 101


def test_overview_without_open_only_shows_all(monkeypatch):
    project_id = "44444444-4444-4444-4444-444444444444"
    api_response = {
        "milestones": [
            {
                "id": "m1",
                "name": "Completed Sprint",
                "status": "completed",
                "tickets": [
                    {"id": 101, "status": "resolved", "subject": "Old task"},
                ],
            },
        ],
    }

    def fake_get(path, params=None):
        return api_response

    monkeypatch.setattr(projects_domain, "get", fake_get)

    result = CliRunner().invoke(
        projects,
        ["overview", project_id],
        obj={"output_json": False, "resolved_agent": "architect"},
    )

    assert result.exit_code == 0
    assert "Completed Sprint" in result.output
    assert "#101" in result.output


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
