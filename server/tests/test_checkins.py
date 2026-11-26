"""Proactive check-ins against a real Postgres, with the LLM faked."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from agent import api, checkins, db
from agent.environments import vexcode_vr
from tests.conftest import records

ENV = vexcode_vr.ENVIRONMENT
KEY = "spinner"
SESSION = "30000000-0000-0000-0000-000000000001"
START = datetime(2026, 11, 20, 14, 0, tzinfo=UTC)
WORKSPACE = json.loads(records("01_error_flagging_a.ndjson")[0]["project"])


@pytest.fixture(autouse=True)
def fresh_runs():
    checkins.forget_runs()
    yield
    checkins.forget_runs()


def keep_runs(count, *, start=0, playground="GO-Mars", workspace=WORKSPACE):
    """`count` runs of the same program, a minute apart, each with its projectEnd."""
    rows = []
    for i in range(start, start + count):
        for offset, event_type in ((0, "runProject"), (20, "projectEnd")):
            rows.append(
                {
                    "environment": ENV.id,
                    "source_id": f"{event_type}-{i}",
                    "student_key": KEY,
                    "student_id": KEY,
                    "class_code": None,
                    "session_id": SESSION,
                    "event_ts": START + timedelta(minutes=i, seconds=offset),
                    "received_at": None,
                    "event_type": event_type,
                    "playground": playground,
                    "project": workspace,
                    "block_event": None,
                    "playground_data": None,
                    "error_message": None,
                }
            )
    db.insert_events(rows)
    return START + timedelta(minutes=start + count - 1, seconds=20)


def check_ins():
    with db.pool().connection() as conn:
        return conn.execute(
            "SELECT trigger_type, body, context FROM messages WHERE origin = 'proactive' ORDER BY id"
        ).fetchall()


def test_running_the_same_program_again_and_again_gets_one_check_in(database, fake_llm):
    last = keep_runs(7)
    fake = fake_llm("Does your robot do anything different each time you run it?")
    sent = checkins.tick_student(ENV, KEY, now=last + timedelta(seconds=10))
    assert len(sent) == 1
    [(trigger, body, context)] = check_ins()
    assert trigger == "wheel_spin"
    assert body == "Does your robot do anything different each time you run it?"
    prompt = fake.prompts[0]
    assert NEUTRAL in prompt and "Wheel" not in prompt and "wheel_spin" not in prompt
    assert "None (no student question; this is a proactive check-in)" in prompt
    assert context["trigger"]
    # The same trigger never fires twice, and check-ins count toward the daily ceiling.
    assert checkins.tick_student(ENV, KEY, now=last + timedelta(seconds=20)) == []
    assert db.tokens_for_budget_key(checkins.BUDGET_KEY) == 100


NEUTRAL = checkins.NEUTRAL_FACT["wheel_spin"]


def test_an_idle_student_hears_once_then_again_after_the_re_alert_wait(database, fake_llm):
    last = keep_runs(1)
    fake_llm("Still there?", "Want a hand?")
    assert len(checkins.tick_student(ENV, KEY, now=last + timedelta(minutes=5))) == 1
    assert checkins.tick_student(ENV, KEY, now=last + timedelta(minutes=8)) == []
    assert len(checkins.tick_student(ENV, KEY, now=last + timedelta(minutes=16))) == 1
    assert [row[0] for row in check_ins()] == ["inactive", "inactive"]


def test_coming_back_closes_the_idle_trigger(database, fake_llm):
    last = keep_runs(1)
    fake_llm("Still there?")
    checkins.tick_student(ENV, KEY, now=last + timedelta(minutes=5))
    keep_runs(1, start=10)
    checkins.tick_student(ENV, KEY, now=START + timedelta(minutes=10, seconds=30))
    with db.pool().connection() as conn:
        assert conn.execute("SELECT resolved_at IS NOT NULL FROM triggers").fetchone()[0]


def test_a_turned_off_trigger_is_kept_but_not_acted_on(database, fake_llm, monkeypatch):
    monkeypatch.setenv("TRIGGER_DISABLED", "wheel_spin, inactive")
    last = keep_runs(7)
    fake = fake_llm()
    assert checkins.tick_student(ENV, KEY, now=last + timedelta(minutes=5)) == []
    assert fake.prompts == []
    with db.pool().connection() as conn:
        kept = {row[0] for row in conn.execute("SELECT trigger_type FROM triggers")}
    assert kept == {"wheel_spin", "inactive"}


def test_no_check_in_on_a_playground_the_agent_does_not_know(database, fake_llm):
    last = keep_runs(7, playground="Some Other Playground")
    fake = fake_llm()
    assert checkins.tick_student(ENV, KEY, now=last + timedelta(seconds=10)) == []
    assert fake.prompts == []


def test_a_tick_reads_the_logs_then_every_recent_student(database, fake_llm, monkeypatch):
    synced = []
    object.__setattr__(ENV, "sync", lambda *args: synced.append(args) or 0)
    try:
        keep_runs(7)
        monkeypatch.setattr(checkins, "tick_student", lambda env, key: [1] if key == KEY else [])
        monkeypatch.setenv("STUDENT_RECENCY_HOURS", str(24 * 365 * 10))
        assert checkins.tick() == 1
        assert synced == [()]
    finally:
        object.__setattr__(ENV, "sync", vexcode_vr.sync)


class FakeRequest:
    def __init__(self, polls):
        self.polls = polls

    async def is_disconnected(self):
        self.polls -= 1
        return self.polls < 0


def test_the_stream_sends_only_check_ins_made_after_it_opened(database, monkeypatch):
    monkeypatch.setattr(api, "STREAM_POLL_S", 0)
    keep_runs(1)
    before = db.insert_message(
        environment=ENV.id,
        student_key=KEY,
        session_id=SESSION,
        chat="student",
        role="agent",
        origin="proactive",
        body="old",
        trigger_type="inactive",
    )
    who = api.Student(ENV, KEY, None, KEY)

    async def read():
        frames = []
        async for frame in api.checkin_stream(who, FakeRequest(polls=2)):
            frames.append(frame)
            if len(frames) == 1:
                db.insert_message(
                    environment=ENV.id,
                    student_key=KEY,
                    session_id=SESSION,
                    chat="student",
                    role="agent",
                    origin="proactive",
                    body="new one",
                    trigger_type="explorer",
                )
        return frames

    frames = asyncio.run(read())
    events = [f for f in frames if f.startswith("event: checkin")]
    assert len(events) == 1
    payload = json.loads(events[0].split("data: ", 1)[1])
    assert payload["body"] == "new one" and payload["trigger_type"] == "explorer"
    assert payload["id"] > before
