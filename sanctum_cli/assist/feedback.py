"""Sanitized correction telemetry and feedback reports.

Generates structured correction reports from local event data for
identifying recurring CLI confusion patterns.
"""

from __future__ import annotations

from typing import Any

from sanctum_cli.assist.events import query_events


def generate_correction_report(
    period_days: int = 7,
    top_n: int = 10,
) -> dict[str, Any]:
    """Generate a comprehensive correction report from the local event store.

    Returns:
        A dict with period metadata and a ``report`` key containing:
        - ``top_confusing_commands`` — most error-prone (domain.action) pairs
        - ``error_classes`` — breakdown by error type
        - ``pattern_frequency`` — count per repair pattern
        - ``pattern_confidence`` — avg/min/max confidence per pattern
        - ``domain_breakdown`` — events grouped by domain
    """
    events = query_events(period_days=period_days)

    if not events:
        return {
            "period_days": period_days,
            "total_events": 0,
            "status": "no_data",
        }

    domain_action_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    for ev in events:
        dom = ev.domain or "unknown"
        act = ev.action or "unknown"
        key = f"{dom}.{act}"
        domain_action_counts[key] = domain_action_counts.get(key, 0) + 1
        domain_counts[dom] = domain_counts.get(dom, 0) + 1

    error_class_counts: dict[str, int] = {}
    for ev in events:
        error_class_counts[ev.error_class] = error_class_counts.get(ev.error_class, 0) + 1

    pattern_counts: dict[str, int] = {}
    for ev in events:
        pattern_counts[ev.pattern] = pattern_counts.get(ev.pattern, 0) + 1

    top_confusing = sorted(domain_action_counts.items(), key=lambda x: -x[1])[:top_n]

    confidence_by_pattern: dict[str, list[float]] = {}
    for ev in events:
        confidence_by_pattern.setdefault(ev.pattern, []).append(ev.confidence)

    pattern_confidence = {}
    for pat, confs in confidence_by_pattern.items():
        pattern_confidence[pat] = {
            "avg": round(sum(confs) / len(confs), 2),
            "min": round(min(confs), 2),
            "max": round(max(confs), 2),
        }

    statuses: dict[str, int] = {}
    for ev in events:
        statuses[ev.status] = statuses.get(ev.status, 0) + 1

    return {
        "period_days": period_days,
        "total_events": len(events),
        "status": "live",
        "report": {
            "top_confusing_commands": [
                {"command": cmd, "errors": count} for cmd, count in top_confusing
            ],
            "error_classes": sorted(error_class_counts.items(), key=lambda x: -x[1]),
            "pattern_frequency": sorted(pattern_counts.items(), key=lambda x: -x[1]),
            "pattern_confidence": pattern_confidence,
            "domain_breakdown": sorted(domain_counts.items(), key=lambda x: -x[1]),
            "status_breakdown": sorted(statuses.items(), key=lambda x: -x[1]),
        },
    }
