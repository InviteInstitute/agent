"""The language model: one OpenAI-compatible endpoint (NCSA Lumen in production), the reply
and classifier calls, and the clean-up that keeps a reply short and free of leaked labels."""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import asdict, dataclass

import openai

from agent import config

log = logging.getLogger(__name__)

# A reply is at most two short sentences: the hint is often in the second.
MAX_SENTENCES = 2
MAX_WORDS = 40
# Room above MAX_WORDS for long `block names` in backticks.
REPLY_MAX_TOKENS = 240
# Room a model that cannot stop reasoning gets to think before it answers.
REASONING_BUDGET_TOKENS = 4096
CLASSIFIER_MAX_TOKENS = 8
# The classifier answers in about 0.2 s. Past this it has stalled at the gateway, and the reply
# goes ahead with the general question type rather than keep the student waiting.
CLASSIFIER_TIMEOUT_S = 6.0
# A call slower than this is logged, so a stall at the gateway shows in the logs.
SLOW_CALL_S = 3.0

# The chat models researchers can pick from. Lumen also serves aliases and non-chat models.
RESEARCH_MODELS = frozenset(
    {
        "deepseek-v4-flash",
        "gemma-4-31b-it",
        "glm-5.3-flash",
        "muse-glimmer-30b",
        "nemotron-3-super-120b-a12b",
        "ornith-1.0-35b",
        "qwen3-coder-next",
        "qwen3.6-35b-a3b",
        "qwen3.8-27b",
    }
)


@dataclass(frozen=True)
class Settings:
    """What a researcher can change on the research page. All defaults is what students get."""

    model: str | None = None
    prompt_template: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    trim_reply: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


PRODUCTION = Settings()


class EmptyAnswer(RuntimeError):
    """The model used its whole budget without an answer. The tokens still count."""

    def __init__(self, message: str, tokens: int):
        super().__init__(message)
        self.tokens = tokens


_client: openai.OpenAI | None = None
_client_lock = threading.Lock()
# Models that answered only once they were given room to reason, so they get it first.
_reasoning_models: set[str] = set()


def client() -> openai.OpenAI:
    """One client for the process, so calls reuse a warm connection."""
    global _client
    with _client_lock:
        if _client is None:
            _client = openai.OpenAI(
                api_key=config.text("OPENAI_API_KEY"),
                base_url=config.text("OPENAI_BASE_URL"),
                timeout=config.number("LLM_TIMEOUT_S", 30.0),
            )
        return _client


def reset() -> None:
    """Forget the client and what was learned about models (for tests)."""
    global _client
    with _client_lock:
        _client = None
    _reasoning_models.clear()


def available_models() -> list[str]:
    """The research models the endpoint serves right now."""
    return sorted(m.id for m in client().models.list().data if m.id in RESEARCH_MODELS)


_THINK_BLOCK = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL)
_THINK_OPEN = re.compile(r"^\s*<think>.*", re.DOTALL)


def strip_thinking(text: str) -> str:
    """Drop reasoning at the start of an answer: a whole <think> block, one the token limit cut
    off, or (when the chat template opened the tag itself) everything up to </think>."""
    text = _THINK_OPEN.sub("", _THINK_BLOCK.sub("", text, count=1), count=1)
    return text.rsplit("</think>", 1)[1] if "</think>" in text else text


