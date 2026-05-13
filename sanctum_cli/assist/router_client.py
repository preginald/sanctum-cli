"""Client for Sanctum Router CLI intent interpretation."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import click
import httpx

from sanctum_cli.assist.schema import build_cli_schema
from sanctum_cli.token_provider import (
    TokenExpiredError,
    TokenProvider,
    TokenUnavailableError,
    has_router_token_source,
)

log = logging.getLogger(__name__)

RouterInterpretMode = Literal["error_repair", "natural_language", "validate"]


DEFAULT_ROUTER_URL = "https://router.digitalsanctum.com.au"
CLI_INTERPRET_PATH = "/v1/cli-interpret"


class RouterClientError(RuntimeError):
    """Raised when Router interpretation cannot be completed."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class RouterOperationPlanStep:
    """Typed operation plan step returned by Router."""

    domain: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    risk: str = "unknown"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RouterOperationPlanStep:
        return cls(
            domain=str(data.get("domain", "")),
            action=str(data.get("action", "")),
            parameters=dict(data.get("parameters") or {}),
            risk=str(data.get("risk", "unknown")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RouterInterpretRequest:
    """Request body for ``POST /v1/cli-interpret``."""

    mode: RouterInterpretMode
    calling_agent: str
    failed_command: str | None = None
    error_output: str | None = None
    intent: str | None = None
    cwd: str | None = None
    available_domains: tuple[str, ...] = ()
    schema_digest: str | None = None
    cli_schema: dict[str, Any] | None = None
    sanitized_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "failed_command": self.failed_command,
            "error_output": self.error_output,
            "intent": self.intent,
            "calling_agent": self.calling_agent,
            "cwd": self.cwd,
            "available_domains": list(self.available_domains),
            "schema_digest": self.schema_digest,
            "cli_schema": self.cli_schema,
            "sanitized_context": self.sanitized_context,
        }


@dataclass(frozen=True)
class RouterInterpretResponse:
    """Typed response from ``POST /v1/cli-interpret``."""

    status: str
    confidence: float
    match_type: str
    inferred_intent: str
    operation_plan: tuple[RouterOperationPlanStep, ...]
    needs_confirmation: bool
    message: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RouterInterpretResponse:
        return cls(
            status=str(data["status"]),
            confidence=float(data["confidence"]),
            match_type=str(data["match_type"]),
            inferred_intent=str(data["inferred_intent"]),
            operation_plan=tuple(
                RouterOperationPlanStep.from_dict(step)
                for step in data.get("operation_plan", [])
                if isinstance(step, dict)
            ),
            needs_confirmation=bool(data["needs_confirmation"]),
            message=str(data["message"]),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["operation_plan"] = [step.to_dict() for step in self.operation_plan]
        return payload


def build_router_interpret_request(
    *,
    mode: RouterInterpretMode,
    calling_agent: str,
    root: click.Group | None = None,
    failed_command: str | None = None,
    error_output: str | None = None,
    intent: str | None = None,
    cwd: str | None = None,
    sanitized_context: dict[str, Any] | None = None,
) -> RouterInterpretRequest:
    """Build a Router request with schema metadata and sanitized caller context."""

    if mode == "error_repair" and not (failed_command and error_output):
        raise ValueError("error_repair mode requires failed_command and error_output")
    if mode == "natural_language" and not intent:
        raise ValueError("natural_language mode requires intent")
    if mode == "validate" and not intent and not failed_command:
        raise ValueError("validate mode requires intent or failed_command")

    schema_digest: str | None = None
    cli_schema: dict[str, Any] | None = None
    available_domains: tuple[str, ...] = ()
    if root is not None:
        schema = build_cli_schema(root)
        schema_digest = schema.digest
        cli_schema = schema.to_dict()
        available_domains = tuple(
            sorted({command.path[0] for command in schema.commands if len(command.path) >= 1})
        )

    return RouterInterpretRequest(
        mode=mode,
        failed_command=failed_command,
        error_output=error_output,
        intent=intent,
        calling_agent=calling_agent,
        cwd=cwd or str(Path.cwd()),
        available_domains=available_domains,
        schema_digest=schema_digest,
        cli_schema=cli_schema,
        sanitized_context=sanitized_context or {},
    )


class RouterClient:
    """Synchronous client for Router-backed CLI interpretation."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        token_provider: TokenProvider | None = None,
        timeout: float = 90.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("SANCTUM_ROUTER_URL") or DEFAULT_ROUTER_URL).rstrip(
            "/"
        )
        self.token = (
            token
            if token is not None
            else os.getenv("SANCTUM_ROUTER_TOKEN") or os.getenv("SANCTUM_ROUTER_JWT")
        )
        self.token_provider = token_provider
        self.timeout = timeout

    def _get_authorization_header(self) -> dict[str, str]:
        """Resolve the current bearer token, preflighting expiry if a provider is available."""
        if self.token_provider:
            try:
                token = self.token_provider.get_token()
            except (TokenUnavailableError, TokenExpiredError) as exc:
                raise RouterClientError(str(exc)) from exc
            return {"Authorization": f"Bearer {token}"}
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        raise RouterClientError("SANCTUM_ROUTER_TOKEN is required for Router CLI interpretation")

    def interpret(self, request: RouterInterpretRequest) -> RouterInterpretResponse:
        """Send an interpretation request to Router and validate the response shape."""

        headers = self._get_authorization_header()

        try:
            response = httpx.post(
                f"{self.base_url}{CLI_INTERPRET_PATH}",
                json=request.to_dict(),
                headers=headers,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise RouterClientError(f"Router interpretation request failed: {exc}") from exc

        if response.status_code == 401 and self.token_provider:
            log.info("Router returned 401, forcing token refresh and retrying once...")
            try:
                new_token = self.token_provider.force_refresh()
            except (TokenUnavailableError, RuntimeError) as exc:
                raise RouterClientError(
                    f"Router request failed with HTTP 401 and token refresh failed: {exc}",
                    status_code=401,
                ) from exc
            headers = {"Authorization": f"Bearer {new_token}"}
            try:
                response = httpx.post(
                    f"{self.base_url}{CLI_INTERPRET_PATH}",
                    json=request.to_dict(),
                    headers=headers,
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:
                raise RouterClientError(
                    f"Router interpretation request failed after token refresh: {exc}"
                ) from exc

        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                err = body.get("error", body.get("detail", {}))
                if isinstance(err, dict):
                    detail = err.get("message", "") or err.get("detail", "")
                elif isinstance(err, str):
                    detail = err
            except Exception:
                pass
            msg = f"Router interpretation failed with HTTP {response.status_code}"
            if detail:
                msg += f": {detail}"
            raise RouterClientError(msg, status_code=response.status_code)

        try:
            payload = response.json()
            return RouterInterpretResponse.from_dict(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise RouterClientError("Router interpretation response had an invalid shape") from exc

    def interpret_error(
        self,
        *,
        failed_command: str,
        error_output: str,
        calling_agent: str,
        root: click.Group | None = None,
        sanitized_context: dict[str, Any] | None = None,
    ) -> RouterInterpretResponse:
        """Interpret a malformed CLI command through Router."""

        request = build_router_interpret_request(
            mode="error_repair",
            failed_command=failed_command,
            error_output=error_output,
            calling_agent=calling_agent,
            root=root,
            sanitized_context=sanitized_context,
        )
        return self.interpret(request)

    def interpret_intent(
        self,
        *,
        intent: str,
        calling_agent: str,
        root: click.Group | None = None,
        sanitized_context: dict[str, Any] | None = None,
    ) -> RouterInterpretResponse:
        """Interpret natural-language CLI intent through Router."""

        request = build_router_interpret_request(
            mode="natural_language",
            intent=intent,
            calling_agent=calling_agent,
            root=root,
            sanitized_context=sanitized_context,
        )
        return self.interpret(request)

    def interpret_validate(
        self,
        *,
        domain: str,
        action: str,
        params: dict[str, Any],
        calling_agent: str,
    ) -> RouterInterpretResponse:
        """ "Send parsed command arguments to Router validate mode."""

        failed_command = f"sanctum --agent {calling_agent} {domain} {action}"
        for key, value in params.items():
            flag = "--" + key.replace("_", "-")
            failed_command += f" {flag} {value}"

        request = build_router_interpret_request(
            mode="validate",
            failed_command=failed_command,
            intent=failed_command,
            calling_agent=calling_agent,
        )
        return self.interpret(request)


def get_router_client() -> RouterClient | None:
    """Return a RouterClient if any token source exists, else None.

    Supports explicit env var, cached tokens, and OIDC client_credentials.
    """
    if not has_router_token_source():
        return None
    explicit = os.getenv("SANCTUM_ROUTER_TOKEN") or os.getenv("SANCTUM_ROUTER_JWT")
    from sanctum_cli.token_provider import RouterTokenProvider

    provider = RouterTokenProvider(explicit_token=explicit)
    return RouterClient(token_provider=provider, token=explicit)
