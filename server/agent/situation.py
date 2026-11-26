"""What a student is doing, measured from their session's events, never guessed.

The snapshot sorts the current playground stretch of a session into a work pattern (cognition)
and a persistence category, which pick the feedback classes. The situation is the same
measurements in plain words for the prompt, so the model grounds its reply on facts.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise
from statistics import mean

from agent.environments import Playground
from agent.events import Event

# Events that open a new stretch on a playground.
SWITCH_EVENTS = {"PlaygroundChange", "playgroundOpen", "menuSelect"}
EDIT_EVENTS = {"blockCreated", "blockChanged", "blockDeleted", "blockMoved"}
# Actions a minute below LOW and up to MEDIUM.
LOW_ACTIONS_PER_MINUTE = 1.5
MEDIUM_ACTIONS_PER_MINUTE = 3.5
# A progress change smaller than this, in points, is noise.
PROGRESS_STEP = 5.0


class Level(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Direction(StrEnum):
    INCREASING = "INCREASING"
    STATIC = "STATIC"
    DECREASING = "DECREASING"


class Cognition(StrEnum):
    LONG_TERM_STALLED_PROGRESS = "LONG_TERM_STALLED_PROGRESS"
    DEVELOPMENT_INCREASES_PROGRESS = "DEVELOPMENT_INCREASES_PROGRESS"
    DEVELOPMENT_STATIC_PROGRESS = "DEVELOPMENT_STATIC_PROGRESS"
    DEVELOPMENT_DECREASES_PROGRESS = "DEVELOPMENT_DECREASES_PROGRESS"
    TRIAL_AND_ERROR = "TRIAL_AND_ERROR"
    CODE_ABANDONMENT = "CODE_ABANDONMENT"
    STEP_BY_STEP_ELIMINATION = "STEP_BY_STEP_ELIMINATION"
    SNAP_N_TEST = "SNAP_N_TEST"
    UNCLASSIFIED = "UNCLASSIFIED"


class Persistence(StrEnum):
    EXPECTED_COMPLETION = "EXPECTED_COMPLETION"
    HIGH_PERSISTER = "HIGH_PERSISTER"
    EARLY_QUITTER = "EARLY_QUITTER"
    IN_PROGRESS = "IN_PROGRESS"


@dataclass(frozen=True)
class Snapshot:
    playground: str
    time_on_task_s: float
    action_level: Level
    # None on a playground with nothing to score.
    progress_pct: float | None
    direction: Direction
    cognition: Cognition
    persistence: Persistence
    runs: int
    # Runs that ended and then sat watched for a while (the episode engine's POST_RUN_PAUSE).
    post_run_pauses: int


def current_stretch(events: list[Event]) -> list[Event]:
    """The newest stretch of events on one playground: since the student last switched to it."""
    events = [event for event in events if event.playground]
    if not events:
        return []
    playground = events[-1].playground
    start = 0
    for index in range(len(events) - 1, -1, -1):
        if events[index].playground != playground:
            start = index + 1
            break
        if events[index].event_type in SWITCH_EVENTS:
            start = index
    return [event for event in events[start:] if event.playground == playground]


def has_active_run(events: list[Event]) -> bool:
    """Whether the newest runProject has not ended yet."""
    for event in reversed(events):
        if event.event_type == "projectEnd":
            return False
        if event.event_type == "runProject":
            return True
    return False


def parameters(event: Event) -> dict:
    data = event.playground_data or {}
    value = data.get("parameters")
    return value if isinstance(value, dict) else {}


def latest_parameters(events: list[Event]) -> dict:
    return next((p for p in map(parameters, reversed(events)) if p), {})


def _direction(series: list[tuple[datetime, float]], start: datetime, end: datetime) -> Direction:
    if not series:
        return Direction.STATIC
    midpoint = start + (end - start) / 2
    first = [value for at, value in series if at <= midpoint] or [series[0][1]]
    second = [value for at, value in series if at > midpoint] or [series[-1][1]]
    delta = mean(second) - mean(first)
    if delta >= PROGRESS_STEP:
        return Direction.INCREASING
    if delta <= -PROGRESS_STEP:
        return Direction.DECREASING
    return Direction.STATIC


def _persistence(time_s: float, level: Level, progress: float, direction: Direction) -> Persistence:
    if progress >= 67.0 or (direction == Direction.INCREASING and progress >= 50.0):
        return Persistence.EXPECTED_COMPLETION
    if time_s >= 600.0 and level == Level.HIGH and progress < 33.0:
        return Persistence.HIGH_PERSISTER
    if time_s <= 120.0 and progress < 10.0 and level == Level.LOW:
        return Persistence.EARLY_QUITTER
    return Persistence.IN_PROGRESS


def _cognition(
    events: list[Event],
    series: list[tuple[datetime, float]],
    time_s: float,
    level: Level,
    progress: float,
    direction: Direction,
    post_run_pauses: int,
    scored: bool,
) -> Cognition:
    # The progress rules only mean something on a playground with a score.
    if scored and time_s >= 600.0 and progress < 10.0 and level != Level.HIGH:
        return Cognition.LONG_TERM_STALLED_PROGRESS
    if scored and direction == Direction.INCREASING and progress >= 10.0:
        return Cognition.DEVELOPMENT_INCREASES_PROGRESS
    if scored and direction == Direction.STATIC and time_s >= 300.0:
        return Cognition.DEVELOPMENT_STATIC_PROGRESS
    if scored and direction == Direction.DECREASING and progress >= 10.0:
        return Cognition.DEVELOPMENT_DECREASES_PROGRESS

    # The progress values in order, each change kept once.
    values: list[float] = []
    for _, value in series:
        if not values or value != values[-1]:
            values.append(value)
    steps = [
        round(after - before, 2)
        for before, after in pairwise(values)
        if abs(round(after - before, 2)) >= PROGRESS_STEP
    ]
    counts = Counter(event.event_type for event in events)
    snaps = unsnaps = 0
    last_edit = last_run = None
    for event in events:
        if event.event_type == "runProject":
            last_run = event.event_ts
        if event.event_type in EDIT_EVENTS:
            last_edit = event.event_ts
        if event.event_type == "blockMoved" and isinstance(event.block_event, dict):
            old, new = event.block_event.get("oldInfo"), event.block_event.get("newInfo")
            snapped = isinstance(new, dict) and "parent" in new
            snaps += snapped
            unsnaps += isinstance(old, dict) and "parent" in old and not snapped

    spread = max(values) - min(values) if values else 0.0
    reversals = sum(1 for a, b in pairwise(steps) if a * b < 0)
    if level == Level.HIGH and spread >= 10.0 and reversals >= 1:
        return Cognition.TRIAL_AND_ERROR

    busy = level in (Level.MEDIUM, Level.HIGH)
    if len(values) >= 3:
        peak = max(range(len(values)), key=values.__getitem__)
        after_peak = values[peak:]
        falls = [b - a for a, b in pairwise(after_peak)]
        if values[peak] - values[-1] >= 15.0 and falls and all(f <= 0 for f in falls) and busy:
            return Cognition.CODE_ABANDONMENT

    if steps:
        drops = [step for step in steps if step < 0]
        if (
            values[-1] - values[0] >= 10.0
            and len(drops) <= 1
            and direction == Direction.INCREASING
            and busy
        ):
            return Cognition.STEP_BY_STEP_ELIMINATION

    runs = counts["runProject"]
    if (
        runs
        and snaps
        and counts["blockDeleted"] + unsnaps
        and last_run is not None
        and last_edit is not None
        and last_run - last_edit <= timedelta(seconds=90)
    ):
        return Cognition.SNAP_N_TEST
    # A run, then sitting to watch the result: snap-and-test even past the 90 second window.
    if runs and snaps and post_run_pauses and busy:
        return Cognition.SNAP_N_TEST
    return Cognition.UNCLASSIFIED


def snapshot(events: list[Event], playground: Playground | None) -> Snapshot | None:
    """The snapshot of the session's current playground stretch, or None without events."""
    from learner_models import segment_session

    stretch = current_stretch(events)
    if not stretch:
        return None
    time_s = round(max((stretch[-1].event_ts - stretch[0].event_ts).total_seconds(), 0.0), 2)
    per_minute = len(stretch) / max(time_s / 60.0, 1.0)
    level = (
        Level.LOW
        if per_minute < LOW_ACTIONS_PER_MINUTE
        else Level.MEDIUM
        if per_minute <= MEDIUM_ACTIONS_PER_MINUTE
        else Level.HIGH
    )
    score = playground.progress if playground else None
    series = (
        [(e.event_ts, score(parameters(e))) for e in stretch if e.playground_data is not None]
        if score
        else []
    )
    progress = round(series[-1][1], 2) if series else 0.0
    direction = _direction(series, stretch[0].event_ts, stretch[-1].event_ts)
    _, pauses = segment_session(
        [{"event_type": e.event_type, "ts": e.event_ts.timestamp()} for e in stretch]
    )
    post_run_pauses = sum(1 for p in pauses if p["episode_type"] == "POST_RUN_PAUSE")
    return Snapshot(
        playground=stretch[-1].playground,
        time_on_task_s=time_s,
        action_level=level,
        progress_pct=progress if score else None,
        direction=direction,
        cognition=_cognition(
            stretch, series, time_s, level, progress, direction, post_run_pauses, bool(score)
        ),
        persistence=(
            _persistence(time_s, level, progress, direction) if score else Persistence.IN_PROGRESS
        ),
        runs=sum(1 for e in events if e.event_type == "runProject"),
        post_run_pauses=post_run_pauses,
    )


