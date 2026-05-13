"""Natural-language assist domain command.

Phase 3: Accept a natural-language intent, interpret it via Sanctum Router,
validate the resulting operation plan against the CLI schema, classify safety,
and present the plan for review or execution.
"""

from __future__ import annotations

import shlex
import sys
from typing import Any

import click

from sanctum_cli.assist.errors import explain_error, render_explanation_text
from sanctum_cli.assist.intent import (
    OperationPlan,
    OperationStep,
    classify_risk,
    validate_operation_plan,
)
from sanctum_cli.assist.router_client import RouterClientError, get_router_client
from sanctum_cli.assist.safety import check_operation
from sanctum_cli.assist.schema import build_cli_schema
from sanctum_cli.assist.session import Session, SessionStore, get_session_store
from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json


def _router_plan_to_operation_plan(
    intent: str,
    resp: Any,
) -> OperationPlan:
    """Convert a RouterInterpretResponse to an OperationPlan with mapped risk levels."""
    steps_raw = getattr(resp, "operation_plan", ())
    operations: list[OperationStep] = []
    for i, step in enumerate(steps_raw):
        operations.append(
            OperationStep(
                id=f"step{i + 1}",
                domain=step.domain,
                action=step.action,
                parameters=dict(step.parameters or {}),
                risk=classify_risk(step.domain, step.action),
                needs_confirmation=resp.needs_confirmation,
            )
        )
    return OperationPlan(
        intent=intent,
        operations=tuple(operations),
        resolved_entities={},
    )


def _get_root_group(ctx: click.Context) -> click.Group:
    """Resolve the root Click Group for schema building."""
    root = ctx.obj.get("root_group")
    if root is not None:
        return root
    root_cmd = ctx.find_root().command
    if isinstance(root_cmd, click.Group):
        return root_cmd
    raise RuntimeError("Cannot resolve root Click group for schema building")


@click.command()
@click.argument("intent")
@click.option("--session-id", default=None, help="Session ID for conversational context")
@click.pass_context
def assist(ctx: click.Context, intent: str, session_id: str | None) -> None:
    """Interpret a natural-language intent and produce a validated operation plan.

    Reads the CLI command schema, sends the intent to Sanctum Router for interpretation,
    validates the returned operation plan, and presents the results.

    Use --session-id to continue a previous conversation with context recall.

    Examples:

        sanctum --agent oracle assist "find milestones for Sanctum Router"

        sanctum --agent surgeon --json assist "list open tickets for project X"
    """
    check_command_identity("assist", "assist", ctx.obj.get("resolved_agent"))
    output_json = ctx.obj.get("output_json")
    calling_agent = ctx.obj.get("resolved_agent")
    store = get_session_store()

    session = _resolve_session(store, session_id, calling_agent)
    if session is not None:
        session.add_message("user", intent)
        store.save(session)

    router = get_router_client()
    if router is None:
        if output_json:
            print_json(
                {
                    "status": "router_unavailable",
                    "message": (
                        "SANCTUM_ROUTER_TOKEN is required for natural-language interpretation"
                    ),
                }
            )
        else:
            print_error("SANCTUM_ROUTER_TOKEN is required for natural-language interpretation")
        sys.exit(1)

    root = _get_root_group(ctx)
    schema = build_cli_schema(root)

    context = session.recent_context(5) if session else None
    sanitized_context = {"conversation_history": context} if context else {}

    try:
        response = router.interpret_intent(
            intent=intent,
            calling_agent=calling_agent or "unknown",
            root=root,
            sanitized_context=sanitized_context,
        )
    except RouterClientError as exc:
        if output_json:
            print_json({"status": "error", "message": str(exc)})
        else:
            print_error(str(exc))
        sys.exit(1)

    plan = _router_plan_to_operation_plan(intent, response)

    validation = validate_operation_plan(plan, schema, calling_agent=calling_agent)

    safety_checks = [check_operation(op.domain, op.action).to_dict() for op in plan.operations]

    if session is not None:
        session.add_message("assistant", response.message)
        store.save(session)

    if output_json:
        output = {
            "status": "validated" if validation.valid else "validation_failed",
            "intent": intent,
            "inferred_intent": response.inferred_intent,
            "confidence": response.confidence,
            "needs_confirmation": response.needs_confirmation,
            "message": response.message,
            "validation": validation.to_dict(),
            "operations": [op.to_dict() for op in plan.operations],
            "safety_checks": safety_checks,
        }
        if session:
            output["session_id"] = session.session_id
        print_json(output)
        return

    click.echo()
    if session:
        click.echo(f"  Session:  {session.session_id}")
    click.echo(f"  Intent:   {intent}")
    click.echo(f"  Inferred: {response.inferred_intent}")
    click.echo(f"  Confidence: {response.confidence:.0%}")
    click.echo()

    if response.message:
        click.echo(f"  {response.message}")
        click.echo()

    if plan.operations:
        click.echo("  Operation Plan:")
        for op in plan.operations:
            risk_icon = _risk_icon(op.risk)
            params = " ".join(
                f"--{k} {v}" if v is not True else f"--{k}" for k, v in op.parameters.items()
            )
            click.echo(
                f"    [{risk_icon} {op.risk}] "
                f"sanctum --agent {calling_agent} {op.domain} {op.action} {params}".rstrip()
            )
        click.echo()

    if not validation.valid:
        click.echo("  Validation Errors:")
        for err in validation.errors:
            click.echo(f"    {err}")
        click.echo()

    has_risky = any(s["rejected"] or s["needs_confirmation"] for s in safety_checks)
    if has_risky:
        click.echo("  Safety Notes:")
        for s in safety_checks:
            risk_icon = _risk_icon(s["risk"])
            note = "CONFIRMATION REQUIRED" if s["needs_confirmation"] else "OK"
            click.echo(f"    [{risk_icon} {s['risk']}] {s['domain']} {s['action']} — {note}")
            if s["rejected"]:
                click.echo(f"      {s['reason']}")
        click.echo()


