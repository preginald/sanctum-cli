"""Observability domain commands.

Sanctum Router error recovery metrics, prompt improvement pipeline,
and correction telemetry reports.
"""

from __future__ import annotations

import click

from sanctum_cli.assist.events import get_pattern_stats, query_events
from sanctum_cli.assist.feedback import generate_correction_report
from sanctum_cli.auth import check_command_identity
from sanctum_cli.display import print_json, print_table


def _parse_period(period: str) -> int:
    unit = period[-1]
    value = int(period[:-1]) if len(period) > 1 else 7
    if unit == "h":
        return max(1, value // 24)
    return value


@click.group()
def observability() -> None:
    """Query Router observability metrics and recovery stats."""


@observability.command()
@click.option("--period", "-p", default="7d", help="Analysis period (e.g. 7d, 24h)")
@click.pass_context
def recovery_stats(ctx: click.Context, period: str) -> None:
    """Show error recovery metrics: repair_success_rate, top errors, pattern effectiveness."""
    check_command_identity("observability", "recovery-stats", ctx.obj.get("resolved_agent"))

    days = _parse_period(period)
    stats = get_pattern_stats(period_days=days)

    if ctx.obj.get("output_json"):
        print_json(
            {
                "period": period,
                "status": "live" if stats["total_events"] > 0 else "no_data",
                "stats": stats,
            }
        )
        return

    click.echo()
    click.echo(f"  Recovery Stats (period: {period})")
    click.echo()

    if stats["total_events"] == 0:
        click.echo("  No recovery events recorded yet.")
        click.echo(
            "  Events are recorded automatically when CLI Assist corrects malformed commands."
        )
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
            title="Recovery Pattern Effectiveness (static)",
        )
        return

    click.echo(f"  Total events: {stats['total_events']}")
    click.echo()

    if stats["patterns"]:
        rows = []
        for pat, info in sorted(stats["patterns"].items()):
            rows.append(
                [
                    pat,
                    f"{info['avg_confidence']:.0%}",
                    f"{info['success_rate']:.0%}",
                    str(info["count"]),
                ]
            )
        print_table(
            ["Pattern", "Avg Confidence", "Success Rate", "Count"],
            rows,
            title="Pattern Effectiveness (live)",
        )

    acceptance = stats.get("acceptance")
    if acceptance:
        a = acceptance["accepted"]
        r = acceptance["rejected"]
        p = acceptance["pending_feedback"]
        total_with_feedback = a + r
        click.echo()
        click.echo(f"  User acceptance: {a} accepted, {r} rejected, {p} pending feedback")
        if total_with_feedback > 0:
            rate = a / total_with_feedback
            click.echo(f"  Acceptance rate:  {rate:.0%}")
        click.echo()

    if stats["by_domain"]:
        domain_rows = [[dom, str(cnt)] for dom, cnt in sorted(stats["by_domain"].items())]
        print_table(["Domain", "Events"], domain_rows, title="By Domain")


@observability.command()
@click.option("--period", "-p", default="7d", help="Analysis period")
@click.option("--min-confidence", default=0.7, type=float, help="Minimum confidence threshold")
@click.pass_context
def prompt_insights(ctx: click.Context, period: str, min_confidence: float) -> None:
    """Analyse Router logs to identify prompt improvement candidates."""
    check_command_identity("observability", "prompt-insights", ctx.obj.get("resolved_agent"))

    days = _parse_period(period)
    events = query_events(period_days=days)
    candidates = _generate_insight_candidates(events, min_confidence)

    if ctx.obj.get("output_json"):
        print_json(
            {
                "period": period,
                "min_confidence": min_confidence,
                "status": "live" if events else "no_data",
                "total_events": len(events),
                "candidates": candidates,
            }
        )
        return

    click.echo()
    click.echo(
        f"  Prompt Improvement Insights (period: {period}, min_confidence: {min_confidence})"
    )
    click.echo()

    if not candidates:
        click.echo("  No improvement candidates found in the current period.")
        click.echo("  More data is needed — recovery events are recorded automatically")
        click.echo("  when CLI Assist corrects malformed commands.")
        return

    click.echo("  Suggested improvements:")
    click.echo()
    for i, c in enumerate(candidates, 1):
        click.echo(f"    {i}. [{c['confidence']:.0%}] {c['suggestion']}")
        click.echo(f"       Evidence: {c['evidence']}")
        click.echo()


@observability.command("correction-report")
@click.option("--period", "-p", default="7d", help="Analysis period (e.g. 7d, 24h)")
@click.option("--top", "-t", default=10, type=int, help="Number of top confusing commands")
@click.pass_context
def correction_report(ctx: click.Context, period: str, top: int) -> None:
    """Show a structured correction telemetry report from the local event store."""
    check_command_identity("observability", "correction-report", ctx.obj.get("resolved_agent"))

    days = _parse_period(period)
    report_data = generate_correction_report(period_days=days, top_n=top)

    if ctx.obj.get("output_json"):
        print_json(report_data)
        return

    click.echo()
    click.echo(f"  Correction Report (period: {period})")
    click.echo()

    if report_data["status"] == "no_data":
        click.echo("  No correction events recorded yet.")
        click.echo("  Events are recorded when CLI Assist repairs malformed commands.")
        click.echo()
        return

    r = report_data["report"]

    click.echo(f"  Total events: {report_data['total_events']}")
    click.echo()

    top_cmds = r.get("top_confusing_commands", [])
    if top_cmds:
        cmd_rows = [[c["command"], str(c["errors"])] for c in top_cmds]
        print_table(["Command", "Errors"], cmd_rows, title="Top Confusing Commands")

    error_classes = r.get("error_classes", [])
    if error_classes:
        ec_rows = [[ec[0], str(ec[1])] for ec in error_classes]
        print_table(["Error Class", "Count"], ec_rows, title="Error Classes")

    pattern_freq = r.get("pattern_frequency", [])
    if pattern_freq:
        pf_rows = [[pf[0], str(pf[1])] for pf in pattern_freq]
        print_table(["Pattern", "Count"], pf_rows, title="Pattern Frequency")

    domain_breakdown = r.get("domain_breakdown", [])
    if domain_breakdown:
        db_rows = [[db[0], str(db[1])] for db in domain_breakdown]
        print_table(["Domain", "Events"], db_rows, title="Events by Domain")


def _generate_insight_candidates(events: list, min_confidence: float) -> list[dict]:
    candidates: list[dict] = []
    low_confidence = [e for e in events if e.confidence < min_confidence]

    if low_confidence:
        candidates.append(
            {
                "type": "low_confidence_repair",
                "suggestion": (
                    f"Review {len(low_confidence)} low-confidence repairs "
                    f"(confidence < {min_confidence}) in the event store"
                ),
                "confidence": 0.75,
                "evidence": (
                    f"{len(low_confidence)} events below {min_confidence} confidence threshold"
                ),
            }
        )

    missing_fields = [e for e in events if e.error_class == "missing_required_option"]
    if missing_fields:
        fields = set()
        for e in missing_fields:
            fields.update(e.inferred_intent.split() if " " in e.inferred_intent else [])
        candidates.append(
            {
                "type": "parameter_alias",
                "suggestion": "Review missing required option patterns for alias candidates",
                "confidence": 0.82,
                "evidence": (f"{len(missing_fields)} events with missing required options"),
            }
        )

    return [c for c in candidates if c["confidence"] >= min_confidence]


# ruff: noqa: E501
