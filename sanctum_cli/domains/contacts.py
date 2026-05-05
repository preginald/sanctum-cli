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
            str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail
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


@contacts.command("set-password")
@click.argument("contact_id")
@click.pass_context
def set_password(ctx: click.Context, contact_id: str) -> None:
    """Set a portal password for a contact."""
    check_command_identity("contacts", "set-password", ctx.obj.get("resolved_agent"))

    password = click.prompt(
        "New portal password",
        hide_input=True,
        confirmation_prompt=True,
    )
    result = post(f"/contacts/{contact_id}/password", json={"password": password})

    if ctx.obj.get("output_json"):
        print_json(result)
        if isinstance(result, dict) and result.get("error"):
            raise SystemExit(1)
        return

    if isinstance(result, dict) and result.get("error"):
        print_error(_error_message(result))
        raise SystemExit(1)

    if isinstance(result, dict) and result.get("email"):
        print_success(f"Portal password set for {result['email']}")
        print_key_value(
            {
                "Status": result.get("status"),
                "Email": result.get("email"),
            }
        )
    else:
        print_error(str(result))
        raise SystemExit(1)


@contacts.command("update")
@click.argument("contact_id")
@click.option("--first-name", "-f", default=None, help="New first name")
@click.option("--last-name", "-l", default=None, help="New last name")
@click.option("--email", "-e", default=None, help="New email address")
@click.option("--phone", "-p", default=None, help="New phone number")
@click.option("--job-title", "-j", default=None, help="New job title")
@click.option("--company-name", "-c", default=None, help="New company name")
@click.option("--account-id", "-a", default=None, help="New account UUID")
@click.option("--primary-contact", is_flag=True, default=None, help="Mark as primary contact")
@click.pass_context
def update_contact(
    ctx: click.Context,
    contact_id: str,
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    phone: str | None,
    job_title: str | None,
    company_name: str | None,
    account_id: str | None,
    primary_contact: bool | None,
) -> None:
    """Update a contact's fields."""
    check_command_identity("contacts", "update", ctx.obj.get("resolved_agent"))

    payload: dict = {}
    if first_name is not None:
        payload["first_name"] = first_name
    if last_name is not None:
        payload["last_name"] = last_name
    if email is not None:
        payload["email"] = email
    if phone is not None:
        payload["phone"] = phone
    if job_title is not None:
        payload["job_title"] = job_title
    if company_name is not None:
        payload["company_name"] = company_name
    if account_id is not None:
        payload["account_id"] = account_id
    if primary_contact is not None:
        payload["is_primary_contact"] = primary_contact

    if not payload:
        print_error("Nothing to update. Provide at least one field.")
        return

    result = put(f"/contacts/{contact_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Contact {contact_id} updated")
        print_key_value(
            {
                "Name": f"{result.get('first_name', '')} {result.get('last_name', '')}".strip(),
                "Email": result.get("email"),
                "Phone": result.get("phone"),
                "Job Title": result.get("job_title"),
                "Company": result.get("company_name"),
                "Primary Contact": result.get("is_primary_contact"),
            }
        )
    else:
        print_error(str(result))


@contacts.command("provision-cms-sso")
@click.argument("contact_id")
@click.pass_context
def provision_cms_sso(ctx: click.Context, contact_id: str) -> None:
    """Provision CMS SSO access for a contact."""
    check_command_identity("contacts", "provision-cms-sso", ctx.obj.get("resolved_agent"))

    result = put(f"/contacts/{contact_id}", json={"provision_cms_sso": True})
    if ctx.obj.get("output_json"):
        print_json(result)
        return

    if isinstance(result, dict) and result.get("id"):
        print_success(f"CMS SSO provisioned for contact: {result['id']}")
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
