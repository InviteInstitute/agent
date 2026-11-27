"""ZANY: link records read from a stand-in for ATLAS-invite's log store, which tests make in
a database beside the agent's (ZANY_STORE_URL, else zany_store_test next to TEST_DATABASE_URL)."""

import json
import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from agent import db
from agent.app import app
from agent.environments import zany
from agent.feedback import wrong_playground
from agent.situation import describe, snapshot

START = datetime(2026, 11, 20, 14, 0, tzinfo=UTC)


def record(n, *, student="S01", klass="room-4", session=None, event="blockMoved", **raw):
    """A ZANY record, as src/vex-logs.ts writes it."""
    at = START + timedelta(seconds=20 * n)
    project = {"workspace": "<xml></xml>", "playground": "CastleCrasherPlus"}
    message = {
        "eventType": event,
        "classCode": klass,
        "studentID": student,
        "sessionID": session or "7d0e0c2e-0000-4000-8000-000000000001",
        "timestamp": at.isoformat().replace("+00:00", "Z"),
        "project": json.dumps(project),
        "playground": "CastleCrasherPlus",
        **raw,
    }
    return {
        "id": n,
        "eventType": event,
        "classCode": klass,
        "studentID": student,
        "project": json.dumps(project),
        "raw_message": json.dumps(message),
        "received_at": at.isoformat(),
    }


def keep(store, *records, stored_at=None):
    for r in records:
        store.execute(
            "INSERT INTO link_record (student_id, page_session, id, class_code, event_type,"
            " record, stored_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                r["studentID"],
                "page-1",
                r["id"],
                r["classCode"],
                r["eventType"],
                json.dumps(r),
                stored_at or datetime.now(UTC),
            ),
        )


def a_castle_run(start=0, cleared=1200, **who):
    return [
        record(start, **who),
        record(start + 1, event="runProject", **who),
        record(
            start + 2,
            event="playgroundData",
            playgroundData={
                "playground": "CasteCrasherPlus",
                "parameters": {"weight_cleared": cleared, "difficulty_level": 1},
            },
            **who,
        ),
        record(start + 3, event="projectEnd", **who),
    ]


def test_everyone_sync_reads_new_records_and_moves_the_cursor(store):
    keep(store, *a_castle_run())
    assert zany.ENVIRONMENT.sync() == 4
    assert zany.ENVIRONMENT.sync() == 0
    assert db.cursor(zany.SOURCE)["seq"] == 4
    keep(store, record(10))
    assert zany.ENVIRONMENT.sync() == 1


def test_one_students_sync_leaves_the_cursor(store):
    keep(store, *a_castle_run(), *a_castle_run(10, student="S02"))
    assert zany.ENVIRONMENT.sync("S01", "room-4") == 4
    assert db.cursor(zany.SOURCE) is None
    assert db.latest_session("zany", "room-4:s02") is None


def test_the_same_student_id_in_two_classes_is_two_students(store):
    keep(store, *a_castle_run(), *a_castle_run(10, klass="room-5"))
    zany.ENVIRONMENT.sync()
    assert db.latest_session("zany", "room-4:s01") and db.latest_session("zany", "room-5:s01")


def test_castle_progress_is_the_weight_cleared(store):
    keep(store, *a_castle_run(cleared=4025))
    zany.ENVIRONMENT.sync()
    session = db.latest_session("zany", "room-4:s01")
    events = db.session_events("zany", "room-4:s01", session)
    assert {e.playground for e in events} == {"Castle Crasher+"}
    text = describe(snapshot(events, zany.CASTLE), events, zany.CASTLE)
    assert text.startswith("Goal progress: 50%")
    assert (
        "Milestones done: push a piece of the castle into the water, clear half the castle." in text
    )


def test_the_frame_carries_the_ids_and_needs_them():
    assert zany.frame(None, None) is None
    assert zany.frame("S 01", "room-4") == "https://vr.inviteai.org/?class=room-4&student=S+01"


def test_an_unknown_playground_names_all_three():
    assert wrong_playground(zany.ENVIRONMENT) == (
        "I can help with Castle Crasher+, Coral Reef Cleanup or Art Canvas right now. "
        "Switch to one of those, then ask for help again."
    )


def test_a_deletion_in_atlas_forgets_the_student_here(store):
    keep(store, *a_castle_run(), *a_castle_run(10, student="S02"))
    zany.ENVIRONMENT.sync()
    session = db.latest_session("zany", "room-4:s01")
    db.insert_message(
        environment="zany",
        student_key="room-4:s01",
        session_id=session,
        chat="student",
        role="student",
        body="help",
    )
    stop = threading.Event()
    watcher = threading.Thread(target=zany.ENVIRONMENT.watch, args=(stop,))
    watcher.start()
    try:
        # ATLAS's forget_link deletes, then notifies.
        store.execute("DELETE FROM link_record WHERE student_id = 'S01'")
        for _ in range(50):
            store.execute(
                "SELECT pg_notify(%s, %s)",
                (zany.FORGOTTEN, json.dumps({"student": "S01", "class_code": None})),
            )
            if db.latest_session("zany", "room-4:s01") is None:
                break
            threading.Event().wait(0.1)
    finally:
        stop.set()
        watcher.join(timeout=10)
    assert db.latest_session("zany", "room-4:s01") is None
    assert db.latest_session("zany", "room-4:s02")
    with db.pool().connection() as conn:
        assert conn.execute("SELECT count(*) FROM messages").fetchone()[0] == 0


def test_the_hourly_check_forgets_what_a_missed_notice_left(store):
    keep(store, *a_castle_run(), *a_castle_run(10, student="S02"))
    zany.ENVIRONMENT.sync()
    store.execute("DELETE FROM link_record WHERE student_id = 'S02'")
    assert zany.reconcile_store(zany.LINK) == 4
    assert db.students_held("zany") == {("room-4", "S01")}


def test_sign_in_needs_the_class_and_frames_zany_with_the_ids(store, fake_llm):
    keep(store, *a_castle_run())
    with TestClient(app) as client:
        assert client.get("/v1/zany/students/S01").status_code == 400
        body = client.get("/v1/zany/students/S01", params={"class_code": "room-4"}).json()
        assert body["frame"] == "https://vr.inviteai.org/?class=room-4&student=S01"
        assert body["playground"] == "Castle Crasher+"

        fake = fake_llm("1", "Try pushing the keep from the east gate.")
        reply = client.post(
            "/v1/zany/students/S01/turns",
            params={"class_code": "room-4"},
            json={"message": "how do i push it in"},
        ).json()["reply"]
        assert reply["body"] == "Try pushing the keep from the east gate."
        assert "You are an educational feedback assistant for ZANY" in fake.prompts[1]
        assert "Castle Crasher+" in fake.prompts[1]

        environments = client.get("/v1/environments").json()["environments"]
        assert [(e["id"], e["needs_class_code"], e["frame"]) for e in environments] == [
            ("vexcode-vr", False, "https://research-vr.vex.com/"),
            ("zany", True, None),
        ]


def test_records_are_parsed_by_the_shared_parser():
    row = zany.parse_records([(record(1), "1")], zany.ENVIRONMENT)[0][0]
    assert row["student_key"] == "room-4:s01" and row["playground"] == "Castle Crasher+"
    assert uuid.UUID(row["session_id"])
