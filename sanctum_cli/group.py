"""Custom Click group with alias support and 'did you mean' suggestions."""

import click


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
