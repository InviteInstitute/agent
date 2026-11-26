"""Proactive check-ins: the agent reaches out when a behavior trigger fires, without being asked.

A background thread (the daemon) reads every environment's new logs, then looks at each
student with recent events. The learner-model engine finds the momentary triggers in how much
each run changed (wheel-spinning, resilience, explorer, iterative), and the inactive trigger
fires when a session has gone quiet. Each trigger is kept once. A new one gets a check-in from
the same feedback pipeline a question uses, grounded in the session, with the trigger given to
the model as a neutral fact and never by its label.

The daemon runs when CHECKINS_ENABLED is on. It messages real students, so turning it on is a
deliberate act. TRIGGER_DISABLED names trigger types it still detects and keeps but does not
act on (e.g. inactive,explorer).
"""

from __future__ import annotations

import logging
import random
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from learner_models import (
    RunDistanceStream,
    detect_inactive_trigger,
    detect_run_triggers_by_playground,
)

from agent import config, db, environments, llm
from agent.environments import Environment
from agent.events import Event
from agent.feedback import generate
from agent.pedagogy import Feedback
from agent.situation import current_stretch

log = logging.getLogger(__name__)

FEEDBACK_FOR_TRIGGER = {
    "wheel_spin": {Feedback.REASSURE, Feedback.DIAGNOSE},
    "resilience": {Feedback.EVIDENCE_BASED_PRAISE},
    "iterative": {Feedback.EVIDENCE_BASED_PRAISE},
    "explorer": {Feedback.DIAGNOSE},
    "inactive": {Feedback.REASSURE, Feedback.QUESTION},
}

# What the model is told happened. Never the trigger's name, which once leaked into replies.
NEUTRAL_FACT = {
    "wheel_spin": "The student keeps running the same program without changing any blocks.",
    "resilience": "The student just changed their program after several unchanged runs.",
    "explorer": "The student made a large change to their program in a single step.",
    "iterative": "The student has been making steady, small changes to their program.",
    "inactive": "The student has not done anything for a while.",
}

# Check-ins spend tokens too. They count toward the site's daily ceiling under this key.
BUDGET_KEY = "check-ins"


def enabled() -> bool:
    return config.flag("CHECKINS_ENABLED")


def disabled_triggers() -> set[str]:
    return {name.strip() for name in config.text("TRIGGER_DISABLED").split(",") if name.strip()}


# --- run distances, kept per session so a tick only reads what is new ---


@dataclass
class _Runs:
    stream: RunDistanceStream = field(default_factory=RunDistanceStream)
    fed: int = 0
    last_id: int | None = None


_RUNS_KEPT = 512
_runs: OrderedDict[tuple[str, str, str], _Runs] = OrderedDict()
_runs_lock = threading.Lock()


def _engine_event(event: Event, environment: Environment) -> dict:
    playground = environment.playground(event.playground)
    return {
        "event_type": event.event_type,
        "content": {
            "project": event.project or {},
            # The engine keys its per-playground thresholds by the logged name.
            "playground": (playground.log_name or playground.name)
            if playground
            else event.playground,
        },
        "ts": event.event_ts.timestamp(),
    }


def run_distances(environment: Environment, student_key: str, session_id: str, events: list[Event]):
    """How much each run of the session changed from the one before. Only events since the
    last call are fed in, unless the list no longer extends what was fed (a late event landed
    in the middle), and then the session is read again from the start."""
    key = (environment.id, student_key, session_id)
    with _runs_lock:
        runs = _runs.get(key)
        extends = (
            runs
            and len(events) >= runs.fed
            and (runs.fed == 0 or events[runs.fed - 1].id == runs.last_id)
        )
        if not extends:
            runs = _Runs()
        for event in events[runs.fed :]:
            runs.stream.push(_engine_event(event, environment))
        runs.fed = len(events)
        runs.last_id = events[-1].id if events else None
        _runs[key] = runs
        _runs.move_to_end(key)
        while len(_runs) > _RUNS_KEPT:
            _runs.popitem(last=False)
        return list(runs.stream.runs)


def forget_runs() -> None:
    """Drop every session's runs (for tests)."""
    with _runs_lock:
        _runs.clear()


# --- one student ---


