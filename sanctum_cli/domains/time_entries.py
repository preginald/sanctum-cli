"""Time entry domain commands."""

import click

from sanctum_cli.display import print_error, print_json, print_success
from sanctum_client.client import post, put


@click.group()
def time_entries() -> None:
    """Manage time entries on tickets."""
    pass


@time_entries.command(name="create")
@click.option("--ticket-id", "-t", type=int, required=True, help="Ticket number")
@click.option("--start", "-s", required=True, help="Start time (ISO 8601)")
@click.option("--end", "-e", required=True, help="End time (ISO 8601)")
@click.option("--description", "-d", default="", help="Work description")
@click.pass_context
def create_entry(
    ctx: click.Context, ticket_id: int, start: str, end: str, description: str
) -> None:
    """Create a time entry on a ticket."""
    payload = {"start_time": start, "end_time": end, "description": description}
    result = post(f"/tickets/{ticket_id}/time_entries", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success(f"Time entry created on #{ticket_id}")
    else:
        print_error(str(result))


@time_entries.command(name="update")
@click.argument("entry_id")
@click.option("--ticket-id", "-t", type=int, required=True, help="Ticket number")
@click.option("--start", "-s", default=None, help="New start time")
@click.option("--end", "-e", default=None, help="New end time")
@click.option("--description", "-d", default=None, help="New description")
@click.pass_context
def update_entry(ctx: click.Context, entry_id: str, ticket_id: int,
                 start: str | None, end: str | None, description: str | None) -> None:
    """Update a time entry."""
    payload: dict = {}
    if start:
        payload["start_time"] = start
    if end:
        payload["end_time"] = end
    if description:
        payload["description"] = description
    result = put(f"/tickets/{ticket_id}/time_entries/{entry_id}", json=payload)
    if ctx.obj.get("output_json"):
        print_json(result)
    elif isinstance(result, dict) and "id" in result:
        print_success("Time entry updated")
    else:
        print_error(str(result))
