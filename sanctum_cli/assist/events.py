"""Sanitized assist correction telemetry store with file-based persistence.

Records correction outcomes, user acceptance feedback, and generates
reports for recurring CLI confusion patterns.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_EVENTS_DIR = Path.home() / ".sanctum" / "events"
_EVENTS_DIR: Path = DEFAULT_EVENTS_DIR
_lock = threading.Lock()

# Patterns whose values MUST be redacted before storage.
_SENSITIVE_FLAGS: set[str] = {
    "--api-key",
    "--password",
    "--secret",
    "--token",
    "--bearer",
    "--key",
}
_SENSITIVE_ENV_PREFIX: str = "SANCTUM_TOKEN_"
_JWT_PATTERN: re.Pattern = re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")


def set_events_dir(path: str | Path) -> None:
    global _EVENTS_DIR
    _EVENTS_DIR = Path(path)


def _ensure_dir() -> Path:
    _EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    return _EVENTS_DIR


def redact_command(command: str | None) -> str | None:
    """Redact sensitive values from a CLI command before storage.

    Strips API keys, bearer tokens, passwords, JWT strings, and env-var
    token assignments.  Keeps agent names and user emails intact.
    """
    if not command:
        return command

    tokens = command.split()

    i = 0
    while i < len(tokens):
        lower = tokens[i].lower()
        if lower in _SENSITIVE_FLAGS and i + 1 < len(tokens):
            tokens[i + 1] = "***"
            i += 2
            continue
        if lower.startswith(_SENSITIVE_ENV_PREFIX.lower()):
            parts = tokens[i].split("=", 1)
            if len(parts) == 2:
                tokens[i] = parts[0] + "=***"
            i += 1
            continue
        i += 1

    result = " ".join(tokens)
    result = _JWT_PATTERN.sub("***.***.***", result)
    return result


def _get_cli_version() -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version("sanctum-cli")
    except (ImportError, ModuleNotFoundError):
        return "dev"


@dataclass
class RecoveryEvent:
    """Sanitised correction event matching the PRD §13.4 data model."""

    event_id: str
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

    # PRD §13.4 fields
    failed_command_redacted: str | None = None
    corrected_operation: str | None = None
    accepted: bool | None = None
    match_type: str = "deterministic"
    cli_version: str = "dev"
    schema_digest: str | None = None
    execution_risk: str | None = None

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryEvent:
        timestamp = str(data.get("timestamp", datetime.now(UTC).isoformat()))
        accepted_raw = data.get("accepted")
        accepted: bool | None = None if accepted_raw is None else bool(accepted_raw)
        return cls(
            event_id=str(data.get("event_id", uuid.uuid4().hex)),
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
            failed_command_redacted=data.get("failed_command_redacted"),
            corrected_operation=data.get("corrected_operation"),
            accepted=accepted,
            match_type=str(data.get("match_type", "deterministic")),
            cli_version=str(data.get("cli_version", "dev")),
            schema_digest=data.get("schema_digest"),
            execution_risk=data.get("execution_risk"),
            timestamp=timestamp,
        )


def record_event(event: RecoveryEvent) -> None:
    date_prefix = event.timestamp[:10]
    with _lock:
        _ensure_dir()
        filepath = _EVENTS_DIR / f"{date_prefix}.jsonl"
        with open(filepath, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")


def record_correction_feedback(
    event_id: str,
    accepted: bool,
    *,
    execution_risk: str | None = None,
) -> None:
    """Record whether a user accepted or rejected a suggested correction.

    Writes a lightweight ``FeedbackEntry`` to ``feedback.jsonl`` in the
    events directory so the original event record remains append-only.
    """
    entry = {
        "event_id": event_id,
        "accepted": accepted,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if execution_risk:
        entry["execution_risk"] = execution_risk

    with _lock:
        _ensure_dir()
        filepath = _EVENTS_DIR / "feedback.jsonl"
        with open(filepath, "a") as f:
            f.write(json.dumps(entry) + "\n")


def _load_feedback() -> dict[str, dict[str, Any]]:
    """Load all feedback entries keyed by event_id."""
    feedback: dict[str, dict[str, Any]] = {}
    filepath = _EVENTS_DIR / "feedback.jsonl"
    if not filepath.exists():
        return feedback
    with _lock, open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            eid = entry.get("event_id")
            if eid:
                feedback[eid] = entry
    return feedback


def _merge_feedback(events: list[RecoveryEvent], feedback: dict[str, dict[str, Any]]) -> None:
    """Merge accepted and execution_risk from feedback into events in-place."""
    for ev in events:
        fb = feedback.get(ev.event_id)
        if fb:
            accepted_raw = fb.get("accepted")
            if accepted_raw is not None:
                object.__setattr__(ev, "accepted", bool(accepted_raw))
            if fb.get("execution_risk"):
                object.__setattr__(ev, "execution_risk", str(fb["execution_risk"]))


def _get_feedback_files() -> list[Path]:
    return list(_EVENTS_DIR.glob("*.jsonl"))


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
        if filepath.name == "feedback.jsonl":
            continue
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
                    feedback = _load_feedback()
                    _merge_feedback(results, feedback)
                    return results

    feedback = _load_feedback()
    _merge_feedback(results, feedback)
    return results


def get_pattern_stats(period_days: int = 7) -> dict[str, Any]:
    events = query_events(period_days=period_days)
    total = len(events)
    if total == 0:
        return {
            "total_events": 0,
            "patterns": {},
            "by_domain": {},
            "by_status": {},
            "acceptance": {"accepted": 0, "rejected": 0, "pending_feedback": 0},
        }

    patterns: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    by_status: dict[str, int] = {}
    accepted_count = 0
    rejected_count = 0
    feedback_count = 0
    for ev in events:
        patterns[ev.pattern] = patterns.get(ev.pattern, 0) + 1
        dom = ev.domain or "unknown"
        by_domain[dom] = by_domain.get(dom, 0) + 1
        by_status[ev.status] = by_status.get(ev.status, 0) + 1
        if ev.accepted is True:
            accepted_count += 1
        elif ev.accepted is False:
            rejected_count += 1
        else:
            feedback_count += 1

    pattern_effectiveness = {}
    for pat, count in patterns.items():
        pattern_events = [e for e in events if e.pattern == pat]
        suggestions = [
            e for e in pattern_events if e.status in ("assist_suggestion", "router_interpreted")
        ]
        success_rate = len(suggestions) / count if count > 0 else 0.0
        avg_confidence = sum(e.confidence for e in pattern_events) / count if count > 0 else 0.0
        pattern_events_accepted = [e for e in pattern_events if e.accepted is True]
        with_feedback = [e for e in pattern_events if e.accepted is not None]
        acceptance_rate = (
            len(pattern_events_accepted) / len(with_feedback) if with_feedback else None
        )
        entry: dict[str, Any] = {
            "count": count,
            "success_rate": round(success_rate, 2),
            "avg_confidence": round(avg_confidence, 2),
        }
        if acceptance_rate is not None:
            entry["acceptance_rate"] = round(acceptance_rate, 2)
        pattern_effectiveness[pat] = entry

    return {
        "total_events": total,
        "patterns": pattern_effectiveness,
        "by_domain": by_domain,
        "by_status": by_status,
        "acceptance": {
            "accepted": accepted_count,
            "rejected": rejected_count,
            "pending_feedback": feedback_count,
        },
    }
