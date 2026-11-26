"""ZANY: the agent frames vr.inviteai.org with the student's class and ID in the link. ZANY sends
those logs to ATLAS-invite, which keeps them as link records in its log store, and the agent
reads them there with a read-only role (ZANY_LOG_DSN).

A researcher can delete a student's link records in ATLAS, as a deletion request needs. ATLAS
then sends `zany_link_forgotten`, and the agent deletes its own copy of that student: the
events, the chat and the settings. An hourly check catches a deletion the agent missed while
it was down.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import psycopg

from agent import config, db
from agent.environments import Environment, Milestone, Playground, fold
from agent.events import parse_records, parse_time

log = logging.getLogger(__name__)

SOURCE = "atlas-link"
PAGE = 1000
OVERLAP = timedelta(seconds=2)
FORGOTTEN = "zany_link_forgotten"
RECONCILE_EVERY_S = 3600
FRAME_URL = "https://vr.inviteai.org/"

BLOCKS = (
    "drive [forward/reverse]",
    "drive [forward/reverse] for [number] [mm/inches]",
    "turn [right/left]",
    "turn [right/left] for [number] degrees",
    "turn to heading [number] degrees",
    "turn to rotation [number] degrees",
    "stop driving",
    "set drive velocity to [number] %",
    "set turn velocity to [number] %",
    "set drive heading to [number] degrees",
    "set drive rotation to [number] degrees",
    "set drive timeout to [number] seconds",
    "drive is done?",
    "drive is moving?",
    "drive heading in degrees",
    "drive rotation in degrees",
    "energize Magnet to [boost/drop]",
    "[LeftBumper/RightBumper] pressed?",
    "when [LeftBumper/RightBumper] [pressed/released]",
    "[FrontDistance] found an object?",
    "[FrontDistance] distance in [mm/inches]",
    "[FrontEye/DownEye] is near object?",
    "[FrontEye/DownEye] detects [red/green/blue/yellow/orange/purple/none]?",
    "[FrontEye/DownEye] brightness in %",
    "position [X/Y] in [mm/inches]",
    "position angle in degrees",
    "when [FrontEye/DownEye] [detects/loses] an object",
    "reset timer",
    "timer in seconds",
    "when timer > [number] seconds",
    "[a] [+/-/*//] [b]",
    "[a] [=/!=/</<=/>/>=] [b]",
    "[a] [<] [b] [<] [c]",
    "pick random [a] to [b]",
    "[condition] [and/or] [condition]",
    "not [condition]",
    "length of [text]",
    "when started",
    "wait [number] seconds",
    "wait until [condition]",
    "repeat [number]",
    "forever",
    "repeat until [condition]",
    "while [condition]",
    "if [condition] then",
    "if [condition] then else",
    "if [condition] then / else if [condition] then / else",
    "break",
    "stop project",
    "comment",
    "move pen [down/up]",
    "set pen to width [extra thin/thin/medium/wide/extra wide]",
    "set pen to color [black/red/green/blue/yellow/purple/orange]",
    "print [text/value]",
    "set cursor to next row",
    "clear all rows",
    "set print precision to [1/0.1/0.01]",
    "set print color [black/red/green/blue]",
    "broadcast [message1]",
    "broadcast [message1] and wait",
    "when I receive [message1]",
    "[myVariable]",
    "set [myVariable] to [number]",
    "change [myVariable] by [number]",
)


def _number(parameters: dict, name: str) -> float:
    value = parameters.get(name)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


# The most any Level 1 run cleared in VEX's logs. ponytail: one target for both levels, a target
# per difficulty_level once Level 2 runs show what a full clear weighs there.
CASTLE_FULL_CLEAR_KG = 8050.0

CASTLE = Playground(
    name="Castle Crasher+",
    task=(
        "The student is working in ZANY, a web copy of VEXcode VR, in the Castle Crasher+ "
        "playground. The castle stands on an island in a lake. The goal is to push the castle's "
        "pieces (walls, turrets, the keep and its towers, and the rocks) into the water without "
        "the robot falling in, which ends the run with 'Fell into the water!'. Each piece counts "
        "its weight in kilograms once it drops into the water, and the run's score is the "
        "weight cleared. The robot can drive, turn, push a plow, and use its magnet to pick up "
        "and drop the hidden tool. It has two bumpers, a front distance sensor, front and down "
        "eye sensors (the Down Eye sees the red border at the island's edge as red) and GPS. "
        "Level 2 adds a row of trees on the eastern border that stop the robot."
    ),
    blocks=BLOCKS,
    log_name="CastleCrasherPlus",
    aliases=("CasteCrasherPlus",),
    milestones=(
        Milestone(
            "push a piece of the castle into the water", lambda p: _number(p, "weight_cleared") > 0
        ),
        Milestone(
            "clear half the castle",
            lambda p: _number(p, "weight_cleared") >= CASTLE_FULL_CLEAR_KG / 2,
        ),
    ),
    progress=lambda p: round(
        min(_number(p, "weight_cleared") / CASTLE_FULL_CLEAR_KG, 1.0) * 100, 2
    ),
)

CORAL_REEF = Playground(
    name="Coral Reef Cleanup",
    task=(
        "The student is working in ZANY, a web copy of VEXcode VR, in the Coral Reef Cleanup "
        "playground. The field is open sand inside a blue channel, with a coral reef round the "
        "edge. The goal is to collect as much trash as possible before the battery runs out, "
        "without touching the coral: touching it stops the robot and ends the run with 'Coral "
        "Damaged!'. Five pieces of trash lie on the sand at the start, and every 5 seconds a new "
        "piece falls in while fewer than 6 are on the sand. The robot collects a piece by "
        "touching it, or from up to 200 mm away with the magnet on. The battery drains faster "
        "at higher drive and turn velocities. The Distance sensor and the Front Eye do not see "
        "the coral, and the Down Eye sees the channel as blue."
    ),
    blocks=BLOCKS,
    log_name="CoralReefRescue",
    milestones=(
        Milestone("collect a piece of trash", lambda p: _number(p, "trash_collected") > 0),
        Milestone(
            "finish a run without touching the coral", lambda p: p.get("coral_damaged") is False
        ),
    ),
    # No fixed amount of trash makes a full score, so there is no percentage to measure.
    progress=None,
)

ART_CANVAS = Playground(
    name="Art Canvas",
    task=(
        "The student is working in ZANY, a web copy of VEXcode VR, in the Art Canvas playground: "
        "a plain white field with a grey grid every 100 mm and walls round the edge. There is no "
        "score. The student draws with the robot's pen, which they move down to draw and up to "
        "stop, and whose width and color they can set. Help them make the drawing they are "
        "going for."
    ),
    blocks=BLOCKS,
    log_name="ArtCanvas",
)


def _store() -> psycopg.Connection:
    dsn = config.text("ZANY_LOG_DSN")
    if not dsn:
        raise RuntimeError("ZANY_LOG_DSN is not set")
    return psycopg.connect(dsn, autocommit=True)


@dataclass(frozen=True)
class Store:
    """Where in ATLAS's log store an environment's students are: the table, the SQL for a
    row's class code and student ID, the agent's cursor, and the notice ATLAS sends with the
    class code and student ID under `notice_keys` when it deletes rows."""

    environment: str
    table: str
    class_code: str
    student_id: str
    source: str
    channel: str
    notice_keys: tuple[str, str]


# Records from a link to vr.inviteai.org, keyed by the IDs typed in it.
LINK = Store(
    "zany", "link_record", "class_code", "student_id", SOURCE, FORGOTTEN, ("class_code", "student")
)
# Records from an ATLAS study, which ZANY logs under the study code and the participant ID.
STUDY = Store(
    "zany-study",
    "log_record",
    "record->>'classCode'",
    "record->>'studentID'",
    "atlas-study",
    "zany_forgotten",
    ("code", "participant"),
)


def _environment(store: Store) -> Environment:
    return ENVIRONMENT if store is LINK else STUDY_ENVIRONMENT


def read_store(store: Store, student_id: str | None = None, class_code: str | None = None) -> int:
    """Read new records: everyone's since the cursor (and move it, a page at a time, since
    pages come oldest first), or one student's (and leave it)."""
    position = db.cursor(store.source)
    if position:
        since = parse_time(position["at"]) - OVERLAP
    elif student_id is None:
        since = datetime.now(UTC) - timedelta(hours=config.student_recency_hours())
    else:
        since = None  # one student's whole history, which the cursor has not reached yet
    conditions, args = [], []
    if since:
        conditions.append("stored_at >= %s")
        args.append(since)
    if student_id is not None:
        conditions.append(f"{store.class_code} = %s AND {store.student_id} = %s")
        args += [class_code or "", student_id]
    elif store is STUDY:
        # Only the study students who opened the agent, whose logs it read when they did. The
        # rest of the study never gave the agent their logs, so it never copies them.
        held = sorted(db.students_held(STUDY.environment))
        if not held:
            return 0
        conditions.append(
            f"({store.class_code}, {store.student_id})"
            " IN (SELECT * FROM unnest(%s::text[], %s::text[]))"
        )
        args += [[code or "" for code, _ in held], [student for _, student in held]]

    environment = _environment(store)
    new = 0
    after: tuple[datetime, int] | None = None
    with _store() as conn:
        while True:
            page = conditions + (["(stored_at, seq) > (%s, %s)"] if after else [])
            page_where = " AND ".join(page) or "true"
            rows = conn.execute(
                f"SELECT seq, stored_at, record FROM {store.table} WHERE {page_where}"
                " ORDER BY stored_at, seq LIMIT %s",
                [*args, *(after or ()), PAGE],
            ).fetchall()
            pairs = [
                (record if isinstance(record, dict) else json.loads(record), str(seq))
                for seq, _, record in rows
            ]
            parsed, skipped = parse_records(pairs, environment)
            if skipped:
                log.info("skipped ZANY %s rows: %s", store.table, skipped)
            new += db.insert_events(parsed)
            if rows:
                after = (rows[-1][1], rows[-1][0])
                if student_id is None:
                    db.save_cursor(store.source, *after)
            if len(rows) < PAGE:
                return new


