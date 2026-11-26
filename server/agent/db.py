"""Postgres: one connection pool, the migrations, and every query the agent makes."""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from agent import config
from agent.events import Event

log = logging.getLogger(__name__)

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def pool() -> ConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ConnectionPool(config.database_url(), min_size=1, max_size=10, open=True)
        return _pool


def close() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def migrate() -> list[str]:
    """Apply the migrations not applied yet, in order, each in its own transaction.
    Returns the names it applied."""
    applied = []
    with pool().connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations"
            " (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
        conn.commit()
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            log.info("applied migration %s", path.name)
            applied.append(path.name)
    return applied


# --- learner logs ---


def insert_events(rows: list[dict[str, Any]]) -> int:
    """Keep parsed records (events.parse_record's rows). A record already kept is skipped.
    Returns how many were new."""
    if not rows:
        return 0
    json_fields = ("project", "block_event", "playground_data")
    with pool().connection() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO events (environment, source_id, student_key, student_id, class_code,
                session_id, event_ts, received_at, event_type, playground, project, block_event,
                playground_data, error_message)
            VALUES (%(environment)s, %(source_id)s, %(student_key)s, %(student_id)s,
                %(class_code)s, %(session_id)s, %(event_ts)s, %(received_at)s, %(event_type)s,
                %(playground)s, %(project)s, %(block_event)s, %(playground_data)s,
                %(error_message)s)
            ON CONFLICT (environment, source_id) DO NOTHING
            """,
            [
                {**row, **{f: Jsonb(row[f]) if row[f] is not None else None for f in json_fields}}
                for row in rows
            ],
        )
        return cur.rowcount  # summed over the batch, skipped records count 0


def session_events(environment: str, student_key: str, session_id: str) -> list[Event]:
    """A session's events on a playground, oldest first."""
    with pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, session_id, event_ts, event_type, playground, project, block_event,
                playground_data, error_message
            FROM events
            WHERE environment = %s AND student_key = %s AND session_id = %s
              AND playground IS NOT NULL
            ORDER BY event_ts, id
            """,
            (environment, student_key, session_id),
        )
        return [Event(**row) for row in cur.fetchall()]


def latest_session(environment: str, student_key: str) -> str | None:
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT session_id FROM events WHERE environment = %s AND student_key = %s"
            " ORDER BY event_ts DESC, id DESC LIMIT 1",
            (environment, student_key),
        ).fetchone()
        return row[0] if row else None


def cursor(source: str) -> dict | None:
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT position FROM ingest_cursors WHERE source = %s", (source,)
        ).fetchone()
        return row[0] if row else None


def save_cursor(source: str, at: datetime, seq: int) -> None:
    """Move a source's cursor forward to (at, seq). Never backward: two syncs can finish in
    either order."""
    with pool().connection() as conn:
        conn.execute(
            """
            INSERT INTO ingest_cursors (source, position) VALUES (%(source)s, %(position)s)
            ON CONFLICT (source) DO UPDATE SET position = EXCLUDED.position, updated_at = now()
            WHERE ((ingest_cursors.position->>'at')::timestamptz,
                   (ingest_cursors.position->>'seq')::bigint)
                < ((EXCLUDED.position->>'at')::timestamptz, (EXCLUDED.position->>'seq')::bigint)
            """,
            {"source": source, "position": Jsonb({"at": at.isoformat(), "seq": seq})},
        )


def students_held(environment: str) -> set[tuple[str | None, str]]:
    """Every (class code, student ID) the agent has events for, as logged."""
    with pool().connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT class_code, student_id FROM events WHERE environment = %s",
            (environment,),
        ).fetchall()
        return {(class_code, student_id) for class_code, student_id in rows}


# Tables keyed by (environment, student_key) that go when a student is forgotten.
FORGOTTEN_WITH_STUDENT = ("triggers", "messages", "agent_settings")


def forget_students(environment: str, class_code: str | None, student_id: str | None) -> int:
    """Delete the events logged under a class code, a student ID or both (exactly as logged),
    then everything else the agent keeps about a student who has no events left: the chat, its
    ratings and the research settings. Token spending stays counted, without the student.
    Returns how many events were deleted."""
    if class_code is None and student_id is None:
        raise ValueError("name a class code or a student ID")
    where, args = ["environment = %s"], [environment]
    for column, value in (("class_code", class_code), ("student_id", student_id)):
        if value is not None:
            where.append(f"{column} = %s")
            args.append(value)
    condition = " AND ".join(where)
    with pool().connection() as conn, conn.transaction():
        keys = [
            row[0]
            for row in conn.execute(
                f"SELECT DISTINCT student_key FROM events WHERE {condition}", args
            )
        ]
        deleted = conn.execute(f"DELETE FROM events WHERE {condition}", args).rowcount
        gone = [
            key
            for key in keys
            if not conn.execute(
                "SELECT 1 FROM events WHERE environment = %s AND student_key = %s LIMIT 1",
                (environment, key),
            ).fetchone()
        ]
        if gone:
            for table in FORGOTTEN_WITH_STUDENT:
                conn.execute(
                    f"DELETE FROM {table} WHERE environment = %s AND student_key = ANY(%s)",
                    (environment, gone),
                )
            conn.execute(
                "UPDATE llm_usage SET student_key = NULL"
                " WHERE environment = %s AND student_key = ANY(%s)",
                (environment, gone),
            )
        return deleted


# --- chat ---


def insert_message(
    *,
    environment: str,
    student_key: str,
    session_id: str,
    chat: str,
    role: str,
    body: str,
    origin: str = "reactive",
    response_id: UUID | None = None,
    question_type: str | None = None,
    feedback_classes: list[str] | None = None,
    trigger_type: str | None = None,
    context: dict | None = None,
) -> int:
    with pool().connection() as conn:
        return conn.execute(
            """
            INSERT INTO messages (environment, student_key, session_id, chat, role, origin, body,
                response_id, question_type, feedback_classes, trigger_type, context)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                environment,
                student_key,
                session_id,
                chat,
                role,
                origin,
                body,
                response_id,
                question_type,
                feedback_classes,
                trigger_type,
                Jsonb(context) if context is not None else None,
            ),
        ).fetchone()[0]


