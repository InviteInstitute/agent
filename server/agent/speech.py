"""Speech: the 3D tutor says replies out loud, and students can ask out loud.

Saying runs in this process with Paradee-8M (an 8M-parameter distillation of Kokoro-82M) on
ONNX Runtime, about 0.2 s for a full reply on the server's CPU. The avatar cannot start a clip
until it has all of it, so a reply is said a sentence per clip (chunks): the first sentence
plays while the next is made. Clips are cached jobs, so a reply prepared as it was written, or
a line many students hear, is ready when the avatar asks for it.

Hearing goes to the LLM gateway's speech-to-text model (TRANSCRIBE_MODEL, granite-speech on
Lumen). The browser records WebM/Opus, which it takes as is.

The model files come from `python -m agent fetch-voice` into server/models/ (the image has them).
"""

import io
import re
import threading
import wave
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from agent import config, llm

MODELS = Path(__file__).resolve().parents[1] / "models"
RELEASE = "https://huggingface.co/sahilmahendrakar/Paradee-8M-v1.2/resolve/v1.2"
MODEL_FILES = {"paradee_int8.onnx": "onnx/paradee_int8.onnx", "paradee_config.json": "config.json"}
# Paradee pads a clip with about 0.3 s of silence before and 0.5 s after. Said a sentence per
# clip, that leaves long gaps, so clips are trimmed to Kokoro's padding.
_QUIET = 0.01
_KEEP_BEFORE, _KEEP_AFTER = 0.05, 0.12


def voice_on() -> bool:
    """Whether students can ask out loud on this site."""
    return bool(config.text("TRANSCRIBE_MODEL"))


def fetch_model() -> None:
    """Download the model files, once (a partial download never takes the real name)."""
    import urllib.request

    MODELS.mkdir(exist_ok=True)
    for name, source in MODEL_FILES.items():
        target = MODELS / name
        if not target.exists():
            partial = target.with_suffix(target.suffix + ".part")
            urllib.request.urlretrieve(f"{RELEASE}/{source}", partial)
            partial.rename(target)


@lru_cache(maxsize=1)
def _paradee():
    from paradee import Paradee  # onnxruntime and spaCy load slowly, and tests stub this

    return Paradee(
        model_path=str(MODELS / "paradee_int8.onnx"),
        config_path=str(MODELS / "paradee_config.json"),
        threads=4,
    )


def _wav(samples, sample_rate: int) -> bytes:
    """Float samples in [-1, 1] as 16-bit mono PCM WAV."""
    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(pcm)
    return buffer.getvalue()


def trim_silence(samples, sample_rate: int):
    import numpy as np

    loud = np.flatnonzero(np.abs(samples) > _QUIET)
    if not loud.size:
        return samples
    start = max(0, loud[0] - int(_KEEP_BEFORE * sample_rate))
    return samples[start : loud[-1] + 1 + int(_KEEP_AFTER * sample_rate)]


def synthesize(text: str) -> bytes:
    from paradee import SAMPLE_RATE

    samples = _paradee()(
        text, speed=config.number("TTS_SPEED", 1.0), voice=config.text("TTS_VOICE", "af_heart")
    )
    return _wav(trim_silence(samples, SAMPLE_RATE), SAMPLE_RATE)


_PLACEHOLDER = re.compile(r"\s*\[[^\]]*\]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def spoken(text: str) -> str:
    """What the tutor says for a reply: block names without their backticks and [slots]."""
    return " ".join(_PLACEHOLDER.sub("", text).replace("`", "").split())


def chunks(text: str) -> list[str]:
    """The reply as the tutor says it, a sentence per clip."""
    return [sentence for sentence in _SENTENCE_END.split(spoken(text)) if sentence]


# ponytail: one in-process cache of clip jobs keyed by the spoken text, and one worker, since
# Paradee's G2P is not thread-safe and a reply takes about 0.2 s. A pool of Paradee instances,
# and a shared cache, if a full class ever queues up or the API runs several workers.
_JOBS_KEPT = 64
_jobs: OrderedDict[str, Future] = OrderedDict()
_jobs_lock = threading.Lock()
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts")


def _job(text: str) -> Future:
    with _jobs_lock:
        job = _jobs.get(text)
        if job is None or (job.done() and job.exception() is not None):
            job = _worker.submit(synthesize, text)
            _jobs[text] = job
        _jobs.move_to_end(text)
        while len(_jobs) > _JOBS_KEPT:
            _jobs.popitem(last=False)
        return job


def prepare(texts: list[str]) -> None:
    """Start making the clips now, so they are ready when the avatar asks."""
    for text in texts:
        _job(text)


def audio(text: str) -> bytes:
    """The WAV clip for one spoken line: cached, joining a job already running, or made now."""
    return _job(text).result()


def forget_clips() -> None:
    with _jobs_lock:
        _jobs.clear()


def warm() -> None:
    """Load the model and make one reply-length clip, so ONNX Runtime's first-run cost does not
    land on the first student."""
    synthesize(
        "Nice work getting the robot to the crater. Which block could lower the arm so it can "
        "scoop up the sample before driving back to the lab?"
    )


def transcribe(filename: str, recording: bytes) -> str:
    """The text of a recording. One try: a student waiting on a spoken question is better told
    to try again than kept waiting through the client's retries."""
    result = (
        llm.client()
        .with_options(max_retries=0)
        .audio.transcriptions.create(
            model=config.text("TRANSCRIBE_MODEL"), file=(filename, recording)
        )
    )
    return (result.text or "").strip()
