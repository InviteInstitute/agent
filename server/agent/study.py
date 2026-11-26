"""Students in an ATLAS-invite study. ATLAS frames the agent page for a student a researcher
gave the agent, with a ticket in the link that says who they are. The ticket is signed with a
secret only ATLAS and the agent hold (AGENT_STUDY_SECRET), so a study student is never taken
from what a browser types, and a ticket lasts 12 hours.

A ticket is base64url(JSON) + "." + hex(HMAC-SHA256(secret, that base64 text)), with the
payload {"study", "code", "participant", "session", "exp"}.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from agent import config

HEADER = "X-Study-Ticket"
PLAY_URL = "https://zany.inviteai.org/play/"


@dataclass(frozen=True)
class Ticket:
    study: str  # ATLAS's study record, STUDY-0001
    code: str  # the study code the student signed in with, which ZANY logs as the class code
    participant: str  # the participant ID, which ZANY logs as the student ID
    session: str  # the study session ZANY is open in
    exp: int

    @property
    def frame(self) -> str:
        return f"{PLAY_URL}?session={self.session}"


def _mac(secret: str, body: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def sign(payload: dict, secret: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{body}.{_mac(secret, body)}"


def read(ticket: str | None) -> Ticket | None:
    """The ticket's student, or None when it is missing, forged, malformed or expired."""
    secret = config.text("AGENT_STUDY_SECRET")
    if not secret or not ticket or ticket.count(".") != 1:
        return None
    body, mac = ticket.split(".")
    if not hmac.compare_digest(mac, _mac(secret, body)):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        found = Ticket(
            study=str(data["study"]),
            code=str(data["code"]),
            participant=str(data["participant"]),
            session=str(data["session"]),
            exp=int(data["exp"]),
        )
    except (ValueError, KeyError, TypeError):
        return None
    return found if found.exp > time.time() else None


def ticket_from(request) -> str | None:
    """The ticket a request carries: in its header, or in the link on the check-in stream,
    where a browser cannot set headers."""
    return request.headers.get(HEADER) or request.query_params.get("ticket")
