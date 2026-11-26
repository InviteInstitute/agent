"""VEXcode VR: the agent frames VEX's research build, and reads the students' logs from the
Invite Institute Hub, where VEXcode VR sends them."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta

import httpx

from agent import config, db
from agent.environments import Environment, Milestone, Playground, fold
from agent.events import parse_records, parse_time

log = logging.getLogger(__name__)

SOURCE = "invite-hub"
PAGE = 500
# The cursor is rewound this much, so a record landing on its boundary is read again rather
# than missed. Reading a record twice keeps it once.
OVERLAP = timedelta(seconds=2)


def _number(parameters: dict, name: str) -> float:
    value = parameters.get(name)
    return float(value) if isinstance(value, (int, float)) else 0.0


GO_MARS_MILESTONES = (
    Milestone(
        "move a sample out of the crater", lambda p: _number(p, "removed_samples_crater") > 0
    ),
    Milestone(
        "place a sample on the lab",
        lambda p: _number(p, "samples_moved_lab") > 0 or _number(p, "samples_moved_lab_top") > 0,
    ),
    Milestone("tilt the solar panel", lambda p: p.get("tilted_solarPanel") is True),
    Milestone("rescue the rover", lambda p: p.get("rover_rescued") is True),
    Milestone("lift the rocket ship upright", lambda p: p.get("lifted_rocketShip_upright") is True),
    Milestone(
        "remove fuel cells from the cradles",
        lambda p: _number(p, "removed_fuel_cells_craters") > 0,
    ),
)
GO_MARS_GOAL = 5.0


def go_mars_progress(parameters: dict) -> float:
    """The score toward the first goal of 5 points: VEX's own total when it logs one, else one
    point per milestone reached."""
    score = parameters.get("total_score")
    points = (
        float(score)
        if isinstance(score, (int, float))
        else sum(m.done(parameters) for m in GO_MARS_MILESTONES)
    )
    return round(min(points, GO_MARS_GOAL) / GO_MARS_GOAL * 100, 2)


GO_MARS = Playground(
    name="GO-Mars",
    task=(
        "The student is working in VEXcode VR in the GO Competition playground called Mars "
        "Math Expedition. In Stage 4, all tasks are available, each completed task is worth 1 "
        "point, and the student should first aim to score at least 5 points and then keep "
        "scoring more if possible within the one-minute match. The robot can drive forward and "
        "backward, turn, raise and lower its arm, and use an eye sensor to detect objects and "
        "object colors. Relevant blocks include Drive for, Turn for, Spin arm motor, Spin arm "
        "motor to position, and Wait until with the eye sensor. Common tasks include removing a "
        "sample from a crater, moving a sample to the Lab, placing a sample on top of the Lab, "
        "tilting the Solar Panel down, clearing the Landing Site, lifting the Rocket Ship "
        "upright, removing Fuel Cells from their cradles, and moving Fuel Cells to the Rocket "
        "Ship or Landing Site."
    ),
    blocks=(
        "drive [forward/reverse]",
        "drive [forward/reverse] until [object/crash]",
        "drive [forward/reverse] for [number] [mm/inches]",
        "turn [right/left]",
        "turn [right/left] for [number] degrees",
        "turn to heading [number] degrees",
        "turn to rotation [number] degrees",
        "stop driving",
        "set drive velocity to [number] [%]",
        "set turn velocity to [number] [%]",
        "set drive heading to [number] degrees",
        "set drive rotation to [number] degrees",
        "set drive timeout to [number] seconds",
        "drive is done?",
        "drive is moving?",
        "drive heading in degrees",
        "drive rotation in degrees",
        "drive velocity in [%]",
        "spin [ArmMotor] [up/down]",
        "spin [ArmMotor] [up/down] for [number] [degrees/turns]",
        "spin [ArmMotor] to position [number] [degrees/turns]",
        "stop [ArmMotor]",
        "set [ArmMotor] velocity to [number] [%]",
        "set [ArmMotor] timeout to [number] seconds",
        "[ArmMotor] position in [degrees/turns]",
        "set [ArmMotor] position to [number] [degrees/turns]",
        "[ArmMotor] is done?",
        "[ArmMotor] is spinning?",
        "[ArmMotor] velocity in [%]",
        "[FrontEye] found an object?",
        "[FrontEye] detects [red/green/blue/orange/purple]?",
        "[FrontEye] brightness in %",
        "[FrontEye] hue in degrees",
        "detected crash?",
        "print [text/value]",
        "set cursor to next row",
        "clear all rows",
        "set print precision to [1/0.1/0.01/0.001/All Digits]",
        "wait [number] seconds",
        "wait until [condition]",
        "repeat [number]",
        "forever",
        "repeat until [condition]",
        "while [condition]",
        "if [condition] then",
        "if [condition] then else",
        "if [condition] then / else if [condition] then / else",
        "break",
        "stop project",
        "reset timer",
        "timer in seconds",
        "when timer > [number] seconds",
        "when started",
        "when I receive [my_event]",
        "broadcast [my_event]",
        "broadcast [my_event] and wait",
        "[a] [+] [b]",
        "[a] [=] [b]",
        "[condition] [and] [condition]",
        "not [condition]",
        "[a] [<] [b] [<] [c]",
        "pick random [a] to [b]",
        "round [number] to [number] decimal places",
        "[abs] of [number]",
        "atan2 of x: [number] y: [number]",
        "remainder of [a] / [b]",
        "join [text] [text]",
        "letter [number] of [text]",
        "length of [text]",
        "[text] contains [text]?",
        "convert [value] to [text]",
        "[myVariable]",
        "set [myVariable] to [number]",
        "change [myVariable] by [number]",
        "comment",
    ),
    log_name="GOMars",
    aliases=("go_mars",),
    milestones=GO_MARS_MILESTONES,
    progress=go_mars_progress,
)


# --- the Invite Institute Hub ---

_token: str | None = None
_token_lock = threading.Lock()


def _base_url() -> str:
    return config.text("INVITE_HUB_BASE_URL", "https://inviteinstitutehub.org").rstrip("/")


def _auth_token(client: httpx.Client, fresh: bool = False) -> str:
    """INVITE_HUB_TOKEN, or a token for INVITE_HUB_USERNAME and INVITE_HUB_PASSWORD. The Hub's
    tokens do not expire, so one is kept for the life of the process."""
    global _token
    if token := config.text("INVITE_HUB_TOKEN"):
        return token
    with _token_lock:
        if _token is None or fresh:
            username, password = (
                config.text("INVITE_HUB_USERNAME"),
                config.text("INVITE_HUB_PASSWORD"),
            )
            if not username or not password:
                raise RuntimeError(
                    "Set INVITE_HUB_TOKEN, or INVITE_HUB_USERNAME and INVITE_HUB_PASSWORD"
                )
            response = client.post(
                f"{_base_url()}/api/token/", json={"username": username, "password": password}
            )
            response.raise_for_status()
            _token = response.json()["token"]
        return _token


def _page(client: httpx.Client, params: dict) -> list[dict]:
    url = f"{_base_url()}/api/rabbitmq/vex_logs/"
    response = client.get(
        url, params=params, headers={"Authorization": f"Token {_auth_token(client)}"}
    )
    if response.status_code in (401, 403) and not config.text("INVITE_HUB_TOKEN"):
        token = _auth_token(client, fresh=True)
        response = client.get(url, params=params, headers={"Authorization": f"Token {token}"})
    response.raise_for_status()
    results = response.json().get("results")
    if not isinstance(results, list):
        raise RuntimeError("The Invite Hub answered without a results list")
    return [record for record in results if isinstance(record, dict)]


def sync(student_id: str | None = None, class_code: str | None = None) -> int:
    """Read new logs from the Hub: everyone's since the cursor (and move it), or one student's
    (and leave it, so other students' unread logs stay unread)."""
    position = db.cursor(SOURCE)
    if position:
        since = parse_time(position["at"]) - OVERLAP
    elif student_id is None:
        # A fresh database starts at the recency window, not years of history.
        since = datetime.now(UTC) - timedelta(hours=config.student_recency_hours())
    else:
        since = None
    params: dict = {"limit": PAGE}
    if since:
        params["dateFrom"] = since.isoformat()
    if student_id:
        params["studentID"] = student_id

    new = 0
    newest: tuple[datetime, int] | None = None
    with httpx.Client(timeout=60) as client:
        offset = 0
        while True:
            records = _page(client, {**params, "offset": offset})
            pairs = [(r, str(r["id"])) for r in records if isinstance(r.get("id"), int)]
            rows, skipped = parse_records(pairs, ENVIRONMENT)
            if skipped:
                log.info("skipped Invite Hub records: %s", skipped)
            new += db.insert_events(rows)
            for record, _ in pairs:
                at = parse_time(record.get("received_at") or record.get("recieved_at"))
                if at and (newest is None or (at, record["id"]) > newest):
                    newest = (at, record["id"])
            if len(records) < PAGE:
                break
            offset += PAGE
    if student_id is None and newest:
        db.save_cursor(SOURCE, *newest)
    return new


ENVIRONMENT = Environment(
    id="vexcode-vr",
    name="VEXcode VR",
    tool="VEXcode VR, a block-based programming tool for middle school students",
    needs_class_code=False,
    playgrounds=(GO_MARS,),
    # VEX's research build, which asks each student for a class code and a student ID. Its
    # ?classcode= link (a class's direct link) signs in without asking for the student ID, so
    # those students' logs carry none and the agent cannot follow them. Tested November 2026.
    frame=lambda student_id, class_code: "https://research-vr.vex.com/",
    student_key=lambda student_id, class_code: fold(student_id),
    sync=sync,
)
