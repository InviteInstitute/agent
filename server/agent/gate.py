"""What keeps the API from being a free LLM: a Cloudflare Turnstile check before any /v1 call,
and a token budget per browser session plus a daily ceiling for the whole site.

The agent has no login. A browser solves the Turnstile widget once, the server checks the
answer with Cloudflare and remembers it in a signed cookie for 12 hours. That cookie is also
the browser session the token budget counts against, so a new budget means a new challenge.
"""

import hashlib
import logging

import httpx
from itsdangerous import BadSignature, TimestampSigner
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from agent import config, db, study

log = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
COOKIE = "ts_verified"
COOKIE_MAX_AGE = 12 * 3600
VERIFY_PATH = "/v1/turnstile/verify/"


def gate_on() -> bool:
    """The gate is on unless TURNSTILE=off, which only local development sets."""
    return config.text("TURNSTILE", "on").lower() != "off"


def _signer() -> TimestampSigner:
    secret = config.text("SESSION_SECRET")
    if not secret and gate_on():
        raise RuntimeError("SESSION_SECRET is not set")
    return TimestampSigner(secret or "dev-only-session-secret")


async def verify(token: str, remote_ip: str) -> bool:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            SITEVERIFY_URL,
            data={
                "secret": config.text("TURNSTILE_SECRET"),
                "response": token,
                "remoteip": remote_ip,
            },
        )
    return response.status_code == 200 and response.json().get("success") is True


def new_cookie() -> str:
    return _signer().sign(b"ok").decode()


def cookie_valid(value: str | None) -> bool:
    if not value:
        return False
    try:
        _signer().unsign(value, max_age=COOKIE_MAX_AGE)
        return True
    except BadSignature:  # also covers an expired signature
        return False


class TurnstileGate(BaseHTTPMiddleware):
    """403 {"error": "turnstile_required"} on /v1 without a valid cookie. The client shows the
    challenge when it sees that. The verify route and everything outside /v1 stay open, and so
    does a request with a valid ATLAS study ticket, since ATLAS signed that student in."""

    async def dispatch(self, request, call_next):
        path = request.url.path
        if gate_on() and path.startswith("/v1/") and path != VERIFY_PATH:
            if not cookie_valid(request.cookies.get(COOKIE)) and not study.read(
                study.ticket_from(request)
            ):
                return JSONResponse({"error": "turnstile_required"}, status_code=403)
        return await call_next(request)


# --- token budgets ---


class OutOfTokens(Exception):
    pass


def budget_key(cookie: str | None) -> str:
    """A browser session's id for its budget: a hash, so the cookie is never stored."""
    return hashlib.sha256((cookie or "no-session").encode()).hexdigest()[:32]


def request_budget_key(request) -> str:
    """The budget a request spends from: its browser session's, or for a study student, their
    ticket's, which lasts as long as a session does."""
    return budget_key(request.cookies.get(COOKIE) or study.ticket_from(request))


def session_limit() -> int:
    return int(config.number("LLM_SESSION_TOKEN_LIMIT", 150_000))


def daily_limit() -> int:
    return int(config.number("LLM_DAILY_TOKEN_LIMIT", 3_000_000))


def usage(key: str) -> dict:
    return {"used": db.tokens_for_budget_key(key), "limit": session_limit()}


def check(key: str) -> None:
    """Refuse when this browser session or the whole site is out of tokens. A call already
    running may go a little past a limit, the next one is refused."""
    if db.tokens_for_budget_key(key) >= session_limit():
        raise OutOfTokens(
            f"This session has used its {session_limit():,} LLM tokens. "
            "Start a new session later to keep going."
        )
    if db.tokens_last_day() >= daily_limit():
        raise OutOfTokens("The agent has reached today's usage limit. Try again tomorrow.")