def _resolve_session(
    store: SessionStore, session_id: str | None, calling_agent: str | None
) -> Session | None:
    if session_id:
        session = store.get(session_id)
        if session:
            return session
        return None
    if calling_agent:
        recent = store.find_by_agent(calling_agent)
        if recent:
            return recent[0]
    return None


def natural_language_execute(ctx: click.Context, intent: str) -> None:
    """Interpret natural language intent via Router and execute the operation plan."""
    ctx.ensure_object(dict)
    root_params = ctx.find_root().params or {}
    calling_agent = ctx.obj.get("resolved_agent") or root_params.get("agent") or "unknown"
    root = _get_root_group(ctx)
    schema = build_cli_schema(root)

    router = get_router_client()
    if router is None:
        raise click.UsageError("SANCTUM_ROUTER_TOKEN required for natural language execution")

    response = router.interpret_intent(
        intent=intent,
        calling_agent=calling_agent,
        root=root,
    )

    plan = _router_plan_to_operation_plan(intent, response)
    validation = validate_operation_plan(plan, schema, calling_agent=calling_agent)
    if not validation.valid:
        errors = "; ".join(str(e) for e in validation.errors)
        raise click.UsageError(f"Operation plan validation failed: {errors}")

    for op in plan.operations:
        safety = check_operation(op.domain, op.action)
        if safety.rejected:
            raise click.UsageError(f"Operation rejected: {op.domain} {op.action} — {safety.reason}")
        if safety.needs_confirmation and not ctx.obj.get("yes"):
            click.echo(f"Confirm: sanctum {op.domain} {op.action}? [y/N]: ", nl=False)
            confirmed = click.getchar().lower() == "y"
            click.echo()
            if not confirmed:
                raise click.UsageError("Operation cancelled by user")

        tokens = _operation_step_to_cli_tokens(op, calling_agent)
        cmd_name, cmd, cmd_args = root.resolve_command(ctx, tokens)
        cmd_ctx = root.make_context("sanctum", tokens, resilient_parsing=False)
        try:
            cmd.invoke(cmd_ctx)
        except (click.ClickException, click.exceptions.Exit, SystemExit):
            raise
        except Exception as e:
            error_output = f"Execution error: {e}"
            failed = "sanctum " + shlex.join(tokens)
            explanation = explain_error(
                failed, error_output, root=root, calling_agent=calling_agent, router=router
            )
            if explanation.status == "assist_suggestion" and explanation.generated_command:
                click.echo(render_explanation_text(explanation))
                tokens2 = _command_tokens_from_string(explanation.generated_command)
                cmd2_name, cmd2, cmd2_args = root.resolve_command(ctx, tokens2)
                cmd2_ctx = root.make_context("sanctum", tokens2, resilient_parsing=False)
                cmd2.invoke(cmd2_ctx)
            else:
                raise


def _operation_step_to_cli_tokens(step: OperationStep, agent: str) -> list[str]:
    tokens = ["--agent", agent, step.domain, step.action]
    for key, value in step.parameters.items():
        flag = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                tokens.append(flag)
        else:
            tokens.extend([flag, str(value)])
    return tokens


def _command_tokens_from_string(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    if tokens and tokens[0].endswith("sanctum"):
        return tokens[1:]
    return tokens


_RISK_ICONS: dict[str, str] = {
    "read": "→",
    "write": "✎",
    "external_effect": "⚡",
    "destructive": "✗",
    "unknown": "?",
}


def _risk_icon(risk: str) -> str:
    return _RISK_ICONS.get(risk, "?")
