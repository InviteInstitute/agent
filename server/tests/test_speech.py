"""The tutor's voice and spoken questions."""

import io
import time
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from agent import speech
from agent.app import app
from agent.environments import vexcode_vr
from tests.conftest import load

STUDENT = "/v1/vexcode-vr/students/fixture_01_1"


@pytest.fixture(autouse=True)
def fresh_clips():
    speech.forget_clips()
    yield
    speech.forget_clips()


@pytest.fixture
def client(database, monkeypatch):
    monkeypatch.setenv("AVATAR_ENABLED", "true")
    monkeypatch.setattr(speech, "warm", lambda: None)
    object.__setattr__(vexcode_vr.ENVIRONMENT, "sync", lambda *args: 0)
    with TestClient(app) as test_client:
        yield test_client
    object.__setattr__(vexcode_vr.ENVIRONMENT, "sync", vexcode_vr.sync)


def test_a_reply_is_said_without_block_markup_a_sentence_per_clip():
    reply = "Check your `drive [forward/reverse] for [number] [mm/inches]` block. Does it run?"
    assert speech.spoken(reply) == "Check your drive for block. Does it run?"
    assert speech.chunks(reply) == ["Check your drive for block.", "Does it run?"]


def test_clips_are_trimmed_to_a_short_pause():
    rate = 1000
    samples = np.concatenate([np.zeros(500), np.full(100, 0.5), np.zeros(800)])
    trimmed = speech.trim_silence(samples, rate)
    assert len(trimmed) == 50 + 100 + 120


def test_wav_has_a_complete_header():
    with wave.open(io.BytesIO(speech._wav(np.zeros(2400), 24000))) as clip:
        assert (clip.getnchannels(), clip.getsampwidth(), clip.getnframes()) == (1, 2, 2400)


def test_clip_jobs_are_shared_and_a_failed_one_is_retried(monkeypatch):
    made = []

    def synthesize(text):
        made.append(text)
        if len(made) == 1:
            raise RuntimeError("first try fails")
        return b"RIFF"

    monkeypatch.setattr(speech, "synthesize", synthesize)
    with pytest.raises(RuntimeError):
        speech.audio("hi")
    assert speech.audio("hi") == b"RIFF"
    assert speech.audio("hi") == b"RIFF"
    assert made == ["hi", "hi"]


@pytest.mark.skipif(not (speech.MODELS / "paradee_int8.onnx").exists(), reason="no voice model")
def test_the_real_voice_says_a_sentence():
    started = time.monotonic()
    clip = speech.synthesize("Try turning right before the crater.")
    with wave.open(io.BytesIO(clip)) as out:
        seconds = out.getnframes() / out.getframerate()
    assert 1.0 < seconds < 5.0
    assert time.monotonic() - started < 30


def test_a_spoken_reply_comes_with_its_clips_started(client, fake_llm, monkeypatch):
    load("01_error_flagging_a.ndjson")
    fake_llm("2", "Your `drive` block is loose. Snap it under `when started`.")
    prepared = []
    monkeypatch.setattr(speech, "prepare", prepared.extend)
    reply = client.post(f"{STUDENT}/turns", json={"message": "why", "speak": True}).json()["reply"]
    assert reply["speech"] == ["Your drive block is loose.", "Snap it under when started."]
    assert prepared == reply["speech"]


def test_tts_serves_a_clip_and_only_with_the_avatar(client, monkeypatch):
    monkeypatch.setattr(speech, "audio", lambda text: b"RIFF" + text.encode())
    response = client.get("/v1/tts", params={"text": "Use the `turn` block."})
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFFUse the turn block."
    monkeypatch.setenv("AVATAR_ENABLED", "false")
    assert client.get("/v1/tts", params={"text": "hi"}).status_code == 404
    assert client.get("/v1/tts", params={"text": "x" * 501}).status_code == 422


def test_a_spoken_question_comes_back_as_text(client, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_MODEL", "granite-speech")
    heard = []
    monkeypatch.setattr(
        speech, "transcribe", lambda name, data: heard.append((name, data)) or "where is the lab"
    )
    url = f"{STUDENT}/transcriptions"
    response = client.post(url, files={"audio": ("q.webm", b"opus", "audio/webm")})
    assert response.json() == {"text": "where is the lab"}
    assert heard == [("q.webm", b"opus")]
    assert client.post(url, files={"audio": ("q.webm", b"", "audio/webm")}).status_code == 400
    too_long = b"x" * (1_000_001)
    assert client.post(url, files={"audio": ("q.webm", too_long, "audio/webm")}).status_code == 413
    assert client.get("/v1/environments").json()["voice"] is True


def test_a_failed_transcription_says_to_try_again(client, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_MODEL", "granite-speech")

    def broken(name, data):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(speech, "transcribe", broken)
    response = client.post(
        f"{STUDENT}/transcriptions", files={"audio": ("q.webm", b"opus", "audio/webm")}
    )
    assert response.status_code == 502 and "type your question" in response.json()["detail"]


def test_no_spoken_questions_without_a_model(client):
    response = client.post(
        f"{STUDENT}/transcriptions", files={"audio": ("q.webm", b"opus", "audio/webm")}
    )
    assert response.status_code == 404
