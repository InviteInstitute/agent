"""ZANY inside an ATLAS study: the signed ticket, the study environment, its records in a
stand-in for ATLAS's log_record, and deletion."""

import json
import threading
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from agent import db, study
from agent.app import app
from agent.environments import zany
from tests.test_zany import a_castle_run, record

SECRET = "test-study-secret"
LOG_SCHEMA = """
DROP TABLE IF EXISTS log_record;
CREATE TABLE log_record (
    research_participant text NOT NULL, page_session text NOT NULL, id bigint NOT NULL,
    study_session text NOT NULL, research_study text NOT NULL, event_type text NOT NULL,
    record jsonb NOT NULL, stored_at timestamptz NOT NULL,
    seq bigint GENERATED ALWAYS AS IDENTITY,
    PRIMARY KEY (research_participant, page_session, id)
);
"""
KEY = "demo:t01"


def ticket(**changes):
    payload = {
        "study": "STUDY-0001",
        "code": "DEMO",
        "participant": "T01",
        "session": "STU-SESS-0001",
        "exp": int(time.time()) + 3600,
        **changes,
    }
    return study.sign(payload, SECRET)


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("AGENT_STUDY_SECRET", SECRET)


@pytest.fixture
def log_store(store, secret, monkeypatch):
    monkeypatch.setenv("ENVIRONMENTS", "vexcode-vr,zany,zany-study")
    store.execute(LOG_SCHEMA)
    return store


def keep(store, *records, participant="RP-0001"):
    for r in records:
        store.execute(
            "INSERT INTO log_record (research_participant, page_session, id, study_session,"
            " research_study, event_type, record, stored_at)"
            " VALUES (%s, 'page-1', %s, 'STU-SESS-0001', 'STUDY-0001', %s, %s, %s)",
            (participant, r["id"], r["eventType"], json.dumps(r), datetime.now(UTC)),
        )


def a_study_run(start=0, **who):
    return a_castle_run(start, klass="DEMO", student="T01", **who)


def test_a_signed_ticket_reads_back(secret):
    found = study.read(ticket())
    assert (found.study, found.code, found.participant) == ("STUDY-0001", "DEMO", "T01")
    assert found.frame == "https://zany.inviteai.org/play/?session=STU-SESS-0001"


def test_an_expired_forged_or_garbled_ticket_reads_as_nobody(secret, monkeypatch):
    assert study.read(ticket(exp=int(time.time()) - 1)) is None
    body, mac = ticket().split(".")
    assert study.read(f"{body}.{'0' * len(mac)}") is None
    assert study.read(study.sign({"study": "x"}, SECRET)) is None
    assert study.read("not a ticket") is None
    assert study.read(None) is None
    monkeypatch.delenv("AGENT_STUDY_SECRET")
    assert study.read(ticket()) is None


def test_a_study_student_signs_in_with_the_ticket_and_sees_their_code(log_store):
    keep(log_store, *a_study_run())
    headers = {study.HEADER: ticket()}
    with TestClient(app) as client:
        body = client.get(
            "/v1/zany-study/students/T01", params={"class_code": "DEMO"}, headers=headers
        ).json()
    assert body["frame"] == "https://zany.inviteai.org/play/?session=STU-SESS-0001"
    assert body["session_id"] and body["playground"] == "Castle Crasher+"
    assert db.latest_session("zany-study", KEY)
    assert db.latest_session("zany", KEY) is None  # never mixed with a link student


def test_a_study_student_needs_a_valid_ticket_that_names_them(log_store):
    path, params = "/v1/zany-study/students/T01", {"class_code": "DEMO"}
    with TestClient(app) as client:
        assert client.get(path, params=params).status_code == 403
        expired = {study.HEADER: ticket(exp=int(time.time()) - 1)}
        assert client.get(path, params=params, headers=expired).status_code == 403
        someone_else = {study.HEADER: ticket(participant="T02")}
        assert client.get(path, params=params, headers=someone_else).status_code == 403
        other_study = {"class_code": "OTHER"}
        assert (
            client.get(path, params=other_study, headers={study.HEADER: ticket()}).status_code
            == 403
        )
        stream = client.get(f"{path}/stream", params={**params, "ticket": "bad"})
        assert stream.status_code == 403


