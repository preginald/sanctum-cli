"""Client for Sanctum Router CLI intent interpretation."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import click
import httpx

from sanctum_cli.assist.schema import build_cli_schema

RouterInterpretMode = Literal["error_repair", "natural_language"]


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

    schema_digest: str | None = None
    available_domains: tuple[str, ...] = ()
    if root is not None:
        schema = build_cli_schema(root)
        schema_digest = schema.digest
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
        sanitized_context=sanitized_context or {},
    )


class RouterClient:
    """Synchronous client for Router-backed CLI interpretation."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("SANCTUM_ROUTER_URL") or DEFAULT_ROUTER_URL).rstrip(
            "/"
        )
        self.token = (
            token
            if token is not None
            else os.getenv("SANCTUM_ROUTER_TOKEN") or os.getenv("SANCTUM_ROUTER_JWT")
        )
        self.timeout = timeout

    def interpret(self, request: RouterInterpretRequest) -> RouterInterpretResponse:
        """Send an interpretation request to Router and validate the response shape."""

        if not self.token:
            raise RouterClientError(
                "SANCTUM_ROUTER_TOKEN is required for Router CLI interpretation"
            )

        try:
            response = httpx.post(
                f"{self.base_url}{CLI_INTERPRET_PATH}",
                json=request.to_dict(),
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise RouterClientError(f"Router interpretation request failed: {exc}") from exc

        if response.status_code >= 400:
            raise RouterClientError(
                f"Router interpretation failed with HTTP {response.status_code}",
                status_code=response.status_code,
            )

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


def get_router_client() -> RouterClient | None:
    """Return a RouterClient if a Router token is configured, else None."""
    token = os.getenv("SANCTUM_ROUTER_TOKEN") or os.getenv("SANCTUM_ROUTER_JWT")
    if not token:
        return None
    return RouterClient(token=token)
