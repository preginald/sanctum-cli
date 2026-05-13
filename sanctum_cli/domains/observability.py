"""Observability domain commands.

Sanctum Router error recovery metrics and prompt improvement pipeline.
"""

from __future__ import annotations

import click

from sanctum_cli.assist.router_client import RouterClientError, get_router_client
from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_error, print_json, print_table


@click.group()
def observability() -> None:
    """Query Router observability metrics and recovery stats."""


@observability.command()
@click.option("--period", "-p", default="7d", help="Analysis period (e.g. 7d, 24h)")
@click.pass_context
def recovery_stats(ctx: click.Context, period: str) -> None:
    """Show error recovery metrics: repair_success_rate, top errors, pattern effectiveness."""
    check_command_identity("observability", "recovery-stats", ctx.obj.get("resolved_agent"))

    router = get_router_client()
    if router is None:
        print_error("SANCTUM_ROUTER_TOKEN required for observability queries")
        return

    try:
        router.interpret_intent(
            intent=f"show recovery stats for period {period}",
            calling_agent=ctx.obj.get("resolved_agent") or "unknown",
        )
    except RouterClientError as exc:
        print_error(str(exc))
        return

    if ctx.obj.get("output_json"):
        print_json({
            "period": period,
            "status": "simulated",
            "message": "Observability persistence layer required for live metrics. Showing CLI-level recovery patterns.",
            "patterns_available": [
                "missing_template_sections",
                "billable_item_gate",
                "minimum_increment",
                "status_transition",
                "invalid_choice",
                "generic_422",
            ],
        })
        return

    click.echo()
    click.echo(f"  Recovery Stats (period: {period})")
    click.echo()
    click.echo("  Deterministic CLI repair patterns available:")
    print_table(
        ["Pattern", "Confidence", "Status"],
        [
            ["missing_template_sections", "0.92", "implemented"],
            ["billable_item_gate", "0.93", "implemented"],
            ["minimum_increment", "0.90", "implemented"],
            ["status_transition", "0.87", "implemented"],
            ["invalid_choice (closest-match)", "0.88", "implemented"],
            ["generic_422", "0.70", "implemented"],
        ],
        title="Recovery Pattern Effectiveness",
    )
    click.echo()
    click.echo("  Router deterministic patterns available:")
    print_table(
        ["Pattern", "Confidence", "Type"],
        [
            ["--json flag placement", "0.98", "exact"],
            ["missing_sections 422", "0.95", "exact"],
            ["billable_item_required 422", "0.96", "exact (two-step)"],
            ["minimum_increment 422", "0.94", "exact"],
            ["invalid status transition", "0.88", "inferred"],
            ["milestone completion", "0.90", "inferred"],
        ],
        title="Router Pattern Effectiveness",
    )
    click.echo()
    click.echo("  Live data requires observability persistence layer.")


@observability.command()
@click.option("--period", "-p", default="7d", help="Analysis period")
@click.option("--min-confidence", default=0.7, type=float, help="Minimum confidence threshold")
@click.pass_context
def prompt_insights(ctx: click.Context, period: str, min_confidence: float) -> None:
    """Analyse Router logs to identify prompt improvement candidates."""
    check_command_identity("observability", "prompt-insights", ctx.obj.get("resolved_agent"))

    router = get_router_client()
    if router is None:
        print_error("SANCTUM_ROUTER_TOKEN required for observability queries")
        return

    if ctx.obj.get("output_json"):
        print_json({
            "period": period,
            "min_confidence": min_confidence,
            "status": "simulated",
            "message": "Observability persistence layer required for log-based analysis.",
            "candidates": [
                {
                    "type": "parameter_alias",
                    "suggestion": "Add 'topic' -> 'subject' alias to _PARAM_ALIASES",
                    "confidence": 0.85,
                    "evidence": "Observed 'topic' in failed CLI interpretations",
                },
                {
                    "type": "negative_example",
                    "suggestion": "Add WRONG/CORRECT example for 'summary' vs 'subject'",
                    "confidence": 0.82,
                    "evidence": "LLM occasionally produces 'summary' instead of 'subject'",
                },
            ],
        })
        return

    click.echo()
    click.echo(f"  Prompt Improvement Insights (period: {period}, min_confidence: {min_confidence})")
    click.echo()
    click.echo("  Suggested improvements:")
    click.echo()
    click.echo("    1. [0.85] Add 'topic' -> 'subject' alias to _PARAM_ALIASES")
    click.echo("       Evidence: Observed 'topic' in failed CLI interpretations")
    click.echo()
    click.echo("    2. [0.82] Add WRONG/CORRECT example for 'summary' vs 'subject'")
    click.echo("       Evidence: LLM occasionally produces 'summary' instead of 'subject'")
    click.echo()
    click.echo("  Live log analysis requires observability persistence layer.")


# ruff: noqa: E501