_DIRECTION_WORDS = {
    Direction.INCREASING: "going up",
    Direction.DECREASING: "going down",
    Direction.STATIC: "holding steady",
}
_COGNITION_WORDS = {
    Cognition.LONG_TERM_STALLED_PROGRESS: "has spent a long time with little change in progress",
    Cognition.DEVELOPMENT_INCREASES_PROGRESS: "has been improving their progress with recent changes",
    Cognition.DEVELOPMENT_STATIC_PROGRESS: "has been editing but progress has held steady",
    Cognition.DEVELOPMENT_DECREASES_PROGRESS: "made recent changes that lowered their progress",
    Cognition.TRIAL_AND_ERROR: "is trying many quick changes and re-running to see what happens",
    Cognition.CODE_ABANDONMENT: "removed code that had been improving their progress",
    Cognition.STEP_BY_STEP_ELIMINATION: "is removing pieces one at a time to isolate a problem",
    Cognition.SNAP_N_TEST: "is adding one block at a time and testing after each",
}
_PERSISTENCE_WORDS = {
    Persistence.HIGH_PERSISTER: "has kept trying persistently despite low progress",
    Persistence.EARLY_QUITTER: "showed signs of stopping early",
    Persistence.EXPECTED_COMPLETION: "is at or near finishing the task",
}


