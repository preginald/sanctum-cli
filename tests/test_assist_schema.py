"""Tests for CLI assist schema generation."""

from sanctum_cli.assist.schema import build_cli_schema
from sanctum_cli.cli import main


def test_schema_includes_registered_command_tree():
    schema = build_cli_schema(main)
    paths = {command.path for command in schema.commands}

    assert ("tickets",) in paths
    assert ("tickets", "show") in paths
    assert ("projects", "create") in paths
    assert ("flow", "definition-create") in paths


def test_schema_includes_global_flags_and_choices():
    schema = build_cli_schema(main)
    global_opts = {opt.name: opt for opt in schema.global_options}

    assert "output_json" in global_opts
    assert "--json" in global_opts["output_json"].opts
    assert "agent" in global_opts
    assert "env" in global_opts
    assert global_opts["env"].choices == ("local", "prod")


def test_schema_includes_expected_agent_from_identity_map():
    schema = build_cli_schema(main)
    commands = {command.path: command for command in schema.commands}

    assert commands[("tickets", "create")].expected_agent == "surgeon"
    assert commands[("articles", "create")].expected_agent == "scribe"
    assert commands[("flow", "definition-create")].expected_agent == "architect"
    assert commands[("tickets", "show")].expected_agent is None


def test_schema_digest_is_stable():
    first = build_cli_schema(main)
    second = build_cli_schema(main)

    assert first.digest == second.digest
    assert first.digest.startswith("sha256:")
