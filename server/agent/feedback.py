"""The one feedback pipeline. A student's question and a proactive check-in run the same steps,
so the pedagogy is the same on both: measure the session, pick the feedback classes, build the
grounded prompt and make one reply call. A question is first sorted into a question type.

Only the inputs differ. A question brings the student's message. A check-in brings a neutral
fact about what the student did (never the trigger's internal label) and no message.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agent import config, db, llm
from agent.environments import Environment, Playground
from agent.events import Event
from agent.pedagogy import (
    PROMPT_TEMPLATE,
    Feedback,
    build_prompt,
    classifier_prompt,
    feedback_for,
    feedback_names,
    parse_question_type,
)
from agent.situation import current_program, current_stretch, describe, has_active_run, snapshot

log = logging.getLogger(__name__)

RECENT_TURNS = 6

NO_EVENTS = "Run your project once so I can see your code, then ask me again."
ACTIVE_RUN = (
    "Please stop your current run using the Stop button in the bottom-left of the playground, "
    "then ask for help again."
)


def wrong_playground(environment: Environment) -> str:
    names = [p.name for p in environment.playgrounds]
    if len(names) == 1:
        return f"I can help with {names[0]} right now. Switch to it, then ask for help again."
    places = ", ".join(names[:-1]) + f" or {names[-1]}"
    return f"I can help with {places} right now. Switch to one of those, then ask for help again."


@dataclass
class Reply:
    body: str
    feedback: list[str] = field(default_factory=list)
    question_type: str | None = None
    model: str | None = None
    # What the agent saw, kept with the reply for research. Empty for a canned answer.
    context: dict = field(default_factory=dict)


def canned(body: str, reason: str) -> Reply:
    return Reply(body=body, context={"canned": reason})


def answer_question(
    environment: Environment,
    student_key: str,
    session_id: str,
    events: list[Event],
    *,
    chat: str,
    student_message: str,
    settings: llm.Settings,
    spent: list[int],
) -> Reply:
    """The reply to a student's question (or Help). Answers without the model when it cannot
    help yet: no events, a playground it does not know, or a run still going."""
    stretch = current_stretch(events)
    if not stretch:
        return canned(NO_EVENTS, "no_events")
    playground = environment.playground(stretch[-1].playground)
    if playground is None:
        return canned(wrong_playground(environment), "unknown_playground")
    if has_active_run(events):
        return canned(ACTIVE_RUN, "active_run")
    return generate(
        environment,
        student_key,
        session_id,
        events,
        playground,
        feedback_for(snapshot(events, playground)),
        chat=chat,
        student_message=student_message,
        settings=settings,
        spent=spent,
    )


def classify(student_message: str, model: str, tool: str, spent: list[int]):
    """The question type of a student's message, by a small separate call on the same model."""
    try:
        answer = llm.complete(
            model,
            classifier_prompt(student_message, tool),
            max_tokens=llm.CLASSIFIER_MAX_TOKENS,
            spent=spent,
        )
    except Exception:
        # A failed classifier must not cost the student their reply. GENERAL asks them what
        # kind of help they need, which is the safe scaffolding.
        log.warning("question classifier failed, using the general type", exc_info=True)
        answer = None
    return parse_question_type(answer)


def generate(
    environment: Environment,
    student_key: str,
    session_id: str,
    events: list[Event],
    playground: Playground,
    feedback: set[Feedback],
    *,
    chat: str,
    student_message: str = "",
    behavior_fact: str | None = None,
    settings: llm.Settings = llm.PRODUCTION,
    spent: list[int],
) -> Reply:
    """One grounded reply. Every LLM call's tokens are appended to `spent`, even when a call
    fails, so the caller can count them."""
    model = settings.model or config.navigator_model()
    situation = describe(events, playground)
    if behavior_fact:
        situation = f"{situation}\n\n{behavior_fact}"
    question = (
        classify(student_message, model, environment.tool, spent) if student_message else None
    )
    prompt = build_prompt(
        template=settings.prompt_template or PROMPT_TEMPLATE,
        tool=environment.tool,
        task=playground.task,
        blocks=playground.blocks,
        program=current_program(events),
        student_message=student_message,
        question=question,
        situation=situation,
        recent_chat=db.chat_messages(environment.id, student_key, session_id, chat, RECENT_TURNS),
        feedback=feedback,
    )
    text = llm.sanitize(
        llm.complete(
            model,
            prompt,
            max_tokens=settings.max_tokens or llm.REPLY_MAX_TOKENS,
            temperature=settings.temperature,
            spent=spent,
        )
    )
    if settings.trim_reply:
        text = llm.trim(text)
    return Reply(
        body=text,
        feedback=feedback_names(feedback),
        question_type=question.value.name if question else None,
        model=model,
        context={
            "playground": playground.name,
            "situation": situation,
            "prompt": prompt,
            "settings": settings.as_dict(),
            "tokens": sum(spent),
        },
    )
