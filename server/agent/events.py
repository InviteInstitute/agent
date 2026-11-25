"""Learner log records, in VEXcode VR's format, which ZANY writes too.

A record is VEX's log row: its own fields plus `raw_message`, the event as JSON text. Every
source hands its records to parse_record, which makes the row the events table keeps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.environments import Environment


@dataclass(frozen=True)
class Event:
    """One kept event, as the analysis reads it."""

    id: int | None
    session_id: str
    event_ts: datetime
    event_type: str
    playground: str | None
    project: dict | None
    block_event: dict | None
    playground_data: dict | None
    error_message: str | None


def parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _json_object(value: Any) -> dict | None:
    """A JSON object, whether it came as one or as JSON text. Anything else is None."""
    if isinstance(value, str):
        try:
            value = json.loads(value) if value.strip() else None
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def parse_record(record: dict, environment: Environment, source_id: str) -> dict:
    """The events row for one log record. Raises ValueError for a record the analysis
    cannot use (no session, student, time or event type)."""
    payload = _json_object(record.get("raw_message", record.get("content"))) or record
    session_id = payload.get("sessionID")
    student_id = payload.get("studentID")
    event_type = payload.get("eventType")
    event_ts = parse_time(payload.get("timestamp"))
    missing = [
        name
        for name, value in (
            ("sessionID", session_id),
            ("studentID", student_id),
            ("timestamp", event_ts),
            ("eventType", event_type),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")

    class_code = payload.get("classCode") or record.get("classCode") or None
    project = _json_object(payload.get("project", record.get("project")))
    playground_data = _json_object(payload.get("playgroundData"))
    config = (project or {}).get("playgroundConfig")
    candidates = [
        payload.get("playground"),
        (project or {}).get("playground"),
        config.get("playground_id") if isinstance(config, dict) else None,
        (playground_data or {}).get("playground"),
    ]
    playground = next((name for name in map(environment.playground_name, candidates) if name), None)
    return {
        "environment": environment.id,
        "source_id": source_id,
        "student_key": environment.student_key(str(student_id), class_code),
        "student_id": str(student_id),
        "class_code": class_code,
        "session_id": str(session_id),
        "event_ts": event_ts,
        "received_at": parse_time(record.get("received_at") or record.get("recieved_at")),
        "event_type": str(event_type),
        "playground": playground,
        "project": project,
        "block_event": _json_object(payload.get("blockEventData")),
        "playground_data": playground_data,
        "error_message": payload.get("errorMessage") or None,
    }


def parse_records(
    records: list[tuple[dict, str]], environment: Environment
) -> tuple[list[dict], dict[str, int]]:
    """Rows for (record, source_id) pairs, and how many were skipped for each reason."""
    rows: list[dict] = []
    skipped: dict[str, int] = {}
    for record, source_id in records:
        try:
            rows.append(parse_record(record, environment, source_id))
        except ValueError as error:
            skipped[str(error)] = skipped.get(str(error), 0) + 1
    return rows, skipped
