"""Event store for error recovery events with file-based persistence."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_EVENTS_DIR = Path.home() / ".sanctum" / "events"
_EVENTS_DIR: Path = DEFAULT_EVENTS_DIR
_lock = threading.Lock()


def set_events_dir(path: str | Path) -> None:
    global _EVENTS_DIR
    _EVENTS_DIR = Path(path)


def _ensure_dir() -> Path:
    _EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    return _EVENTS_DIR


@dataclass
class RecoveryEvent:
    pattern: str
    error_class: str
    inferred_intent: str
    risk: str
    confidence: float
    generated_command: str | None
    status: str
    calling_agent: str | None
    domain: str | None
    action: str | None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryEvent:
        return cls(
            pattern=str(data.get("pattern", "")),
            error_class=str(data.get("error_class", "")),
            inferred_intent=str(data.get("inferred_intent", "")),
            risk=str(data.get("risk", "unknown")),
            confidence=float(data.get("confidence", 0.0)),
            generated_command=data.get("generated_command"),
            status=str(data.get("status", "")),
            calling_agent=data.get("calling_agent"),
            domain=data.get("domain"),
            action=data.get("action"),
            timestamp=str(data.get("timestamp", datetime.now(UTC).isoformat())),
        )


def record_event(event: RecoveryEvent) -> None:
    date_prefix = event.timestamp[:10]
    with _lock:
        _ensure_dir()
        filepath = _EVENTS_DIR / f"{date_prefix}.jsonl"
        with open(filepath, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")


def query_events(
    period_days: int = 7,
    *,
    pattern: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[RecoveryEvent]:
    results: list[RecoveryEvent] = []
    now = time.time()
    cutoff = now - (period_days * 86400)

    files = sorted(_EVENTS_DIR.glob("*.jsonl"), reverse=True)
    for filepath in files:
        try:
            file_mtime = filepath.stat().st_mtime
        except OSError:
            continue
        if file_mtime < cutoff:
            continue
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = RecoveryEvent.from_dict(json.loads(line))
                except (json.JSONDecodeError, TypeError):
                    continue
                if pattern and ev.pattern != pattern:
                    continue
                if domain and ev.domain != domain:
                    continue
                if status and ev.status != status:
                    continue
                results.append(ev)
                if len(results) >= limit:
                    return results

    return results


def get_pattern_stats(period_days: int = 7) -> dict[str, Any]:
    events = query_events(period_days=period_days)
    total = len(events)
    if total == 0:
        return {"total_events": 0, "patterns": {}, "by_domain": {}, "by_status": {}}

    patterns: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for ev in events:
        patterns[ev.pattern] = patterns.get(ev.pattern, 0) + 1
        dom = ev.domain or "unknown"
        by_domain[dom] = by_domain.get(dom, 0) + 1
        by_status[ev.status] = by_status.get(ev.status, 0) + 1

    pattern_effectiveness = {}
    for pat, count in patterns.items():
        pattern_events = [e for e in events if e.pattern == pat]
        suggestions = [
            e for e in pattern_events
            if e.status in ("assist_suggestion", "router_interpreted")
        ]
        success_rate = len(suggestions) / count if count > 0 else 0.0
        avg_confidence = sum(e.confidence for e in pattern_events) / count if count > 0 else 0.0
        pattern_effectiveness[pat] = {
            "count": count,
            "success_rate": round(success_rate, 2),
            "avg_confidence": round(avg_confidence, 2),
        }

    return {
        "total_events": total,
        "patterns": pattern_effectiveness,
        "by_domain": by_domain,
        "by_status": by_status,
    }
