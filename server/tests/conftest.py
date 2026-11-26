"""Shared test setup. Tests that use the `database` fixture need TEST_DATABASE_URL, a Postgres
the tests may wipe (CI starts one). The rest need nothing."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import db, environments, llm
from agent.events import Event, parse_record

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def quiet_settings(monkeypatch):
    for name in (
        "ENVIRONMENTS",
        "NAVIGATOR_MODEL",
        "INVITE_HUB_TOKEN",
        "TRANSCRIBE_MODEL",
        "CHECKINS_ENABLED",
        "TRIGGER_DISABLED",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TURNSTILE", "off")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://llm.invalid/v1")
    llm.reset()
    yield
    llm.reset()


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    monkeypatch.setenv("DATABASE_URL", url)
    db.close()
    with db.pool().connection() as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    db.migrate()
    yield db
    db.close()


def records(name: str) -> list[dict]:
    path = FIXTURES / "vexcode_vr" / name
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def events_of(name: str) -> list[Event]:
    """A fixture's events as the analysis reads them, without a database."""
    env = environments.all_environments()["vexcode-vr"]
    rows = [parse_record(r, env, str(r["id"])) for r in records(name)]
    rows.sort(key=lambda row: (row["event_ts"], int(row["source_id"])))
    return [
        Event(
            id=int(row["source_id"]),
            session_id=row["session_id"],
            event_ts=row["event_ts"],
            event_type=row["event_type"],
            playground=row["playground"],
            project=row["project"],
            block_event=row["block_event"],
            playground_data=row["playground_data"],
            error_message=row["error_message"],
        )
        for row in rows
        if row["playground"]
    ]


def load(name: str) -> None:
    env = environments.all_environments()["vexcode-vr"]
    db.insert_events([parse_record(r, env, str(r["id"])) for r in records(name)])


class FakeLLM:
    """Stands in for the OpenAI client. `answers` are given out in order; the prompts it was
    sent are kept in `prompts`."""

    def __init__(self, *answers: str, finish: str = "stop"):
        self.answers = list(answers)
        self.finish = finish
        self.prompts: list[str] = []
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.models = SimpleNamespace(
            list=lambda: SimpleNamespace(data=[SimpleNamespace(id="gemma-4-31b-it")])
        )

    def _create(self, *, model, messages, **kwargs):
        self.prompts.append(messages[0]["content"])
        self.calls.append({"model": model, **kwargs})
        answer = self.answers.pop(0) if self.answers else ""
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=answer), finish_reason=self.finish)
            ],
            usage=SimpleNamespace(total_tokens=100),
        )


@pytest.fixture
def fake_llm(monkeypatch):
    def install(*answers: str, finish: str = "stop") -> FakeLLM:
        fake = FakeLLM(*answers, finish=finish)
        monkeypatch.setattr(llm, "client", lambda: fake)
        return fake

    return install
