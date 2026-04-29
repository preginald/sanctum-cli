# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e ".[dev]"        # install with dev deps
pytest                         # run all tests
pytest tests/test_auth.py      # run one test file
pytest tests/test_auth.py::test_name -v   # run one test
ruff check .                   # lint
ruff format .                  # format
sanctum --help                 # exercise the installed entry point
```

`pyproject.toml` pins ruff to `line-length = 100`, `target-version = "py311"`, rule sets `E,F,I,W,UP,B,C4,SIM`.

## Architecture

Two cooperating packages under one repo:

- `sanctum_client/` — pure HTTP layer (httpx + retry/backoff), bearer-token auth, agent identity resolution. **No Click, no CLI concerns.** Reused by other tools (e.g. MCP server) — keep it framework-free.
- `sanctum_cli/` — Click-based CLI that consumes `sanctum_client`. Entry point: `sanctum = "sanctum_cli.cli:main"`.

### Click root + late command registration

`cli.py` defines a custom `AliasedGroup` and the global `main` group with cross-cutting flags (`--env`, `--agent`, `--user`, `--yes`, `--json`, `--debug`). Domain command groups are imported and `add_command`-ed **after** `main` is defined (note the `# ruff: noqa: E402` — this ordering is intentional). When adding a new domain, follow the same late-import pattern in `cli.py`.

Each domain lives in `sanctum_cli/domains/<name>.py` as its own `@click.group()`. Trailing-underscore filenames (`search_.py`, `artefacts_.py`) avoid shadowing stdlib/builtins.

### Auth model — agent vs user

`main` requires either `--agent <name>` or `--user <email>` (except for `login`, `version`). `auth.ensure_auth` resolves this:

- `--agent` → `sanctum_client.identity.resolve_agent_token` reads `SANCTUM_TOKEN_<AGENT>` env vars (and optional `.env.<agent>` files in a configured env dir). Token map mirrors **SYS-057** (architect, scribe, sentinel, surgeon, oracle, chat, hermes, mock, guardian). The `operator` identity is **explicitly rejected** — it is reserved for human use; AI agents must pick a specific identity (see DOC-111).
- `--user` → loads (or interactively obtains, with optional 2FA via `SANCTUM_TOTP_SECRET`) a personal access token saved under `~/.sanctum/users/<sha256-of-email>.txt` with `0o600`.

Resolved agent name is stashed in `ctx.obj["resolved_agent"]` for downstream identity checks.

### Identity guard (`identity_map.py`)

`DOMAIN_AGENT_MAP` maps `"<domain>.<command>"` → expected agent (or `None` for any). Each domain command should call `check_command_identity("<domain>", "<command>", ctx.obj.get("resolved_agent"))` near the top — it warns on mismatch but does not abort. When adding a new command, add a corresponding entry to the map (omit or use `None` for read-only commands that any agent may run).

### HTTP client conventions (`sanctum_client/client.py`)

- Module-level singleton `httpx.Client`; reset via `set_api_base` / `close_client`.
- `_request` retries `502/503/504` and connection errors up to 3× with exponential backoff (0.5, 1, 2s).
- `post` and `put` return `{"error": True, "status_code": 422, ...}` on validation errors instead of raising — domain commands inspect the dict.
- `_check_upstream` logs a redacted token hint on 401/403 before raising.

### Output (`display.py`)

All user-facing output goes through `display.py` helpers (`print_table`, `print_json`, `print_key_value`, `print_success`, `print_error`, `print_warning`) using `rich`. Domain commands branch on `ctx.obj["output_json"]` to choose JSON vs. human-friendly rendering.

### Tests

`tests/conftest.py` provides `temp_home` (redirects `~/.sanctum` via monkeypatching `DEFAULT_CONFIG_DIR` / `DEFAULT_TOKENS_DIR` / `USER_TOKENS_DIR`), `mock_agent_tokens` (sets `SANCTUM_TOKEN_*` env vars), and an autouse `clean_client` that closes the httpx singleton between tests. Use `pytest-httpx` for API mocking.

## Reference docs (read via MCP, not the filesystem)

- **SYS-057** — agent identity architecture; token map here mirrors that spec.
- **DOC-111** — agent reference / identity guide referenced in error messages.
