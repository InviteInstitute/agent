"""The /v1 routes the client calls. A student is addressed by environment and student ID, plus
the class code in environments that key students by class (ZANY)."""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from agent import config, db, environments, gate, llm, speech
from agent.environments import Environment
from agent.feedback import NO_EVENTS, Reply, answer_question
from agent.pedagogy import PLACEHOLDERS, PROMPT_TEMPLATE
from agent.situation import current_stretch

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1")

HISTORY_LIMIT = 50


@dataclass(frozen=True)
class Student:
    environment: Environment
    student_id: str
    class_code: str | None
    key: str


def student(environment: str, student_id: str, class_code: str | None = None) -> Student:
    env = environments.get(environment)
    if env is None:
        raise HTTPException(404, f"This site does not serve {environment}.")
    student_id = student_id.strip()
    class_code = (class_code or "").strip() or None
    if not student_id or len(student_id) > 100 or len(class_code or "") > 100:
        raise HTTPException(400, "Enter the student ID your teacher gave you.")
    if env.needs_class_code and not class_code:
        raise HTTPException(400, f"{env.name} needs your class code too.")
    return Student(env, student_id, class_code, env.student_key(student_id, class_code))


StudentDep = Annotated[Student, Depends(student)]


def sync_student(who: Student) -> None:
    """Read the student's newest logs, so a reply sees the run they just made. A source that is
    down only means the reply works from what is already kept."""
    try:
        who.environment.sync(who.student_id, who.class_code)
    except Exception:
        log.warning("could not read %s's logs from %s", who.key, who.environment.id, exc_info=True)


class Overrides(BaseModel):
    model: str | None = None
    prompt_template: str | None = Field(None, max_length=20_000)
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=16, le=4096)
    trim_reply: bool = True

    @field_validator("model")
    @classmethod
    def known_model(cls, model: str | None) -> str | None:
        if model and model not in llm.RESEARCH_MODELS | {config.navigator_model()}:
            raise ValueError(f"{model} is not one of the research models")
        return model


class TurnRequest(BaseModel):
    # Empty is the Help button.
    message: str = Field("", max_length=2000)
    # A researcher's settings. A turn with them goes to the research chat, kept apart from
    # what students see.
    overrides: Overrides | None = None
    # The tutor will say the reply, so the server starts making the clips as it answers.
    speak: bool = False


class RatingRequest(BaseModel):
    response_id: UUID
    thumb: Literal["up", "down"]
    comment: str | None = Field(None, max_length=2000)


class SettingsRequest(BaseModel):
    overrides: Overrides | None = None


Chat = Literal["student", "research"]


