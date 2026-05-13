"""Session memory model for conversational context tracking."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SESSION_TTL = 28800  # 8 hours
DEFAULT_SESSIONS_DIR = Path.home() / ".sanctum" / "sessions"


@dataclass
class Message:
    role: str
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            role=str(data.get("role", "user")),
            content=str(data.get("content", "")),
            timestamp=str(data.get("timestamp", "")),
        )


@dataclass
class Session:
    session_id: str
    agent: str | None
    user: str | None
    messages: list[Message] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=content))
        self.updated_at = datetime.now(UTC).isoformat()

    def recent_context(self, n: int = 5) -> list[dict[str, str]]:
        return [
            {"role": m.role, "content": m.content} for m in self.messages[-n:]
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent": self.agent,
            "user": self.user,
            "messages": [m.to_dict() for m in self.messages],
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        return cls(
            session_id=str(data.get("session_id", "")),
            agent=data.get("agent"),
            user=data.get("user"),
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            context=dict(data.get("context", {})),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )


class SessionStore:
    def __init__(self, sessions_dir: str | Path | None = None) -> None:
        self._sessions_dir = Path(sessions_dir or DEFAULT_SESSIONS_DIR)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.json"

    def create(
        self,
        *,
        agent: str | None = None,
        user: str | None = None,
    ) -> Session:
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            agent=agent,
            user=user,
        )
        self._save(session)
        return session

    def get(self, session_id: str) -> Session | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            session = Session.from_dict(data)
            if self._is_expired(session):
                path.unlink(missing_ok=True)
                return None
            return session
        except (json.JSONDecodeError, OSError, KeyError):
            return None

    def save(self, session: Session) -> None:
        session.updated_at = datetime.now(UTC).isoformat()
        self._save(session)

    def _save(self, session: Session) -> None:
        path = self._path(session.session_id)
        path.write_text(json.dumps(session.to_dict(), indent=2))

    def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_active(self) -> list[Session]:
        sessions: list[Session] = []
        for path in sorted(self._sessions_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text())
                session = Session.from_dict(data)
                if not self._is_expired(session):
                    sessions.append(session)
            except (json.JSONDecodeError, OSError, KeyError):
                continue
        return sessions

    def find_by_agent(self, agent: str) -> list[Session]:
        return [s for s in self.list_active() if s.agent == agent]

    def _is_expired(self, session: Session) -> bool:
        try:
            updated = datetime.fromisoformat(session.updated_at)
            age = time.time() - updated.timestamp()
            return age > SESSION_TTL
        except (ValueError, TypeError):
            return True

    def clear_expired(self) -> int:
        count = 0
        for path in list(self._sessions_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                session = Session.from_dict(data)
                if self._is_expired(session):
                    path.unlink()
                    count += 1
            except (json.JSONDecodeError, OSError, KeyError):
                path.unlink(missing_ok=True)
                count += 1
        return count


_global_store = SessionStore()


def get_session_store() -> SessionStore:
    return _global_store