def sync(student_id: str | None = None, class_code: str | None = None) -> int:
    return read_store(LINK, student_id, class_code)


def sync_study(student_id: str | None = None, class_code: str | None = None) -> int:
    return read_store(STUDY, student_id, class_code)


def forget(class_code: str | None, student_id: str | None) -> int:
    """Delete the agent's copy of the students whose link records ATLAS deleted (by class, by
    student ID or both, as ATLAS's forget_link). Returns how many events went."""
    return db.forget_students(ENVIRONMENT.id, class_code, student_id)


def forget_study(class_code: str | None, student_id: str | None) -> int:
    """Delete everything the agent keeps about a study student whose records ATLAS deleted,
    the chat too, even when it has no events. Returns how many events went."""
    if not class_code or not student_id:
        return 0
    key = STUDY_ENVIRONMENT.student_key(student_id, class_code)
    return db.forget_student_key(STUDY.environment, key)


def _forget(store: Store, class_code: str | None, student_id: str | None) -> int:
    return (forget if store is LINK else forget_study)(class_code, student_id)


def reconcile_store(store: Store) -> int:
    """Forget every student the agent holds whose records are all gone from ATLAS."""
    with _store() as conn:
        kept = {
            (class_code, student_id)
            for class_code, student_id in conn.execute(
                f"SELECT DISTINCT {store.class_code}, {store.student_id} FROM {store.table}"
            )
        }
    return sum(
        _forget(store, class_code, student_id)
        for class_code, student_id in db.students_held(store.environment)
        if (class_code or "", student_id) not in kept
    )