def history(who: Student, session_id: str | None, chat: Chat) -> list[dict]:
    if not session_id:
        return []
    rows = db.chat_messages(who.environment.id, who.key, session_id, chat, HISTORY_LIMIT)
    return [
        {
            "id": row["id"],
            "role": row["role"],
            "origin": row["origin"],
            "body": row["body"],
            "response_id": str(row["response_id"]) if row["response_id"] else None,
            "trigger_type": row["trigger_type"],
            "thumb": row["thumb"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


@router.get("/environments")
def list_environments() -> dict:
    return {
        "environments": [
            {
                "id": env.id,
                "name": env.name,
                "needs_class_code": env.needs_class_code,
                # What to frame before anyone signs in, if the environment allows it.
                "frame": env.frame(None, None),
            }
            for env in environments.enabled()
        ],
        "voice": speech.voice_on(),
    }


@router.get("/{environment}/students/{student_id}")
def sign_in(who: StudentDep, chat: Chat = "student") -> dict:
    """What the page needs once a student signs in: the frame for them, and their current
    session's chat (or a researcher's chat) so a reload picks up where it was."""
    sync_student(who)
    session_id = db.latest_session(who.environment.id, who.key)
    events = db.session_events(who.environment.id, who.key, session_id) if session_id else []
    stretch = current_stretch(events)
    return {
        "environment": who.environment.id,
        "student_id": who.student_id,
        "class_code": who.class_code,
        "frame": who.environment.frame(who.student_id, who.class_code),
        "session_id": session_id,
        "playground": stretch[-1].playground if stretch else None,
        "messages": history(who, session_id, chat),
    }


@router.post("/{environment}/students/{student_id}/turns")
def take_turn(who: StudentDep, body: TurnRequest, request: Request) -> dict:
    """A student's question (or Help) and the agent's reply to it."""
    key = gate.budget_key(request.cookies.get(gate.COOKIE))
    try:
        gate.check(key)
    except gate.OutOfTokens as error:
        raise HTTPException(429, str(error)) from error

    env = who.environment
    chat = "research" if body.overrides else "student"
    settings = llm.Settings(**body.overrides.model_dump()) if body.overrides else llm.PRODUCTION
    sync_student(who)
    session_id = db.latest_session(env.id, who.key)
    if session_id is None:
        # Nothing logged yet, so there is no session to keep the turn in.
        return {"session_id": None, "reply": {"response_id": None, "body": NO_EVENTS}}
    events = db.session_events(env.id, who.key, session_id)
    message = body.message.strip()
    student_message_id = db.insert_message(
        environment=env.id,
        student_key=who.key,
        session_id=session_id,
        chat=chat,
        role="student",
        body=message or "Help",
    )

    spent: list[int] = []
    try:
        reply: Reply = answer_question(
            env,
            who.key,
            session_id,
            events,
            chat=chat,
            student_message=message or "Help",
            settings=settings,
            spent=spent,
        )
    except Exception as error:
        log.exception("reply failed for %s", who.key)
        raise HTTPException(
            502, "The agent ran into a delay. Try asking again in a moment."
        ) from error
    finally:
        # A call that spent tokens and then failed counts too (llm.complete notes them before
        # it raises), or failing on purpose would be a free way to spend them.
        if sum(spent):
            db.record_llm_usage(
                budget_key=key,
                environment=env.id,
                student_key=who.key,
                model=settings.model or config.navigator_model(),
                origin=chat,
                tokens=sum(spent),
            )

    response_id = uuid4()
    db.insert_message(
        environment=env.id,
        student_key=who.key,
        session_id=session_id,
        chat=chat,
        role="agent",
        body=reply.body,
        response_id=response_id,
        question_type=reply.question_type,
        feedback_classes=reply.feedback or None,
        context=reply.context,
    )
    said = None
    if body.speak:
        said = speech.chunks(reply.body)
        speech.prepare(said)
    log.info(
        "replied to %s/%s (%s, %s): %s",
        env.id,
        who.key,
        reply.question_type or reply.context.get("canned"),
        ", ".join(reply.feedback),
        reply.body,
    )
    return {
        "session_id": session_id,
        "student_message_id": student_message_id,
        "reply": {
            "response_id": str(response_id),
            "body": reply.body,
            "question_type": reply.question_type,
            "feedback": reply.feedback,
            "speech": said,
            # The research chat shows what produced a reply. Students see only the reply.
            **(
                {"model": reply.model, "prompt": reply.context.get("prompt"), "tokens": sum(spent)}
                if chat == "research"
                else {}
            ),
        },
        "session_tokens": gate.usage(key),
    }


STREAM_POLL_S = 2.0


def checkin_event(row: dict) -> str:
    payload = {
        "id": row["id"],
        "body": row["body"],
        "response_id": str(row["response_id"]) if row["response_id"] else None,
        "trigger_type": row["trigger_type"],
        "created_at": row["created_at"].isoformat(),
        "speech": speech.chunks(row["body"]),
    }
    return f"event: checkin\ndata: {json.dumps(payload)}\n\n"


async def checkin_stream(who: Student, request: Request):
    """The student's new check-ins, as server-sent events. It starts at the newest check-in,
    so a new connection replays nothing (the page already loaded the chat), and it polls one
    index-backed query every STREAM_POLL_S seconds. A comment line keeps proxies from closing
    an idle stream."""
    env_id = who.environment.id
    last = await asyncio.to_thread(db.latest_proactive_id, env_id, who.key)
    while not await request.is_disconnected():
        for row in await asyncio.to_thread(db.proactive_after, env_id, who.key, last):
            last = row["id"]
            yield checkin_event(row)
        yield ": keep-alive\n\n"
        await asyncio.sleep(STREAM_POLL_S)


@router.get("/{environment}/students/{student_id}/stream")
def stream(who: StudentDep, request: Request) -> StreamingResponse:
    return StreamingResponse(
        checkin_stream(who, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{environment}/students/{student_id}/ratings", status_code=204)
def rate(who: StudentDep, body: RatingRequest) -> None:
    message_id = db.message_for_response(who.environment.id, who.key, body.response_id)
    if message_id is None:
        raise HTTPException(404, "That reply was not found for this student.")
    db.insert_rating(message_id, body.thumb, (body.comment or "").strip() or None)


@router.put("/{environment}/students/{student_id}/settings", status_code=204)
def save_settings(who: StudentDep, body: SettingsRequest) -> None:
    """A researcher's settings for this student's check-ins, which no request carries."""
    db.save_agent_settings(
        who.environment.id, who.key, body.overrides.model_dump() if body.overrides else None
    )


@router.get("/research/config")
def research_config(request: Request) -> dict:
    default = config.navigator_model()
    try:
        models, models_error = llm.available_models(), None
    except Exception as error:
        log.warning("listing models failed", exc_info=True)
        models, models_error = [], f"Could not list models: {error}"
    return {
        "defaults": {"model": default, "max_tokens": llm.REPLY_MAX_TOKENS, "trim_reply": True},
        "models": models if default in models else [default, *models],
        "models_error": models_error,
        "prompt_template": PROMPT_TEMPLATE,
        "placeholders": PLACEHOLDERS,
        "session_tokens": gate.usage(gate.budget_key(request.cookies.get(gate.COOKIE))),
    }


# About a minute of the browser's Opus. The page stops recording at 30 seconds.
MAX_RECORDING_BYTES = 1_000_000


@router.post("/{environment}/students/{student_id}/transcriptions")
def transcribe(who: StudentDep, request: Request, audio: Annotated[UploadFile, File()]) -> dict:
    """A spoken question as text, which the page then asks like a typed one, so the student
    sees what the tutor heard."""
    if not speech.voice_on():
        raise HTTPException(404, "This site does not take spoken questions.")
    try:
        gate.check(gate.budget_key(request.cookies.get(gate.COOKIE)))
    except gate.OutOfTokens as error:
        raise HTTPException(429, str(error)) from error
    recording = audio.file.read(MAX_RECORDING_BYTES + 1)
    if not recording:
        raise HTTPException(400, "The recording was empty.")
    if len(recording) > MAX_RECORDING_BYTES:
        raise HTTPException(413, "That recording is too long. Keep it under a minute.")
    try:
        text = speech.transcribe(audio.filename or "question.webm", recording)
    except Exception as error:
        log.exception("transcription failed for %s", who.key)
        raise HTTPException(
            502, "Couldn't turn the recording into text. Try again, or type your question."
        ) from error
    return {"text": text}


@router.get("/tts")
def tts(text: str = Query(min_length=1, max_length=500)) -> Response:
    """One spoken line as WAV, for the avatar to play and lip-sync. A whole clip, since Unity
    plays a clip only once it has all of it."""
    try:
        clip = speech.audio(speech.spoken(text))
    except Exception as error:
        log.exception("speech failed")
        raise HTTPException(500, "The tutor's voice is not working right now.") from error
    return Response(
        clip, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"}
    )
