# The INVITE Agent inside an ATLAS study: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A researcher ticks "With the INVITE Agent" on an ATLAS student, and that student's ZANY steps open inside the agent page.

**Architecture:** ATLAS's `/study` frames `agent.inviteai.org/study#ticket=...` for a ticked, collecting student. The ticket is HMAC-signed with a shared secret. The agent's new `zany-study` environment trusts only the ticket, frames `zany.inviteai.org/play/?session=...` and reads that student's rows from ATLAS's `log_record`.

**Tech Stack:** Frappe v16 (atlas-invite), FastAPI with psycopg 3 and React 19 (agent), nginx (infra).

**Spec:** `docs/superpowers/specs/2026-11-26-atlas-study-agent-design.md`

## Global Constraints

- Ticket: `base64url(JSON payload, no padding) + "." + hex(HMAC-SHA256(secret, that base64 text))`.
- Ticket payload: `{"study": "STUDY-0001", "code": "DEMO", "participant": "T01", "session": "STU-SESS-0001", "exp": <unix seconds>}`, with exp set 12 hours out.
- The secret is `agent_study_secret` in ATLAS's site config and `AGENT_STUDY_SECRET` in the agent's env. It is never committed.
- The agent frame URL is `https://agent.inviteai.org/study#ticket=<ticket>`. The ZANY frame URL is `https://zany.inviteai.org/play/?session=<session>`.
- The study student key is the same as zany's: `f"{fold(code)}:{fold(participant)}"`, under the environment id `zany-study`.
- The ticket travels in the `X-Study-Ticket` header, or as `?ticket=` on the event stream only.
- ATLAS's `zany_forgotten` payload gains a `"code"` field (the study code). The existing fields stay.

## Review Focus

- An expired or tampered ticket gets a 403 on every `/v1/zany-study` call, including the stream. This is tested in agent Task 1.
- A path student ID that differs from the ticket's gets a 403. Agent Task 1.
- A ticked student who has not consented, or whose study is paused, gets the plain `/play/` frame. ATLAS Task 1.
- `zany-study` never shows in the sign-in form's environment list. Agent Task 1.
- "I'm finished" still waits for `zany:logs-sent` from the nested ZANY frame. Checked by hand in Task 4's browser run.

---

### Task 1 (agent): the zany-study environment and the ticket

**Files:** create `server/agent/study.py` and `server/tests/test_study.py`. Modify `server/agent/environments/__init__.py`, `server/agent/environments/zany.py`, `server/agent/api.py` and `server/agent/gate.py`.

**Interfaces:**
- `study.Ticket(study: str, code: str, participant: str, session: str, exp: int)`
- `study.sign(payload: dict, secret: str) -> str`
- `study.read(ticket: str | None) -> Ticket | None` (None when missing, bad or expired)
- `study.ticket_from(request) -> str | None` (the header, else the `ticket` query parameter)
- `Environment.study: bool = False`. `list_environments` leaves out study environments.
- `zany.STUDY_ENVIRONMENT` has id `zany-study` and name `ZANY`. Its frame returns None. Its sync reads `log_record` by `record->>'classCode'` and `record->>'studentID'`, under cursor source `atlas-study`. Its watch listens on `zany_forgotten` (payload `code` and `participant`) and reconciles hourly against `log_record`.
- `Student.ticket: Ticket | None`. For a study environment, `student()` requires `read(ticket_from(request))`, a matching path ID and class code (folded), or it returns 403. `sign_in` returns `f"https://zany.inviteai.org/play/?session={ticket.session}"` as the frame.
- `TurnstileGate` passes a request with a valid ticket. The budget key is the cookie, else the ticket.

- [ ] Write tests: a signed ticket round-trips, and an expired, tampered or garbage ticket reads as None. For the API, sign-in with a ticket returns the `/play/` frame and logs rows read from a stand-in `log_record`. A request without a ticket, with a wrong path ID or with an expired ticket gets 403. `/v1/environments` has no `zany-study`. A `zany_forgotten` notice deletes the student. The gate passes `/v1/environments` with a ticket and no cookie.
- [ ] Run them and see them fail.
- [ ] Implement.
- [ ] Run `pytest -q` and ruff until both pass.

### Task 2 (agent): the client at /study

**Files:** modify `client/src/api.js`, `client/src/App.jsx` and `client/src/App.test.jsx`.

**Interfaces:**
- `api.js` gets `studyTicket(hash = location.hash) -> {ticket, environment: "zany-study", studentId, classCode} | null`. It decodes the payload without checking it, because the server checks it. It also gets `useTicket(ticket)`, after which every request sends `X-Study-Ticket` and the stream adds `?ticket=`.
- At `/study` with a ticket, App signs that student in at once, with no sign-in form and no Sign out button. With no ticket it shows "Open this from your study page."

- [ ] Write tests: at `/study#ticket=...` App sends the header and frames the returned `/play/` URL. Sign out is absent. With no ticket the notice shows.
- [ ] Run them and see them fail. Implement. Run vitest and prettier until both pass.
- [ ] Relay the log flush: none is needed, because ATLAS posts to the nested frame (ATLAS Task 1). Make sure the ZANY iframe comes before the avatar iframe in the DOM.
- [ ] Open the agent PR, with the spec and this plan.

### Task 3 (atlas-invite): with_agent and the agent frame

**Files:** modify `research_participant.json`, `atlas/participant.py` (add `agent_frame(participant, study, session)`), `atlas/www/study.py`, `atlas/www/study.html`, `atlas/templates/zany_base.html`, `atlas/research.py`, the researcher pages, `atlas/zany_logs.py` (payload `code` and an index on `log_record ((record->>'classCode'), (record->>'studentID'))`) and the docs (data model, participant flow, running a study). Add tests in `atlas/tests`.

- [ ] Write tests: `with_agent` plus collecting frames the agent URL with a ticket that verifies under the secret. Unticked, not consented, or no secret configured all frame `/play/`. `add_participants` and `update_participant` set `with_agent`. The forgotten notice carries `code`.
- [ ] Implement. On leaving, `zany_base.html` targets `frame.contentWindow.frames[0]` when the frame has `data-agent`.
- [ ] Run the tests as deploy does, and ruff. Open the PR.

### Task 4 (infra and rollout)

- [ ] Infra PR: in zany.inviteai.org, replace `X-Frame-Options SAMEORIGIN` with `Content-Security-Policy "frame-ancestors 'self' https://agent.inviteai.org"`. Add the `GRANT SELECT ON log_record TO agent_reader` line to the README runbook, and note the secret in the README.
- [ ] On the server: run the grant, add `AGENT_STUDY_SECRET` and `zany-study` to the agent's `.env`, and set `agent_study_secret` with `bench set-config`. Merge infra and run `sudo ./apply`, then merge agent, then merge atlas.
- [ ] End to end on zany.inviteai.org with a demo study: a ticked student sees the agent and "I'm finished" works, and an unticked student sees plain ZANY.
