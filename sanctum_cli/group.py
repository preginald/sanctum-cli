"""Custom Click group with alias support and 'did you mean' suggestions."""

import click

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