def reconcile() -> int:
    return reconcile_store(LINK)


def watch_store(store: Store, stop: threading.Event) -> None:
    """Listen for ATLAS's deletions until `stop` is set, checking everything once an hour."""
    if not config.text("ZANY_LOG_DSN"):
        log.warning("ZANY_LOG_DSN is not set, so ZANY's logs cannot be read")
        return
    last_check = 0.0
    while not stop.is_set():
        try:
            with _store() as conn:
                conn.execute(f"LISTEN {store.channel}")
                while not stop.is_set():
                    now = datetime.now(UTC).timestamp()
                    if now - last_check >= RECONCILE_EVERY_S:
                        last_check = now
                        if gone := reconcile_store(store):
                            log.info("forgot %d ZANY events deleted from ATLAS", gone)
                    for notice in conn.notifies(timeout=5.0, stop_after=1):
                        who = json.loads(notice.payload or "{}")
                        klass, student = store.notice_keys
                        gone = _forget(store, who.get(klass), who.get(student))
                        log.info("ATLAS deleted %s rows, forgot %d events", store.table, gone)
        except Exception:
            log.warning("lost the ZANY log store, retrying in 30 s", exc_info=True)
            stop.wait(30)


def watch(stop: threading.Event) -> None:
    watch_store(LINK, stop)


def watch_study(stop: threading.Event) -> None:
    watch_store(STUDY, stop)


def frame(student_id: str | None, class_code: str | None) -> str | None:
    """vr.inviteai.org with the student's IDs, so ZANY logs under them. None before sign-in:
    without IDs ZANY keeps no logs, and the agent would have nothing to read."""
    if not student_id or not class_code:
        return None
    return f"{FRAME_URL}?{urlencode({'class': class_code, 'student': student_id})}"


def student_key(student_id: str, class_code: str | None) -> str:
    return f"{fold(class_code)}:{fold(student_id)}"


ENVIRONMENT = Environment(
    id="zany",
    name="ZANY",
    tool="ZANY, a block-based programming tool for middle school students built like VEXcode VR",
    needs_class_code=True,
    playgrounds=(CASTLE, CORAL_REEF, ART_CANVAS),
    frame=frame,
    student_key=student_key,
    sync=sync,
    watch=watch,
)

# ZANY inside an ATLAS study, for a student a researcher gave the agent. ATLAS's ticket says
# who the student is and which session to frame (agent/study.py), so nobody signs in here.
STUDY_ENVIRONMENT = Environment(
    id="zany-study",
    name="ZANY",
    tool=ENVIRONMENT.tool,
    needs_class_code=True,
    playgrounds=ENVIRONMENT.playgrounds,
    frame=lambda student_id, class_code: None,
    student_key=student_key,
    sync=sync_study,
    watch=watch_study,
    study=True,
)
