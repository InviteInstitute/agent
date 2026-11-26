"""The coding environments the agent works in. Each one is a module here that says what the
agent page frames, how a student is keyed, where the student's learner logs come from and
which playgrounds the agent knows. Everything else (the analysis, the pedagogy, the chat) is
shared, because every environment logs in VEXcode VR's format.

A deployment serves the environments ENVIRONMENTS names (config.environments).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from agent import config


def fold(text: str | None) -> str:
    """A name as a key: case and surrounding space folded, so Cobra3 and cobra3 match."""
    return (text or "").strip().lower()


def squash(text: str) -> str:
    """A playground name with only its letters and digits, upper case: GO-Mars, GOMars and
    go_mars are all GOMARS."""
    return "".join(ch for ch in text.upper() if ch.isalnum())


@dataclass(frozen=True)
class Milestone:
    label: str
    done: Callable[[dict], bool]  # over the run's playgroundData parameters


@dataclass(frozen=True)
class Playground:
    name: str
    task: str
    blocks: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    milestones: tuple[Milestone, ...] = ()
    # Progress toward the goal, 0 to 100, from a run's playgroundData parameters. None for a
    # playground with nothing to score.
    progress: Callable[[dict], float] | None = None


@dataclass(frozen=True)
class Environment:
    id: str
    name: str
    # How the prompt names the tool to the model.
    tool: str
    # ZANY's logs are keyed by class and student, VEXcode VR's by student alone.
    needs_class_code: bool
    playgrounds: tuple[Playground, ...]
    # The page the agent frames for a student. None while the student still has to sign in.
    frame: Callable[[str | None, str | None], str | None]
    # A student's key from what they sign in with.
    student_key: Callable[[str, str | None], str]
    # Read new learner logs into the events table: everyone's, moving the source's cursor,
    # or one student's (student_id, class_code) without moving it. Returns how many were new.
    sync: Callable[..., int]
    # Work the environment does in the background while the server runs, until the event is
    # set (ZANY listens for ATLAS's deletions).
    watch: Callable[[threading.Event], None] | None = None
    _by_squashed: dict[str, Playground] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        names = {squash(alias): p for p in self.playgrounds for alias in (p.name, *p.aliases)}
        object.__setattr__(self, "_by_squashed", names)

    def playground_name(self, raw: object) -> str | None:
        """A logged playground name as this environment's catalog names it, or as logged
        when the catalog has no such playground. None when nothing was logged."""
        if not isinstance(raw, str) or not raw.strip():
            return None
        known = self._by_squashed.get(squash(raw))
        return known.name if known else raw.strip()

    def playground(self, name: str | None) -> Playground | None:
        return self._by_squashed.get(squash(name)) if name else None


def all_environments() -> dict[str, Environment]:
    from agent.environments import vexcode_vr, zany

    return {env.id: env for env in (vexcode_vr.ENVIRONMENT, zany.ENVIRONMENT)}


def enabled() -> list[Environment]:
    known = all_environments()
    unknown = [name for name in config.environments() if name not in known]
    if unknown:
        raise RuntimeError(f"ENVIRONMENTS names unknown environments: {', '.join(unknown)}")
    return [known[name] for name in config.environments()]


def get(environment_id: str) -> Environment | None:
    """An environment this deployment serves, or None."""
    return next((env for env in enabled() if env.id == environment_id), None)
