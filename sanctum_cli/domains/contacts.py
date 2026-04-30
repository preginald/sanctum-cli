"""Contact domain commands."""

import click
import httpx

from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success
from sanctum_client.client import post, put


def _error_message(result: dict) -> str:
    detail = result.get("detail") or result.get("message") or result.get("error")
    if isinstance(detail, list):
        return "; ".join(
            str(item.get("msg", item)) if isinstance(item, dict) else str(item)
            for item in detail
        )
    return str(detail or result)


@click.group()
def contacts() -> None:
    """Manage contacts."""
    pass


@contacts.command("enable-portal")
@click.argument("contact_id")
@click.pass_context
def enable_portal(ctx: click.Context, contact_id: str) -> None:
    """Enable SSO portal access for a contact."""
    check_command_identity("contacts", "enable-portal", ctx.obj.get("resolved_agent"))

    result = put(f"/contacts/{contact_id}", json={"enable_portal_access": True})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    if isinstance(result, dict) and result.get("id"):
        print_success(f"Portal access enabled for contact: {result['id']}")
        print_key_value(
            {
                "Name": f"{result.get('first_name', '')} {result.get('last_name', '')}".strip(),
                "Email": result.get("email"),
                "Portal Access": result.get("portal_access"),
                "Provisioning": result.get("provisioning_result"),
            }
        )
    else:
        print_error(str(result))


@contacts.command("invite")
@click.argument("contact_id")
@click.pass_context
def invite(ctx: click.Context, contact_id: str) -> None:
    """Send a portal password setup invite for a contact."""
    check_command_identity("contacts", "invite", ctx.obj.get("resolved_agent"))

    try:
        result = post(f"/contacts/{contact_id}/invite", json={})
    except httpx.HTTPStatusError as exc:
        if ctx.obj.get("output_json"):
            print_json(
                {
                    "error": True,
                    "status_code": exc.response.status_code,
                    "detail": exc.response.text,
                }
            )
            raise SystemExit(1) from exc
        print_error(f"Invite failed ({exc.response.status_code}): {exc.response.text}")
        raise SystemExit(1) from exc

    if ctx.obj.get("output_json"):
        print_json(result)
        if isinstance(result, dict) and result.get("error"):
            raise SystemExit(1)
        return

    if isinstance(result, dict) and result.get("error"):
        print_error(_error_message(result))
        raise SystemExit(1)

    if isinstance(result, dict) and result.get("email"):
        print_success(f"Portal invite sent to {result['email']}")
        print_key_value(
            {
                "Status": result.get("status"),
                "Email": result.get("email"),
            }
        )
    else:
        print_error(str(result))
        raise SystemExit(1)
