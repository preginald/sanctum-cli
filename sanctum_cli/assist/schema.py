"""Click command-tree schema generation for CLI assist."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

import click
from click._utils import Sentinel

from sanctum_cli.identity_map import suggest_agent_for


@dataclass(frozen=True)
class ParameterSchema:
    """Serializable metadata for a Click option or argument."""

    name: str
    kind: str
    required: bool
    type: str
    opts: tuple[str, ...] = ()
    secondary_opts: tuple[str, ...] = ()
    choices: tuple[str, ...] = ()
    default: Any = None
    is_flag: bool = False
    multiple: bool = False
    nargs: int = 1


@dataclass(frozen=True)
class CommandSchema:
    """Serializable metadata for a Click command or group."""

    path: tuple[str, ...]
    name: str
    help: str | None
    is_group: bool
    expected_agent: str | None = None
    aliases: tuple[str, ...] = ()
    parameters: tuple[ParameterSchema, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CliSchema:
    """Serializable schema for the registered Sanctum CLI command tree."""

    commands: tuple[CommandSchema, ...]
    global_options: tuple[ParameterSchema, ...]
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_cli_schema(root: click.Group) -> CliSchema:
    """Build a stable schema from a registered Click root group."""

    global_options = tuple(_parameter_schema(param) for param in root.params)
    commands = tuple(_iter_commands(root))
    payload = {
        "commands": [asdict(command) for command in commands],
        "global_options": [asdict(option) for option in global_options],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    digest = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    return CliSchema(commands=commands, global_options=global_options, digest=digest)


def _iter_commands(group: click.Group, prefix: tuple[str, ...] = ()) -> list[CommandSchema]:
    commands: list[CommandSchema] = []
    for name in sorted(group.commands):
        command = group.commands[name]
        path = (*prefix, name)
        is_group = isinstance(command, click.Group)
        commands.append(
            CommandSchema(
                path=path,
                name=name,
                help=command.help,
                is_group=is_group,
                expected_agent=_expected_agent(path),
                aliases=tuple(getattr(command, "aliases", ())),
                parameters=tuple(_parameter_schema(param) for param in command.params),
            )
        )
        if isinstance(command, click.Group):
            commands.extend(_iter_commands(command, path))
    return commands


def _parameter_schema(param: click.Parameter) -> ParameterSchema:
    param_type = param.type
    choices: tuple[str, ...] = ()
    if isinstance(param_type, click.Choice):
        choices = tuple(str(choice) for choice in param_type.choices)

    opts: tuple[str, ...] = ()
    secondary_opts: tuple[str, ...] = ()
    is_flag = False
    if isinstance(param, click.Option):
        opts = tuple(param.opts)
        secondary_opts = tuple(param.secondary_opts)
        is_flag = bool(param.is_flag)

    default = None if isinstance(param.default, Sentinel) else param.default

    return ParameterSchema(
        name=param.name or "",
        kind="option" if isinstance(param, click.Option) else "argument",
        required=bool(param.required),
        type=param_type.name,
        opts=opts,
        secondary_opts=secondary_opts,
        choices=choices,
        default=default,
        is_flag=is_flag,
        multiple=bool(param.multiple),
        nargs=param.nargs,
    )


def _expected_agent(path: tuple[str, ...]) -> str | None:
    if len(path) < 2:
        return None
    return suggest_agent_for(".".join(path[:-1]), path[-1])
