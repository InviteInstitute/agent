"""The routes against a real Postgres, with the LLM faked and no Invite Hub."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from agent import db
from agent.app import app
from agent.environments import vexcode_vr
from agent.feedback import ACTIVE_RUN, NO_EVENTS
from tests.conftest import load

STUDENT = "/v1/vexcode-vr/students/fixture_01_1"


@pytest.fixture
def client(database):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def no_hub():
    # Environment is frozen, so its sync is swapped past the dataclass guard.
    object.__setattr__(vexcode_vr.ENVIRONMENT, "sync", lambda *args, **kwargs: 0)
    yield
    object.__setattr__(vexcode_vr.ENVIRONMENT, "sync", vexcode_vr.sync)


def test_environments_and_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    body = client.get("/v1/environments").json()
    assert "avatar" not in body
    assert body["environments"] == [
        {
            "id": "vexcode-vr",
            "name": "VEXcode VR",
            "needs_class_code": False,
            "frame": "https://research-vr.vex.com/",
        }
    ]
    assert client.get("/v1/zany/students/S01").status_code == 404


def test_sign_in_before_any_logs(client):
    body = client.get(STUDENT).json()
    assert body["session_id"] is None and body["messages"] == []
    reply = client.post(f"{STUDENT}/turns", json={"message": "help me"}).json()
    assert reply["reply"]["body"] == NO_EVENTS


def test_a_question_gets_a_grounded_reply_kept_with_what_produced_it(client, fake_llm):
    load("01_error_flagging_a.ndjson")
    fake = fake_llm("2", "Your `drive` block is not connected to `when started`.")
    body = client.post(f"{STUDENT}/turns", json={"message": "why won't it move"}).json()

    reply = body["reply"]
    assert reply["body"] == "Your `drive` block is not connected to `when started`."
    assert reply["question_type"] == "Debugging / Problem Diagnosis"
    assert reply["feedback"] == ["Error Flagging"]
    assert "prompt" not in reply  # students see only the reply
    assert body["session_tokens"] == {"used": 200, "limit": 150_000}

    classifier, prompt = fake.prompts
    assert "why won't it move" in classifier
    assert "Student: why won't it move" in prompt  # the turn is in its own recent chat
    assert "Debugging / Problem Diagnosis" in prompt
    assert "- Error Flagging" in prompt

    # A reload shows the chat, and the reply can be rated.
    messages = client.get(STUDENT).json()["messages"]
    assert [m["role"] for m in messages] == ["student", "agent"]
    rated = client.post(
        f"{STUDENT}/ratings", json={"response_id": reply["response_id"], "thumb": "up"}
    )
    assert rated.status_code == 204
    assert client.get(STUDENT).json()["messages"][1]["thumb"] == "up"
    with db.pool().connection() as conn:
        context = conn.execute("SELECT context FROM messages WHERE role = 'agent'").fetchone()[0]
    assert context["playground"] == "GO-Mars" and "Goal progress" in context["situation"]


def test_research_turns_stay_out_of_the_student_chat(client, fake_llm):
    load("01_error_flagging_a.ndjson")
    fake_llm("2", "Research reply.", "2", "Student reply.")
    research = client.post(
        f"{STUDENT}/turns", json={"message": "a", "overrides": {"model": "gemma-4-31b-it"}}
    ).json()
    assert research["reply"]["model"] == "gemma-4-31b-it"
    assert research["reply"]["prompt"]
    client.post(f"{STUDENT}/turns", json={"message": "b"})
    assert [m["body"] for m in client.get(STUDENT).json()["messages"]] == ["b", "Student reply."]
    research_chat = client.get(STUDENT, params={"chat": "research"}).json()["messages"]
    assert [m["body"] for m in research_chat] == ["a", "Research reply."]


def test_an_unknown_model_is_refused(client):
    response = client.post(f"{STUDENT}/turns", json={"overrides": {"model": "gpt-5"}})
    assert response.status_code == 422


def test_help_is_a_turn_with_no_message(client, fake_llm):
    load("01_error_flagging_a.ndjson")
    fake = fake_llm("3", "What part do you want help with?")
    client.post(f"{STUDENT}/turns", json={})
    assert "Student message:\nHelp" in fake.prompts[1]
    assert client.get(STUDENT).json()["messages"][0]["body"] == "Help"


def test_a_run_still_going_gets_asked_to_stop_first(client, fake_llm):
    load("01_error_flagging_a.ndjson")
    session = db.latest_session("vexcode-vr", "fixture_01_1")
    last = db.session_events("vexcode-vr", "fixture_01_1", session)[-1]
    db.insert_events(
        [
            {
                "environment": "vexcode-vr",
                "source_id": "run-still-going",
                "student_key": "fixture_01_1",
                "student_id": "fixture_01_1",
                "class_code": None,
                "session_id": session,
                "event_ts": last.event_ts + timedelta(seconds=5),
                "received_at": None,
                "event_type": "runProject",
                "playground": "GO-Mars",
                "project": last.project,
                "block_event": None,
                "playground_data": None,
                "error_message": None,
            }
        ]
    )
    fake = fake_llm()
    assert client.post(f"{STUDENT}/turns", json={}).json()["reply"]["body"] == ACTIVE_RUN
    assert fake.prompts == []


def test_out_of_tokens_is_429(client, fake_llm, monkeypatch):
    load("01_error_flagging_a.ndjson")
    monkeypatch.setenv("LLM_SESSION_TOKEN_LIMIT", "150")
    fake_llm("2", "One.")
    assert client.post(f"{STUDENT}/turns", json={"message": "a"}).status_code == 200
    second = client.post(f"{STUDENT}/turns", json={"message": "b"})
    assert second.status_code == 429 and "150" in second.json()["detail"]


def test_a_failed_reply_still_counts_its_tokens(client, fake_llm):
    load("01_error_flagging_a.ndjson")
    fake_llm("2", "", "")  # classifier, then a reply that never comes
    response = client.post(f"{STUDENT}/turns", json={"message": "a"})
    assert response.status_code == 502
    assert db.tokens_last_day() == 300


def test_the_gate_wants_a_solved_challenge(client, monkeypatch):
    monkeypatch.setenv("TURNSTILE", "on")
    monkeypatch.setenv("SESSION_SECRET", "s")
    assert client.get("/v1/ping").json() == {"error": "turnstile_required"}
    assert client.get("/healthz").status_code == 200
