"""Custom Click group with alias support and 'did you mean' suggestions."""

import shlex
import sys

import click

from sanctum_cli.assist.errors import explain_error, render_explanation_text
from sanctum_cli.assist.router_client import get_router_client
from sanctum_cli.display import print_json

_GLOBAL_FLAGS: dict[str, str] = {
    "--json": "sanctum --json --agent surgeon <command>",
    "--debug": "sanctum --debug --agent surgeon <command>",
    "--yes": "sanctum --yes --agent surgeon <command>",
    "--agent": "sanctum --agent surgeon <command>",
    "--user": "sanctum --user email@example.com <command>",
    "--env": "sanctum --env prod --agent surgeon <command>",
}


class HelpfulGroup(click.Group):
    """Click group with alias support and 'did you mean' suggestions.

    Pass a ``suggestions`` dict when defining the group to map unknown
    command names to a hint string:

        @click.group(cls=HelpfulGroup, suggestions={
            "comments": (
                "tickets show --comments <id>    View comments\\n"
                "tickets comment <id> -b \"...\"  Add a comment"
            ),
        })
        def tickets():
            ...
    """

    def __init__(self, *args, suggestions=None, **kwargs):
        self.suggestions = suggestions or {}
        super().__init__(*args, **kwargs)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        for _name, command in self.commands.items():
            if hasattr(command, "aliases") and cmd_name in command.aliases:
                return command
        return None

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str, click.Command, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            cmd_name = args[0] if args else ""
            if cmd_name in self.suggestions:
                raise click.UsageError(
                    f"No such command '{cmd_name}'.\n"
                    f"\n"
                    f"Did you mean:\n"
                    f"  {self.suggestions[cmd_name]}"
                ) from None
            raise

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except click.NoSuchOption as e:
            if _raw_mode(ctx):
                raise

            if _assist_enabled(ctx):
                failed_command = _failed_command(ctx, e.option_name)
                explanation = explain_error(
                    failed_command,
                    f"Error: No such option: {e.option_name}",
                    calling_agent=ctx.find_root().obj.get("resolved_agent"),
                    router=get_router_client(),
                )
                if ctx.find_root().obj.get("output_json"):
                    print_json(explanation.to_dict())
                else:
                    click.echo(render_explanation_text(explanation))
                raise click.exceptions.Exit(1) from e

            hint = _GLOBAL_FLAGS.get(e.option_name)
            if hint:
                raise click.UsageError(
                    f"No such option: {e.option_name}\n"
                    f"\n"
                    f"Hint: {e.option_name} is a global flag — place it before the"
                    f" command name.\n"
                    f"\n"
                    f"  Correct:  {hint}"
                ) from e
            raise


def _raw_mode(ctx: click.Context) -> bool:
    root_obj = ctx.find_root().obj or {}
    return bool(root_obj.get("raw"))


def _assist_enabled(ctx: click.Context) -> bool:
    root_obj = ctx.find_root().obj or {}
    if bool(root_obj.get("raw")):
        return False
    return bool(root_obj.get("assist"))


def _failed_command(ctx: click.Context, option_name: str | None) -> str:
    argv = "sanctum " + shlex.join(sys.argv[1:])
    if option_name and option_name in argv:
        return argv

    root = ctx.find_root()
    root_params = root.params
    tokens: list[str] = []
    if root_params.get("assist"):
        tokens.append("--assist")
    if root_params.get("env"):
        tokens.extend(["--env", root_params["env"]])
    if root_params.get("agent"):
        tokens.extend(["--agent", root_params["agent"]])
    if root_params.get("user"):
        tokens.extend(["--user", root_params["user"]])
    if root_params.get("yes"):
        tokens.append("--yes")
    if root_params.get("output_json"):
        tokens.append("--json")
    if root_params.get("debug"):
        tokens.append("--debug")

    command_parts = ctx.command_path.split()[1:]
    tokens.extend(command_parts)
    if ctx.invoked_subcommand:
        tokens.append(ctx.invoked_subcommand)
    if option_name:
        tokens.append(option_name)
    tokens.extend(ctx.args)
    return "sanctum " + shlex.join(tokens)