def chat_messages(
    environment: str, student_key: str, session_id: str, chat: str, limit: int
) -> list[dict]:
    """The newest `limit` turns of one chat in a session, oldest first. Check-ins belong to
    both chats."""
    with pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT * FROM (
                SELECT m.id, m.role, m.origin, m.body, m.response_id, m.trigger_type,
                    m.created_at, r.thumb
                FROM messages m
                LEFT JOIN LATERAL (
                    SELECT thumb FROM ratings WHERE message_id = m.id ORDER BY id DESC LIMIT 1
                ) r ON true
                WHERE m.environment = %s AND m.student_key = %s AND m.session_id = %s
                  AND (m.chat = %s OR m.origin = 'proactive')
                ORDER BY m.id DESC LIMIT %s
            ) newest ORDER BY id
            """,
            (environment, student_key, session_id, chat, limit),
        )
        return cur.fetchall()


def message_for_response(environment: str, student_key: str, response_id: UUID) -> int | None:
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT id FROM messages"
            " WHERE environment = %s AND student_key = %s AND response_id = %s AND role = 'agent'",
            (environment, student_key, response_id),
        ).fetchone()
        return row[0] if row else None


def insert_rating(message_id: int, thumb: str, comment: str | None) -> None:
    with pool().connection() as conn:
        conn.execute(
            "INSERT INTO ratings (message_id, thumb, comment) VALUES (%s, %s, %s)",
            (message_id, thumb, comment),
        )


def latest_proactive_id(environment: str, student_key: str) -> int:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM messages"
            " WHERE environment = %s AND student_key = %s AND origin = 'proactive'",
            (environment, student_key),
        ).fetchone()[0]


def proactive_after(environment: str, student_key: str, after_id: int) -> list[dict]:
    """A student's check-ins newer than `after_id`, oldest first."""
    with pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, body, response_id, trigger_type, created_at FROM messages
            WHERE environment = %s AND student_key = %s AND origin = 'proactive' AND id > %s
            ORDER BY id
            """,
            (environment, student_key, after_id),
        )
        return cur.fetchall()


# --- triggers ---


def recent_students(environment: str, hours: float) -> list[str]:
    """Every student with an event in the last `hours`."""
    with pool().connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT student_key FROM events"
            " WHERE environment = %s AND event_ts > now() - make_interval(secs => %s)",
            (environment, hours * 3600),
        ).fetchall()
        return [row[0] for row in rows]


def insert_trigger(
    environment: str,
    student_key: str,
    session_id: str,
    trigger_type: str,
    run_index: int,
    detail: dict | None,
    fired_at: datetime,
) -> int | None:
    """Keep a detected trigger, fired at the time its detection used. Returns its id, or None
    when it was already kept."""
    with pool().connection() as conn:
        row = conn.execute(
            """
            INSERT INTO triggers (environment, student_key, session_id, trigger_type, run_index,
                detail, fired_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (environment, student_key, session_id, trigger_type, run_index) DO NOTHING
            RETURNING id
            """,
            (
                environment,
                student_key,
                session_id,
                trigger_type,
                run_index,
                Jsonb(detail),
                fired_at,
            ),
        ).fetchone()
        return row[0] if row else None


def last_inactive_fire(environment: str, student_key: str, session_id: str):
    """(run_index, fired_at) of the session's newest inactive trigger, or None."""
    with pool().connection() as conn:
        return conn.execute(
            "SELECT run_index, fired_at FROM triggers WHERE environment = %s AND student_key = %s"
            " AND session_id = %s AND trigger_type = 'inactive' ORDER BY fired_at DESC LIMIT 1",
            (environment, student_key, session_id),
        ).fetchone()


def resolve_inactive(environment: str, student_key: str, session_id: str) -> None:
    """Close a session's open inactive triggers: the student is active again."""
    with pool().connection() as conn:
        conn.execute(
            "UPDATE triggers SET resolved_at = now() WHERE environment = %s AND student_key = %s"
            " AND session_id = %s AND trigger_type = 'inactive' AND resolved_at IS NULL",
            (environment, student_key, session_id),
        )


def link_trigger_message(trigger_id: int, message_id: int) -> None:
    with pool().connection() as conn:
        conn.execute("UPDATE triggers SET message_id = %s WHERE id = %s", (message_id, trigger_id))


# --- research settings ---


def agent_settings(environment: str, student_key: str) -> dict | None:
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT settings FROM agent_settings WHERE environment = %s AND student_key = %s",
            (environment, student_key),
        ).fetchone()
        return row[0] if row else None


