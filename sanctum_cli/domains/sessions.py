"""Session management commands for conversational context."""

import click

from sanctum_cli.assist.session import get_session_store
from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_key_value, print_success, print_table


@click.group()
def sessions() -> None:
    """Manage conversational sessions."""


@sessions.command()
@click.option("--agent", "-a", default=None, help="Agent identity for session")
@click.option("--user", "-u", default=None, help="User email for session")
@click.pass_context
def create(ctx: click.Context, agent: str | None, user: str | None) -> None:
    """Create a new conversational session."""
    check_command_identity("sessions", "create", ctx.obj.get("resolved_agent"))
    store = get_session_store()
    session = store.create(agent=agent, user=user)
    if ctx.obj.get("output_json"):
        print_json(session.to_dict())
    else:
        print_success(f"Session created: {session.session_id}")


@sessions.command()
@click.argument("session_id")
@click.pass_context
def show(ctx: click.Context, session_id: str) -> None:
    """Show session details and message history."""
    check_command_identity("sessions", "show", ctx.obj.get("resolved_agent"))
    store = get_session_store()
    session = store.get(session_id)
    if session is None:
        print_error(f"Session not found or expired: {session_id}")
        return
    if ctx.obj.get("output_json"):
        print_json(session.to_dict())
        return

    print_key_value(
        {
            "Session ID": session.session_id,
            "Agent": session.agent or "(none)",
            "User": session.user or "(none)",
            "Messages": str(len(session.messages)),
            "Created": session.created_at,
            "Updated": session.updated_at,
        },
        title="Session",
    )

    if session.messages:
        click.echo("\n  Recent Messages:")
        for msg in session.messages[-10:]:
            click.echo(f"    [{msg.role}] {msg.content[:120]}")


@sessions.command()
@click.pass_context
def list(ctx: click.Context) -> None:
    """List active sessions."""
    check_command_identity("sessions", "list", ctx.obj.get("resolved_agent"))
    store = get_session_store()
    all_sessions = store.list_active()
    if ctx.obj.get("output_json"):
        print_json([s.to_dict() for s in all_sessions])
        return
    if not all_sessions:
        click.echo("No active sessions.")
        return
    rows = []
    for s in all_sessions:
        rows.append([
            s.session_id[:8],
            s.agent or "-",
            str(len(s.messages)),
            s.updated_at[:19],
        ])
    print_table(
        ["ID", "Agent", "Messages", "Updated"],
        rows,
        title="Active Sessions",
    )


@sessions.command()
@click.argument("session_id")
@click.pass_context
def delete(ctx: click.Context, session_id: str) -> None:
    """Delete a session."""
    check_command_identity("sessions", "delete", ctx.obj.get("resolved_agent"))
    store = get_session_store()
    if store.delete(session_id):
        print_success(f"Session deleted: {session_id}")
    else:
        print_error(f"Session not found: {session_id}")


@sessions.command(name="clear-expired")
@click.pass_context
def clear_expired(ctx: click.Context) -> None:
    """Remove expired sessions."""
    check_command_identity("sessions", "clear-expired", ctx.obj.get("resolved_agent"))
    store = get_session_store()
    count = store.clear_expired()
    print_success(f"Cleared {count} expired session(s)")
