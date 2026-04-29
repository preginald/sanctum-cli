# AGENTS.md

## Commands

- Install for local development with `pip install -e ".[dev]"`.
- Run all tests with `pytest`; run a file with `pytest tests/test_auth.py`; run one test with `pytest tests/test_auth.py::test_name -v`.
- Lint with `ruff check .`; format with `ruff format .`. Ruff is configured in `pyproject.toml` for Python 3.11, line length 100, double quotes, and rules `E,F,I,W,UP,B,C4,SIM`.
- Exercise the installed CLI entrypoint with `sanctum --help` or `sanctum --version` after editable install.

## Architecture

- This repo has two packages: `sanctum_client/` is the framework-free HTTP/auth layer; `sanctum_cli/` is the Click CLI and should own CLI concerns.
- The console script is `sanctum = "sanctum_cli.cli:main"`.
- `sanctum_cli/cli.py` defines `main` first, then imports domain groups and calls `main.add_command(...)`; keep new domain registration in that late-import block.
- Domain commands live in `sanctum_cli/domains/<name>.py` as Click groups. Some filenames intentionally have trailing underscores, such as `search_.py` and `artefacts_.py`, to avoid name collisions.

## Auth And Identity

- Most commands require either `--agent <name>` or `--user <email>`; `login` and `version` are exceptions.
- Do not use `--agent operator`: `auth.ensure_auth` explicitly rejects it even though `README.md` has a stale example.
- Agent tokens resolve from `SANCTUM_TOKEN_<AGENT>` env vars and optional `.env.<agent>` files from the configured env dir; supported short names are in `sanctum_client/identity.py`.
- User auth stores PATs under `~/.sanctum/users/<sha256-prefix>.txt` with `0o600`; tests redirect this via fixtures.
- New domain commands should call `check_command_identity("<domain>", "<command>", ctx.obj.get("resolved_agent"))` near the top and update `DOMAIN_AGENT_MAP` in `sanctum_cli/identity_map.py`. Mismatches warn but do not abort.

## HTTP And Output Conventions

- `sanctum_client/client.py` uses a module-level `httpx.Client`; tests rely on `close_client()` cleanup and `set_api_base()` resetting the singleton.
- Client requests retry `502/503/504` and connection errors up to 3 times with exponential backoff.
- `post()` and `put()` return an error dict for HTTP 422 instead of raising; domain commands should inspect that result.
- All user-facing CLI output should go through `sanctum_cli/display.py`; domain commands should branch on `ctx.obj["output_json"]` for JSON output.

## Tests

- Tests use `pytest-httpx` for API calls; add mocked responses with exact URLs including the API base.
- `tests/conftest.py` provides `temp_home`, `mock_agent_tokens`, and an autouse `clean_client` fixture; use these rather than touching the real `~/.sanctum` or leaving the HTTP singleton open.
