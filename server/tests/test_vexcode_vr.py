"""Reading logs from the Invite Hub, with the Hub mocked."""

from datetime import UTC, datetime

import httpx
import pytest

from agent import db
from agent.environments import vexcode_vr
from tests.conftest import records


@pytest.fixture
def hub(monkeypatch):
    """A fake Hub serving `pages` (one list of records per offset) and noting each request."""
    state = {"pages": [], "requests": [], "reject_first": False}

    def handle(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"token": f"t{len(state['requests'])}"})
        if state["reject_first"]:
            state["reject_first"] = False
            return httpx.Response(401, json={"detail": "bad token"})
        index = int(request.url.params["offset"]) // vexcode_vr.PAGE
        pages = state["pages"]
        return httpx.Response(200, json={"results": pages[index] if index < len(pages) else []})

    real = httpx.Client
    monkeypatch.setattr(
        vexcode_vr.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handle), **kw)
    )
    monkeypatch.setenv("INVITE_HUB_USERNAME", "u")
    monkeypatch.setenv("INVITE_HUB_PASSWORD", "p")
    monkeypatch.setattr(vexcode_vr, "_token", None)
    return state


def test_everyone_sync_keeps_the_records_and_moves_the_cursor(database, hub):
    session = records("01_error_flagging_a.ndjson")
    hub["pages"] = [session]
    assert vexcode_vr.sync() == len(session)
    assert vexcode_vr.sync() == 0  # read again, kept once
    position = db.cursor(vexcode_vr.SOURCE)
    assert position["seq"] == max(r["id"] for r in session)

    # The next sync asks only for what came after the cursor, less the overlap.
    date_from = hub["requests"][-1].url.params["dateFrom"]
    assert datetime.fromisoformat(date_from) < datetime.fromisoformat(position["at"])


def test_a_fresh_database_starts_at_the_recency_window(database, hub):
    vexcode_vr.sync()
    since = datetime.fromisoformat(hub["requests"][-1].url.params["dateFrom"])
    hours = (datetime.now(UTC) - since).total_seconds() / 3600
    assert 23.9 < hours < 24.1


def test_one_students_sync_leaves_the_cursor(database, hub):
    hub["pages"] = [records("01_error_flagging_a.ndjson")]
    assert vexcode_vr.sync("fixture_01_1") > 0
    assert hub["requests"][-1].url.params["studentID"] == "fixture_01_1"
    assert "dateFrom" not in hub["requests"][-1].url.params
    assert db.cursor(vexcode_vr.SOURCE) is None


def test_it_pages_until_a_short_page(database, hub, monkeypatch):
    monkeypatch.setattr(vexcode_vr, "PAGE", 10)
    session = records("02_elaborate_a.ndjson")
    hub["pages"] = [session[i : i + 10] for i in range(0, len(session), 10)]
    assert vexcode_vr.sync() == len(session)


def test_a_rejected_token_is_renewed_once(database, hub):
    hub["pages"] = [records("01_error_flagging_a.ndjson")]
    vexcode_vr.sync()  # logs in
    hub["reject_first"] = True
    vexcode_vr.sync()
    logins = [r for r in hub["requests"] if r.url.path == "/api/token/"]
    assert len(logins) == 2