def describe(events: list[Event], playground: Playground | None) -> str:
    """The measured facts for the prompt, one per line, in words rather than internal labels.
    "None" when there is nothing to go on."""
    snap = snapshot(events, playground)
    if snap is None:
        return "None"
    lines = []
    if snap.progress_pct is not None:
        lines.append(
            f"Goal progress: {snap.progress_pct:.0f}% ({_DIRECTION_WORDS[snap.direction]})."
        )
    if playground and playground.milestones and (latest := latest_parameters(events)):
        done = [m.label for m in playground.milestones if m.done(latest)]
        todo = [m.label for m in playground.milestones if not m.done(latest)]
        if done:
            lines.append("Milestones done: " + ", ".join(done) + ".")
        if todo:
            lines.append("Still to do: " + ", ".join(todo) + ".")
    lines.append(f"Time on task: {snap.time_on_task_s / 60:.0f} min, {snap.runs} run(s) so far.")
    if pattern := _COGNITION_WORDS.get(snap.cognition):
        lines.append(f"Work pattern: the student {pattern}.")
    if persistence := _PERSISTENCE_WORDS.get(snap.persistence):
        lines.append(f"Persistence: the student {persistence}.")
    if snap.post_run_pauses:
        lines.append(f"The student paused to watch the result {snap.post_run_pauses} time(s).")
    if error := next((e.error_message for e in reversed(events) if e.error_message), None):
        lines.append(f"Most recent error the robot reported: {error}")
    return "\n".join(lines)


def current_program(events: list[Event]) -> str:
    """The student's newest workspace as compact pseudo-code: from the newest run, or the
    newest event with a project. Empty when no event carries one."""
    from learner_models import extract_workspace_xml
    from log_parser_delta_engine import generate_compact_prompt_from_project, generate_readable_text

    runs = [e.project for e in reversed(events) if e.event_type == "runProject" and e.project]
    project = next(iter(runs), None) or next(
        (e.project for e in reversed(events) if e.project), None
    )
    if not project:
        return ""
    return generate_compact_prompt_from_project(json.dumps(project)) or generate_readable_text(
        extract_workspace_xml({"project": project})
    )
