"""Mockup domain commands."""

from __future__ import annotations

import builtins
import hashlib
import re
from datetime import UTC, datetime
from typing import Any

import click

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table
from sanctum_client.client import delete as api_delete
from sanctum_client.client import get, post, put

RULESET = "mockup-publish-v1"
SUPPORTED_MIME_TYPES = {
    "text/jsx",
    "text/tsx",
    "text/html",
    "text/css",
    "application/json",
    "text/javascript",
    "text/typescript",
    "image/png",
    "image/jpeg",
    "image/svg+xml",
}
SANDBOX_MIME_TYPES = {"text/jsx", "text/tsx", "text/html", "text/javascript", "text/typescript"}
CODE_MIME_TYPES = {"text/css", "application/json"}
PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


@click.group()
def mockups() -> None:
    """Manage mockup artefacts."""
    pass


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _content_hash(mime_type: str | None, content: str | None) -> str:
    raw = f"{RULESET}\0{mime_type or ''}\0{content or ''}"
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def _metadata(raw: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(raw, dict):
        return raw, True
    return {}, False


def _require_mockup(artefact: dict[str, Any]) -> bool:
    return artefact.get("category") == "mockup"


def _render_strategy(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type in SANDBOX_MIME_TYPES:
        return "sandbox"
    if mime_type in CODE_MIME_TYPES:
        return "code"
    return "fallback"


def _find_placeholder(value: Any, path: str) -> str | None:
    if isinstance(value, str):
        return path if PLACEHOLDER_RE.search(value) else None
    if isinstance(value, dict):
        for key, child in value.items():
            found = _find_placeholder(child, f"{path}.{key}")
            if found:
                return found
    if isinstance(value, builtins.list):
        for index, child in enumerate(value):
            found = _find_placeholder(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _lint_result(artefact: dict[str, Any], *, checked_at: str | None = None) -> dict[str, Any]:
    metadata, metadata_was_object = _metadata(artefact.get("metadata"))
    mime_type = artefact.get("mime_type") or ""
    content = artefact.get("content") or ""
    issues: list[dict[str, str]] = []

    if not metadata_was_object:
        issues.append(
            {
                "rule": "metadata_shape",
                "severity": "error",
                "message": "Metadata must be an object",
                "path": "metadata",
            }
        )
    if mime_type not in SUPPORTED_MIME_TYPES:
        issues.append(
            {
                "rule": "mime_supported",
                "severity": "error",
                "message": "MIME type is not publishable",
                "path": "mime_type",
            }
        )
    if _render_strategy(mime_type) == "fallback":
        issues.append(
            {
                "rule": "render_strategy_supported",
                "severity": "error",
                "message": "MIME type has no publishable render strategy",
                "path": "mime_type",
            }
        )
    if not content:
        issues.append(
            {
                "rule": "content_present",
                "severity": "error",
                "message": "Mockup content is required",
                "path": "content",
            }
        )
    placeholder_path = (
        "content" if PLACEHOLDER_RE.search(content) else _find_placeholder(metadata, "metadata")
    )
    if placeholder_path:
        issues.append(
            {
                "rule": "placeholder_free",
                "severity": "error",
                "message": "Mockup contains unresolved placeholder tokens",
                "path": placeholder_path,
            }
        )

    return {
        "schema_version": 1,
        "ruleset": RULESET,
        "status": "fail" if any(i["severity"] == "error" for i in issues) else "pass",
        "checked_at": checked_at or _utc_now_iso(),
        "content_hash": _content_hash(mime_type, content),
        "issues": issues,
    }


def _with_lint_metadata(metadata_raw: Any, lint_result: dict[str, Any]) -> dict[str, Any]:
    metadata, _ = _metadata(metadata_raw)
    merged = {**metadata, "mockup_lint": lint_result}
    if lint_result["status"] != "pass":
        merged["published"] = False
        merged["published_at"] = None
    return merged


def _not_run_metadata(artefact: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    metadata, _ = _metadata(artefact.get("metadata"))
    mime_type = payload.get("mime_type", artefact.get("mime_type") or "")
    content = payload.get("content", artefact.get("content") or "")
    return {
        **metadata,
        "mockup_lint": {
            "schema_version": 1,
            "ruleset": RULESET,
            "status": "not_run",
            "checked_at": _utc_now_iso(),
            "content_hash": _content_hash(mime_type, content),
            "issues": [],
        },
        "published": False,
        "published_at": None,
    }


@mockups.command()
@click.option("--ticket-id", "-t", type=int, default=None, help="Filter by ticket")
@click.option("--limit", "-l", default=20, type=int)
@click.pass_context
def list(ctx: click.Context, ticket_id: int | None, limit: int) -> None:
    """List mockups."""
    check_command_identity("mockups", "list", ctx.obj.get("resolved_agent"))

    check_command_identity("mockups", "list", ctx.obj.get("resolved_agent"))
    params: dict = {"limit": str(limit)}
    if ticket_id:
        params["ticket_id"] = str(ticket_id)
    result = get("/artefacts", params={**params, "category": "mockup"})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    mockups_list = result if isinstance(result, builtins.list) else result.get("artefacts", [])
    if not mockups_list:
        click.echo("No mockups found.")
        return

    rows = []
    for m in mockups_list:
        rows.append(
            [
                m.get("name", "")[:50],
                m.get("status", ""),
                str(m.get("links_count", 0)),
                m.get("created_at", ""),
            ]
        )
    print_table(["Name", "Status", "Links", "Created"], rows, title="Mockups")


@mockups.command()
@click.argument("mockup_id")
@click.pass_context
def show(ctx: click.Context, mockup_id: str) -> None:
    """Show mockup artefact details."""
    check_command_identity("mockups", "show", ctx.obj.get("resolved_agent"))
    result = get(f"/artefacts/{mockup_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    print_key_value(
        {
            "Name": result.get("name"),
            "Status": result.get("status"),
            "Links": result.get("links_count"),
            "Ticket": result.get("ticket_id"),
            "Created": result.get("created_at"),
            "MIME Type": result.get("mime_type"),
        },
        title=f"Mockup: {result.get('name', '')}",
    )


@mockups.command()
@click.option("--name", "-n", required=True, help="Mockup name")
@click.option("--ticket-id", "-t", type=int, default=None, help="Link to ticket")
@click.option("--file", "-f", type=click.Path(exists=True, dir_okay=False), help="Mockup file path")
@click.option(
    "--type",
    "artefact_type",
    default="file",
    type=click.Choice(["file", "url", "code_path", "document", "credential_ref"]),
    help="Artefact type",
)
@click.option("--content", default=None, help="Mockup body content")
@click.option("--mime-type", "mime_type", default=None, help="Content MIME type (e.g. text/html)")
@click.pass_context
def create(
    ctx: click.Context,
    name: str,
    ticket_id: int | None,
    file: str | None,
    artefact_type: str,
    content: str | None,
    mime_type: str | None,
) -> None:
    """Create a new mockup artefact."""
    check_command_identity("mockups", "create", ctx.obj.get("resolved_agent"))

    payload: dict = {"name": name, "category": "mockup", "artefact_type": artefact_type}
    if ticket_id:
        payload["ticket_id"] = ticket_id
    if file:
        payload["file_path"] = file

    result = post("/artefacts", json=payload)
    error: dict | None = None
    if isinstance(result, dict) and "id" in result:
        artefact_id = result["id"]
        if content or mime_type:
            update: dict = {}
            if content:
                update["content"] = content
            if mime_type:
                update["mime_type"] = mime_type
            update_result = put(f"/artefacts/{artefact_id}", json=update)
            if isinstance(update_result, dict) and update_result.get("error"):
                error = update_result
        if ctx.obj.get("output_json"):
            if error:
                print_json({"create": result, "content_update": error})
            else:
                print_json(result)
            return
        if error:
            print_error(f"Mockup created but content update failed: {error}")
            return
        print_success(f"Mockup created: {artefact_id}")
    elif isinstance(result, dict) and result.get("error"):
        print_error(str(result))
    else:
        print_error(str(result))


@mockups.command()
@click.argument("mockup_id")
@click.option("--name", "-n", default=None, help="New mockup name")
@click.option("--ticket-id", "-t", type=int, default=None, help="Link to ticket")
@click.option("--file", "-f", type=click.Path(exists=True, dir_okay=False), help="Mockup file path")
@click.option("--content", default=None, help="Mockup body content")
@click.option("--mime-type", "mime_type", default=None, help="Content MIME type (e.g. text/html)")
@click.pass_context
def update(
    ctx: click.Context,
    mockup_id: str,
    name: str | None,
    ticket_id: int | None,
    file: str | None,
    content: str | None,
    mime_type: str | None,
) -> None:
    """Update a mockup artefact."""
    check_command_identity("mockups", "update", ctx.obj.get("resolved_agent"))

    payload: dict = {}
    if name:
        payload["name"] = name
    if ticket_id is not None:
        payload["ticket_id"] = ticket_id
    if file:
        payload["file_path"] = file
    if content:
        payload["content"] = content
    if mime_type:
        payload["mime_type"] = mime_type
    if not payload:
        print_error(
            "Nothing to update. Provide --name, --ticket-id, --file, --content, or --mime-type."
        )
        return

    if content is not None or mime_type is not None:
        artefact = get(f"/artefacts/{mockup_id}", params={"expand": "content"})
        if not isinstance(artefact, dict) or not _require_mockup(artefact):
            print_error("Refusing to update publish-gate metadata for a non-mockup artefact")
            return
        payload["metadata"] = _not_run_metadata(artefact, payload)

    result = put(f"/artefacts/{mockup_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Mockup {mockup_id} updated")
    else:
        print_error(str(result))


@mockups.command()
@click.argument("mockup_id")
@click.option("--dry-run", is_flag=True, help="Run lint without persisting metadata")
@click.pass_context
def lint(ctx: click.Context, mockup_id: str, dry_run: bool) -> None:
    """Run deterministic publish-gate lint for a mockup."""
    check_command_identity("mockups", "lint", ctx.obj.get("resolved_agent"))

    artefact = get(f"/artefacts/{mockup_id}", params={"expand": "content"})
    if not isinstance(artefact, dict) or not _require_mockup(artefact):
        print_error("Refusing to lint a non-mockup artefact")
        return
    result = _lint_result(artefact)
    if not dry_run:
        metadata = _with_lint_metadata(artefact.get("metadata"), result)
        put(f"/artefacts/{mockup_id}", json={"metadata": metadata})

    output = {"id": mockup_id, **result, "persisted": not dry_run}
    if ctx.obj.get("output_json"):
        print_json(output)
        return
    if result["status"] == "pass":
        print_success(f"Mockup {mockup_id} lint passed")
    else:
        print_error(f"Mockup {mockup_id} lint failed with {len(result['issues'])} issue(s)")


@mockups.command()
@click.argument("mockup_id")
@click.pass_context
def publish(ctx: click.Context, mockup_id: str) -> None:
    """Publish a mockup after a current passing lint result."""
    check_command_identity("mockups", "publish", ctx.obj.get("resolved_agent"))

    artefact = get(f"/artefacts/{mockup_id}", params={"expand": "content"})
    if not isinstance(artefact, dict) or not _require_mockup(artefact):
        print_error("Refusing to publish a non-mockup artefact")
        return
    metadata, _ = _metadata(artefact.get("metadata"))
    lint_result = (
        metadata.get("mockup_lint") if isinstance(metadata.get("mockup_lint"), dict) else None
    )
    if not lint_result or lint_result.get("status") != "pass":
        print_error("Mockup lint has not passed")
        return
    if any(issue.get("severity") == "error" for issue in lint_result.get("issues", [])):
        print_error("Mockup lint has blocking errors")
        return
    current_hash = _content_hash(artefact.get("mime_type") or "", artefact.get("content") or "")
    if lint_result.get("content_hash") != current_hash:
        print_error("Stored lint result is stale; run mockups lint again")
        return

    published_at = metadata.get("published_at") if metadata.get("published") else _utc_now_iso()
    next_metadata = {**metadata, "published": True, "published_at": published_at}
    put(f"/artefacts/{mockup_id}", json={"metadata": next_metadata})
    output = {
        "id": mockup_id,
        "published": True,
        "published_at": published_at,
        "mockup_lint": lint_result,
    }
    if ctx.obj.get("output_json"):
        print_json(output)
        return
    print_success(f"Mockup {mockup_id} published")


@mockups.command()
@click.argument("mockup_id")
@click.confirmation_option(prompt="Delete this mockup?")
@click.pass_context
def delete(ctx: click.Context, mockup_id: str) -> None:
    """Delete a mockup artefact."""
    check_command_identity("mockups", "delete", ctx.obj.get("resolved_agent"))

    result = api_delete(f"/artefacts/{mockup_id}")
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and result.get("status") in ("deleted", "archived"):
        print_success(f"Mockup {mockup_id} deleted")
    else:
        print_error(str(result))