def save_agent_settings(environment: str, student_key: str, settings: dict | None) -> None:
    """Remember a student's research settings, or forget them (None means production)."""
    with pool().connection() as conn:
        if settings is None:
            conn.execute(
                "DELETE FROM agent_settings WHERE environment = %s AND student_key = %s",
                (environment, student_key),
            )
            return
        conn.execute(
            """
            INSERT INTO agent_settings (environment, student_key, settings) VALUES (%s, %s, %s)
            ON CONFLICT (environment, student_key)
            DO UPDATE SET settings = EXCLUDED.settings, updated_at = now()
            """,
            (environment, student_key, Jsonb(settings)),
        )


# --- LLM spending ---


def record_llm_usage(
    *,
    budget_key: str,
    environment: str | None,
    student_key: str | None,
    model: str,
    origin: str,
    tokens: int,
) -> None:
    with pool().connection() as conn:
        conn.execute(
            "INSERT INTO llm_usage (budget_key, environment, student_key, model, origin, tokens)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (budget_key, environment, student_key, model, origin, tokens),
        )


def tokens_for_budget_key(budget_key: str) -> int:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT COALESCE(SUM(tokens), 0) FROM llm_usage WHERE budget_key = %s", (budget_key,)
        ).fetchone()[0]


def tokens_last_day() -> int:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT COALESCE(SUM(tokens), 0) FROM llm_usage"
            " WHERE created_at > now() - INTERVAL '1 day'"
        ).fetchone()[0]