def _ask(
    model: str,
    prompt: str,
    max_tokens: int | None,
    temperature: float | None,
    reasoning: bool,
    timeout: float | None = None,
) -> tuple[str, str, int]:
    """One completion: (answer, finish_reason, tokens spent). Without `reasoning`, Qwen's
    thinking is turned off. With it, the model gets a low effort and extra room to reason."""
    kwargs: dict = {}
    budget = max_tokens
    if reasoning:
        kwargs["reasoning_effort"] = "low"
        budget = (max_tokens or REPLY_MAX_TOKENS) + REASONING_BUDGET_TOKENS
    else:
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    if budget is not None:
        kwargs["max_tokens"] = budget
    if temperature is not None:
        kwargs["temperature"] = temperature
    # A call with its own time limit gets one try, since a retry would outlast the limit.
    api = client().with_options(timeout=timeout, max_retries=0) if timeout else client()
    started = time.monotonic()
    response = api.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}], **kwargs
    )
    took = time.monotonic() - started
    if took > SLOW_CALL_S:
        log.warning("%s took %.1f s to answer", model, took)
    choice = response.choices[0]
    content = choice.message.content or ""
    usage = getattr(response, "usage", None)
    tokens = getattr(usage, "total_tokens", None) or (len(prompt) + len(content)) // 4
    return strip_thinking(content).strip(), choice.finish_reason or "stop", tokens


def complete(
    model: str,
    prompt: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float | None = None,
    spent: list[int],
) -> str:
    """An answer from `model`, with the tokens each call spent appended to `spent`.

    A short reply never needs its whole budget, so an empty answer or a cut-off one means the
    model spent it reasoning. It is asked again with room to reason, and remembered."""
    reasoning = model in _reasoning_models
    answer, finish, tokens = _ask(model, prompt, max_tokens, temperature, reasoning, timeout)
    spent.append(tokens)
    if (not answer or finish == "length") and not reasoning:
        log.info("%s gave no usable answer (%s), asking again with room to reason", model, finish)
        answer, finish, tokens = _ask(model, prompt, max_tokens, temperature, True, timeout)
        spent.append(tokens)
        if answer:
            _reasoning_models.add(model)
    if not answer:
        raise EmptyAnswer(f"{model} returned no answer (finish_reason={finish})", sum(spent))
    return answer


# --- keeping a reply clean and bite-sized ---

_LABEL = re.compile(r"^\s*[A-Z][A-Za-z]+(?:\s+[A-Za-z]+)?:\s*")
_VOCATIVE = re.compile(r"^\s*(?:hi\s+student|hey\s+student|student)\s*[,:]\s*", re.IGNORECASE)
_QUOTES = "\"'`"
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_BREAK = re.compile(r"(?:,|;|:|\s[\u2014\u2013-])\s")
MIN_CLAUSE_WORDS = 6


def sanitize(text: str) -> str:
    """Remove what small models leak around a reply: reasoning, wrapping quotes, a leading
    "Label:" and a leading "Student,". Only those, never real content."""
    cleaned = strip_thinking((text or "").strip()).strip()
    if len(cleaned) >= 2 and cleaned[0] in _QUOTES and cleaned[-1] == cleaned[0]:
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.strip(_QUOTES).strip()
    cleaned = _VOCATIVE.sub("", _LABEL.sub("", cleaned, count=1), count=1)
    cleaned = cleaned.strip(_QUOTES).strip()
    return cleaned[:1].upper() + cleaned[1:]


def _end(text: str) -> str:
    text = text.rstrip(" ,;:\u2014\u2013-")
    return text if not text or text[-1] in ".!?" else f"{text}."


def trim(text: str) -> str:
    """The first sentence, and the second when both fit MAX_WORDS. A first sentence over
    MAX_WORDS ends early at its last clause break that leaves a real sentence."""
    sentences = [s for s in _SENTENCE_END.split(" ".join((text or "").split())) if s]
    if not sentences:
        return ""
    first = sentences[0]
    if len(first.split()) > MAX_WORDS:
        head = " ".join(first.split()[:MAX_WORDS])
        breaks = [
            m.start()
            for m in _CLAUSE_BREAK.finditer(head)
            if len(head[: m.start()].split()) >= MIN_CLAUSE_WORDS
        ]
        return _end(head[: breaks[-1]] if breaks else head)
    kept, words = [first], len(first.split())
    for sentence in sentences[1:MAX_SENTENCES]:
        words += len(sentence.split())
        if words > MAX_WORDS:
            break
        kept.append(sentence)
    return _end(" ".join(kept))