def test_the_sign_in_form_never_offers_the_study_environment(log_store):
    with TestClient(app) as client:
        ids = [e["id"] for e in client.get("/v1/environments").json()["environments"]]
    assert ids == ["vexcode-vr", "zany"]


def test_a_ticket_passes_the_turnstile_gate(log_store, monkeypatch):
    monkeypatch.setenv("TURNSTILE", "on")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    with TestClient(app) as client:
        assert client.get("/v1/environments").status_code == 403
        assert client.get("/v1/environments", headers={study.HEADER: "bad"}).status_code == 403
        ok = client.get("/v1/environments", headers={study.HEADER: ticket()})
        assert ok.status_code == 200


def test_a_deletion_in_atlas_forgets_the_study_student_and_their_chat(log_store):
    keep(log_store, *a_study_run(), *a_castle_run(10, klass="DEMO", student="T02"))
    zany.STUDY_ENVIRONMENT.sync("T01", "DEMO")  # both open the agent
    zany.STUDY_ENVIRONMENT.sync("T02", "DEMO")
    session = db.latest_session("zany-study", KEY)
    db.insert_message(
        environment="zany-study",
        student_key=KEY,
        session_id=session,
        chat="student",
        role="student",
        body="help",
    )
    stop = threading.Event()
    watcher = threading.Thread(target=zany.STUDY_ENVIRONMENT.watch, args=(stop,))
    watcher.start()
    try:
        log_store.execute("DELETE FROM log_record WHERE record->>'studentID' = 'T01'")
        notice = {"study": "STUDY-0001", "participant": "T01", "code": "DEMO"}
        for _ in range(50):
            log_store.execute("SELECT pg_notify('zany_forgotten', %s)", (json.dumps(notice),))
            if db.latest_session("zany-study", KEY) is None:
                break
            threading.Event().wait(0.1)
    finally:
        stop.set()
        watcher.join(timeout=10)
    assert db.latest_session("zany-study", KEY) is None
    assert db.latest_session("zany-study", "demo:t02")
    with db.pool().connection() as conn:
        assert conn.execute("SELECT count(*) FROM messages").fetchone()[0] == 0


def test_the_hourly_check_forgets_a_study_student_whose_records_are_gone(log_store):
    keep(log_store, *a_study_run(), *a_castle_run(10, klass="DEMO", student="T02"))
    zany.STUDY_ENVIRONMENT.sync("T01", "DEMO")  # both open the agent
    zany.STUDY_ENVIRONMENT.sync("T02", "DEMO")
    log_store.execute("DELETE FROM log_record WHERE record->>'studentID' = 'T02'")
    assert zany.reconcile_store(zany.STUDY) == 4
    assert db.students_held("zany-study") == {("DEMO", "T01")}


def test_study_records_parse_under_the_study_environment():
    row = zany.parse_records(
        [(record(1, klass="DEMO", student="T01"), "1")], zany.STUDY_ENVIRONMENT
    )
    assert row[0][0]["environment"] == "zany-study" and row[0][0]["student_key"] == KEY


def test_the_background_read_copies_only_students_who_opened_the_agent(log_store):
    keep(log_store, *a_study_run(), *a_castle_run(10, klass="DEMO", student="T02"))
    assert zany.STUDY_ENVIRONMENT.sync() == 0  # nobody has opened the agent yet
    zany.STUDY_ENVIRONMENT.sync("T01", "DEMO")  # T01 signs in
    keep(log_store, *a_study_run(20), *a_castle_run(30, klass="DEMO", student="T02"))
    assert zany.STUDY_ENVIRONMENT.sync() == 4
    assert db.students_held("zany-study") == {("DEMO", "T01")}
