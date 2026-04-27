"""Sanctum CLI — root Click group with global flags."""

import logging
import sys
from typing import Optional

import click

from sanctum_cli.auth import ensure_auth
from sanctum_cli.display import print_error

logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)


class AliasedGroup(click.Group):
    """Click group that supports command aliases via aliases dict on commands."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        for name, command in self.commands.items():
            if hasattr(command, "aliases") and cmd_name in command.aliases:
                return command
        return None


@click.group(cls=AliasedGroup)
@click.option("--env", "-e", type=click.Choice(["local", "prod"]), default=None, help="API environment")
@click.option("--agent", "-a", type=str, default=None, help="Agent identity (operator, architect, etc.)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def main(
    ctx: click.Context,
    env: Optional[str],
    agent: Optional[str],
    yes: bool,
    output_json: bool,
    debug: bool,
) -> None:
    """Sanctum Core CLI — manage tickets, articles, milestones, invoices, and more."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    ctx.ensure_object(dict)
    ctx.obj["env"] = env
    ctx.obj["agent"] = agent
    ctx.obj["yes"] = yes
    ctx.obj["output_json"] = output_json

    if ctx.invoked_subcommand not in ("login", "version", None):
        try:
            ensure_auth(env=env, agent=agent)
        except Exception as e:
            print_error(f"Authentication failed: {e}")
            sys.exit(1)


@main.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Show CLI version."""
    import importlib.metadata
    try:
        v = importlib.metadata.version("sanctum-cli")
    except importlib.metadata.PackageNotFoundError:
        v = "dev"
    click.echo(f"sanctum-cli v{v}")


@main.command()
@click.option("--env", "-e", type=click.Choice(["local", "prod"]), default=None)
@click.option("--agent", "-a", type=str, default=None)
def login(env: Optional[str], agent: Optional[str]) -> None:
    """Authenticate interactively and save token."""
    ensure_auth(env=env, agent=agent)
    click.echo("Authenticated.")


# Import domain command groups
from sanctum_cli.domains.tickets import tickets
from sanctum_cli.domains.articles import articles
from sanctum_cli.domains.milestones import milestones
from sanctum_cli.domains.invoices import invoices
from sanctum_cli.domains.search_ import search

main.add_command(tickets)
main.add_command(articles)
main.add_command(milestones)
main.add_command(invoices)
main.add_command(search)


if __name__ == "__main__":
    main()