def new_triggers(
    environment: Environment,
    student_key: str,
    session_id: str,
    events: list[Event],
    now: datetime | None = None,
) -> list[dict]:
    """Detect the session's triggers and keep the ones not kept before. Returns the new ones."""
    now = now or datetime.now(UTC)
    fires = list(
        detect_run_triggers_by_playground(
            run_distances(environment, student_key, session_id, events)
        )
    )
    last_event = events[-1].event_ts if events else None
    idle = detect_inactive_trigger(
        last_event,
        now,
        db.last_inactive_fire(environment.id, student_key, session_id),
    )
    if idle:
        fires.append(idle)
    else:
        db.resolve_inactive(environment.id, student_key, session_id)
    new = []
    for trigger_type, run_index, detail in fires:
        trigger_id = db.insert_trigger(
            environment.id, student_key, session_id, trigger_type, run_index, detail, now
        )
        if trigger_id is not None:
            new.append({"id": trigger_id, "type": trigger_type, "detail": detail})
    return new


def check_in(
    environment: Environment, student_key: str, session_id: str, events: list[Event], trigger: dict
) -> int | None:
    """Send the check-in for a new trigger. Returns the message id, or None when the agent
    does not act on it (turned off, or a playground it does not know)."""
    if trigger["type"] in disabled_triggers() or trigger["type"] not in FEEDBACK_FOR_TRIGGER:
        return None
    stretch = current_stretch(events)
    playground = environment.playground(stretch[-1].playground) if stretch else None
    if playground is None:
        return None
    saved = db.agent_settings(environment.id, student_key)
    settings = llm.Settings(**saved) if saved else llm.PRODUCTION
    spent: list[int] = []
    try:
        reply = generate(
            environment,
            student_key,
            session_id,
            events,
            playground,
            FEEDBACK_FOR_TRIGGER[trigger["type"]],
            chat="student",
            behavior_fact=NEUTRAL_FACT[trigger["type"]],
            settings=settings,
            spent=spent,
        )
    finally:
        if sum(spent):
            db.record_llm_usage(
                budget_key=BUDGET_KEY,
                environment=environment.id,
                student_key=student_key,
                model=settings.model or config.navigator_model(),
                origin="proactive",
                tokens=sum(spent),
            )
    message_id = db.insert_message(
        environment=environment.id,
        student_key=student_key,
        session_id=session_id,
        chat="student",
        role="agent",
        origin="proactive",
        body=reply.body,
        response_id=uuid4(),
        feedback_classes=reply.feedback,
        trigger_type=trigger["type"],
        context={**reply.context, "trigger": trigger["detail"]},
    )
    db.link_trigger_message(trigger["id"], message_id)
    log.info(
        "checked in with %s/%s (%s): %s", environment.id, student_key, trigger["type"], reply.body
    )
    return message_id


def tick_student(
    environment: Environment, student_key: str, now: datetime | None = None
) -> list[int]:
    """One pass for one student's newest session. Returns the check-ins sent."""
    session_id = db.latest_session(environment.id, student_key)
    if session_id is None:
        return []
    events = db.session_events(environment.id, student_key, session_id)
    sent = []
    for trigger in new_triggers(environment, student_key, session_id, events, now):
        message_id = check_in(environment, student_key, session_id, events, trigger)
        if message_id:
            sent.append(message_id)
    return sent


def tick() -> int:
    """One pass over every environment: read the new logs, then every recent student. Returns
    how many check-ins went out."""
    sent = 0
    for environment in environments.enabled():
        try:
            environment.sync()
        except Exception:
            log.warning("could not read %s's logs this tick", environment.id, exc_info=True)
        for student_key in db.recent_students(environment.id, config.student_recency_hours()):
            try:
                sent += len(tick_student(environment, student_key))
            except Exception:
                log.warning(
                    "check-in pass failed for %s/%s", environment.id, student_key, exc_info=True
                )
    return sent


def run(stop: threading.Event) -> None:
    """The daemon: a tick every CHECKIN_INTERVAL_S seconds while check-ins go out, slowing
    toward CHECKIN_IDLE_MAX_S while nothing happens, and backing off after failures."""
    base = config.number("CHECKIN_INTERVAL_S", 5.0)
    ceiling = config.number("CHECKIN_IDLE_MAX_S", 30.0)
    idle = failures = 0
    log.info("check-in daemon started (every %ss, up to %ss when quiet)", base, ceiling)
    while not stop.is_set():
        try:
            busy = tick() > 0
            failures = 0
        except Exception:
            failures += 1
            log.warning("check-in tick failed (%d in a row)", failures, exc_info=True)
            stop.wait(min(30.0, 0.5 * 2 ** min(failures, 6)) + random.uniform(0, 0.5))
            continue
        idle = 0 if busy else idle + 1
        stop.wait(base if busy else min(ceiling, base * 2 ** min(idle, 6)))
