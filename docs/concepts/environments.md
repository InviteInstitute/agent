# Environments

An environment is a coding space the agent works in. Each is a module in
`server/agent/environments/` that says four things.

- What the agent page frames for a student.
- How a student is keyed.
- Where the student's learner logs come from.
- Which playgrounds the agent knows, with each one's task, blocks, milestones and how progress is
  scored.

Everything else, the measurements, the pedagogy and the chat, is shared, because every
environment logs in VEXcode VR's format. A site serves the environments its `ENVIRONMENTS`
setting names.

| Id | Name | Key | Playgrounds |
| --- | --- | --- | --- |
| `vexcode-vr` | VEXcode VR | the student ID, case folded | GO-Mars |
| `zany` | ZANY | class code and student ID, both case folded | Castle Crasher+, Coral Reef Cleanup, Art Canvas |
| `zany-study` | ZANY | study code and participant ID, both case folded | the same as `zany` |

ZANY joins the class code and the student ID, because two classes can each have an S01. The API
takes the student ID in the path and the class code as a query parameter, and the server makes the
key, so the page never handles keys.

## VEXcode VR

The page frames `https://research-vr.vex.com/`. VEXcode VR sends its logs to the Invite Institute
Hub, and the agent reads them there with a token, or with a login that gets one.

VEXcode VR's links have no way to name the student. So the student signs in to VEXcode VR inside
the frame, and types the same student ID into the agent.

## ZANY

The page frames `https://vr.inviteai.org/?class=…&student=…` with the IDs the student signed in
to the agent with. So ZANY and the agent always agree on who the student is. Until the student
signs in there is nothing to frame, since ZANY keeps no logs without IDs.

ZANY sends those logs to ATLAS-invite, which keeps them as link records (`link_record` in its log
store). The agent reads them with the read-only login in `ZANY_LOG_DSN`.

A researcher can delete a student's link records in ATLAS. ATLAS then sends `zany_link_forgotten`,
and the agent deletes its own copy of that student, which means the events, the chat and the
settings. An hourly check catches a deletion the agent missed while it was down.

## ZANY In An ATLAS Study

`zany-study` is ZANY for a student a researcher gave the agent in an ATLAS study. It never shows
in the sign-in form. [ZANY In An ATLAS Study](atlas-study.md) has the whole flow.

## Reading The Logs

Each source is read two ways.

- One student's newest logs, right before a reply, so it sees the run they just made.
- Everyone's new logs, from a saved cursor, on each pass of the check-in daemon.

A fresh database's first read reaches back `STUDENT_RECENCY_HOURS` (24 by default). A record read
twice is kept once.

## Adding An Environment

1. Add a module in `server/agent/environments/` that builds an `Environment`, with its playgrounds.
2. Add it to `all_environments()` in `server/agent/environments/__init__.py`.
3. Add tests in `server/tests/` with real log records as fixtures.
4. Add its id to `ENVIRONMENTS` on the site that should serve it.
