"""Sanctum CLI — root Click group with global flags."""

import logging
import sys

import click

from sanctum_cli.auth import ensure_auth
from sanctum_cli.display import print_error
from sanctum_cli.group import HelpfulGroup

logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)


@click.group(cls=HelpfulGroup)
@click.option(  # noqa: E501
    "--env", "-e", type=click.Choice(["local", "prod"]), default=None, help="API environment"
)
@click.option(  # noqa: E501
    "--agent", "-a", type=str, default=None, help="Agent identity (surgeon, architect, etc.)"
)
@click.option(
    "--user", "-u", type=str, default=None, help="Human user email (saves PAT to ~/.sanctum/users/)"
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def main(
    ctx: click.Context,
    env: str | None,
    agent: str | None,
    user: str | None,
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
    ctx.obj["user"] = user
    ctx.obj["yes"] = yes
    ctx.obj["output_json"] = output_json

    if ctx.invoked_subcommand not in ("login", "version", None):
        if not agent and not user:
            print_error("--agent <name> or --user <email> is required")
            print_error("Available: architect, surgeon, sentinel, scribe, oracle,")
            print_error("          guardian, hermes, mock")
            print_error("See DOC-111 for the full agent reference and identity guide")
            print_error("Example: sanctum --agent surgeon tickets list")
            print_error("         sanctum --user peter@digitalsanctum.com.au tickets list")
            sys.exit(1)

        try:
            resolved = ensure_auth(env=env, agent=agent, user=user)
            ctx.obj["resolved_agent"] = resolved
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
@click.option("--user", "-u", type=str, default=None)
def login(env: str | None, agent: str | None, user: str | None) -> None:
    """Authenticate interactively and save token."""
    if not agent and not user:
        print_error("--agent <name> or --user <email> is required")
        sys.exit(1)
    ensure_auth(env=env, agent=agent, user=user)
    click.echo("Authenticated.")


# ruff: noqa: E402 — domain imports must be after main() definition
from sanctum_cli.domains.artefacts_ import artefacts
from sanctum_cli.domains.articles import articles
from sanctum_cli.domains.capture_execute import capture_execute
from sanctum_cli.domains.invoices import invoices
from sanctum_cli.domains.milestones import milestones
from sanctum_cli.domains.mockups import mockups
from sanctum_cli.domains.notify import notify
from sanctum_cli.domains.products import products
from sanctum_cli.domains.projects import projects
from sanctum_cli.domains.rate_cards import rate_cards
from sanctum_cli.domains.search_ import search
from sanctum_cli.domains.templates import templates
from sanctum_cli.domains.tickets import tickets
from sanctum_cli.domains.time_entries import time_entries
from sanctum_cli.domains.workbench import workbench

main.add_command(tickets)
main.add_command(articles)
main.add_command(capture_execute)
main.add_command(milestones)
main.add_command(invoices)
main.add_command(search)
main.add_command(projects)
main.add_command(templates)
main.add_command(products)
main.add_command(rate_cards)
main.add_command(workbench)
main.add_command(time_entries)
main.add_command(artefacts)
main.add_command(notify)
main.add_command(mockups)


if __name__ == "__main__":
    main()
