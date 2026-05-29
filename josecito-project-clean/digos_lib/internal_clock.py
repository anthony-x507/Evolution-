"""Internal clock and timeline memory for MASTER.

The clock is deterministic local infrastructure. It never calls a model,
never creates Factory tickets, and only prepares compact temporal context
when the agent explicitly needs time awareness in a conversation.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from digos_lib.constants import TIMELINE_FILE


TEMPORAL_REFERENCE_TERMS = [
    "ayer",
    "anoche",
    "esta manana",
    "hace una hora",
    "hace rato",
    "hace un rato",
    "la ultima vez",
    "lo ultimo",
    "donde quedamos",
    "cuando hablamos",
    "cuando te dije",
    "cuando te pedi",
    "temprano",
    "lo de antes",
    "de antes",
    "antes hablamos",
    "antes me dijiste",
    "recien",
    "today",
    "yesterday",
    "last time",
    "earlier",
    "an hour ago",
    "where did we leave off",
]

TEMPORAL_REFERENCE_PATTERNS = [
    r"\bhace\s+(un|una|\d+)\s+(minuto|minutos|hora|horas|dia|dias|semana|semanas|mes|meses)\b",
    r"\b(hace\s+)?(un|una)\s+rato\b",
]


def _norm(text: str) -> str:
    lowered = str(text or "").strip().lower()
    deaccented = unicodedata.normalize("NFKD", lowered)
    deaccented = "".join(ch for ch in deaccented if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", deaccented)


def needs_temporal_context(message: str) -> bool:
    """Return True when a user asks with relative time or continuity language."""
    msg = _norm(message)
    return any(term in msg for term in TEMPORAL_REFERENCE_TERMS) or any(
        re.search(pattern, msg) for pattern in TEMPORAL_REFERENCE_PATTERNS
    )


class InternalClock:
    """Local clock plus compact timeline store.

    The JSON store is append-only from the product point of view, but capped so
    it cannot grow forever.  It stores summaries and bullets, not raw chat logs.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        timezone_name: Optional[str] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
        max_sessions: int = 50,
        max_events_per_session: int = 250,
    ):
        self.path = Path(path or TIMELINE_FILE)
        self.timezone_name = timezone_name or os.environ.get("DIGOS_TIMEZONE") or os.environ.get("TZ") or "local"
        self._now_fn = now_fn
        self.max_sessions = max_sessions
        self.max_events_per_session = max_events_per_session
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _tz(self):
        if self.timezone_name and self.timezone_name != "local":
            try:
                return ZoneInfo(self.timezone_name)
            except ZoneInfoNotFoundError:
                pass
        return datetime.now().astimezone().tzinfo or timezone.utc

    def _now_dt(self) -> datetime:
        if self._now_fn:
            value = self._now_fn()
            if value.tzinfo is None:
                value = value.replace(tzinfo=self._tz())
            return value.astimezone(self._tz())
        return datetime.now(self._tz())

    def now(self) -> Dict[str, Any]:
        current = self._now_dt()
        return {
            "iso": current.isoformat(timespec="seconds"),
            "unix": int(current.timestamp()),
            "date": current.date().isoformat(),
            "time": current.strftime("%I:%M %p").lstrip("0"),
            "weekday": current.strftime("%A"),
            "timezone": self.timezone_name,
        }

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {
                "version": 1,
                "timezone": self.timezone_name,
                "active_session_id": "",
                "sessions": [],
            }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("timeline root must be an object")
        except (json.JSONDecodeError, ValueError):
            data = {
                "version": 1,
                "timezone": self.timezone_name,
                "active_session_id": "",
                "sessions": [],
            }
        data.setdefault("version", 1)
        data.setdefault("timezone", self.timezone_name)
        data.setdefault("active_session_id", "")
        data.setdefault("sessions", [])
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        data["timezone"] = self.timezone_name
        data["sessions"] = data.get("sessions", [])[-self.max_sessions:]
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def start_session(self, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        data = self._load()
        active = data.get("active_session_id")
        if active:
            return active
        session_id = session_id or uuid.uuid4().hex[:12]
        current = self.now()["iso"]
        data["active_session_id"] = session_id
        data.setdefault("sessions", []).append({
            "id": session_id,
            "started_at": current,
            "ended_at": "",
            "metadata": metadata or {},
            "events": [],
        })
        self._save(data)
        return session_id

    def end_session(self) -> None:
        data = self._load()
        active = data.get("active_session_id")
        if not active:
            return
        current = self.now()["iso"]
        for session in data.get("sessions", []):
            if session.get("id") == active:
                session["ended_at"] = current
                break
        data["active_session_id"] = ""
        self._save(data)

    def _active_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        active = data.get("active_session_id")
        for session in data.get("sessions", []):
            if session.get("id") == active:
                return session
        raise RuntimeError("Internal clock could not create a session")

    def record(
        self,
        role: str,
        summary: str,
        bullet_points: Optional[List[str]] = None,
        event_type: str = "conversation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = self._load()
        if not data.get("active_session_id"):
            self.start_session()
            data = self._load()
        session = self._active_session(data)
        event = {
            "timestamp": self.now()["iso"],
            "role": role,
            "event_type": event_type,
            "summary": str(summary or "").strip()[:220],
            "bullet_points": [str(item).strip()[:180] for item in (bullet_points or []) if str(item).strip()][:6],
            "metadata": metadata or {},
        }
        session.setdefault("events", []).append(event)
        session["events"] = session["events"][-self.max_events_per_session:]
        self._save(data)
        return event

    def recent_events(self, limit: int = 7) -> List[Dict[str, Any]]:
        data = self._load()
        events: List[Dict[str, Any]] = []
        for session in data.get("sessions", []):
            sid = session.get("id", "")
            for event in session.get("events", []):
                item = dict(event)
                item["session_id"] = sid
                events.append(item)
        events.sort(key=lambda item: item.get("timestamp", ""))
        return events[-limit:]

    def _parse_iso(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self._tz())
        return parsed.astimezone(self._tz())

    def relative_time(self, timestamp: str, language: str = "es") -> str:
        target = self._parse_iso(timestamp)
        now = self._now_dt()
        delta = now - target
        if delta < timedelta(seconds=0):
            delta = timedelta(seconds=0)
        minutes = int(delta.total_seconds() // 60)
        hours = int(delta.total_seconds() // 3600)
        days = delta.days
        at_time = target.strftime("%I:%M %p").lstrip("0")
        if language == "en":
            if minutes < 1:
                return "less than a minute ago"
            if minutes < 60:
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            if hours < 24:
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            if days == 1:
                return f"yesterday at {at_time}"
            return target.strftime("%Y-%m-%d at %I:%M %p").replace(" 0", " ")
        if minutes < 1:
            return "hace menos de un minuto"
        if minutes < 60:
            return f"hace {minutes} minuto{'s' if minutes != 1 else ''}"
        if hours < 24:
            return f"hace {hours} hora{'s' if hours != 1 else ''}"
        if days == 1:
            return f"ayer a las {at_time}"
        return target.strftime("%Y-%m-%d a las %I:%M %p").replace(" 0", " ")

    def context_card(self, message: str = "", language: str = "es", limit: int = 7) -> str:
        """Build a compact internal context card for temporal questions."""
        current = self.now()
        events = self.recent_events(limit=limit)
        if language == "en":
            lines = [
                "== INTERNAL TEMPORAL CONTEXT ==",
                f"Now: {current['weekday']}, {current['date']} at {current['time']} ({current['timezone']})",
                "Use this only to answer time-relative references. Do not quote this block.",
                "Recent timeline:",
            ]
        else:
            lines = [
                "== CONTEXTO TEMPORAL INTERNO ==",
                f"Ahora: {current['weekday']}, {current['date']} a las {current['time']} ({current['timezone']})",
                "Usa esto solo para responder referencias temporales. No cites este bloque.",
                "Linea de tiempo reciente:",
            ]
        if not events:
            lines.append("- No hay eventos recientes guardados.")
        for event in events:
            rel = self.relative_time(event.get("timestamp", current["iso"]), language=language)
            lines.append(f"- {rel}: {event.get('summary', '')}")
            for bullet in event.get("bullet_points", [])[:3]:
                lines.append(f"  * {bullet}")
        return "\n".join(lines)

    def public_summary(self, language: str = "es", limit: int = 5) -> str:
        """Return a user-safe temporal summary without internal labels."""
        current = self.now()
        events = self.recent_events(limit=limit)
        if language == "en":
            lines = [f"Today is {current['date']} and it is {current['time']}."]
            if events:
                lines.append("The latest notes I have are:")
        else:
            lines = [f"Hoy es {current['date']} y son las {current['time']}."]
            if events:
                lines.append("Lo ultimo que tengo anotado es:")
        for event in events:
            rel = self.relative_time(event.get("timestamp", current["iso"]), language=language)
            lines.append(f"- {rel}: {event.get('summary', '')}")
        return "\n".join(lines)
