# Design

This repository replaces vex-chat-agent and vex-pedagogical-agent. Those two were one codebase
that forked in September 2026. After that every fix had to land twice, and the fork changed
how the tutor teaches as well as adding the avatar. This one keeps their features, is
written fresh, and adds ZANY as a second environment.

## What carries over

- Grounded replies to a question or the Help button.
- Proactive check-ins when a behavior trigger fires (wheel-spinning, resilience, explorer,
  iterative, inactive).
- The study's question types and their scaffolding, the feedback-class flowchart and the prompt.
- The research page. A researcher picks a model, edits the prompt and the sampling, and those
  replies stay in a research chat apart from what students see.
- Ratings and notes on replies.
- The Turnstile gate and the token budgets per browser session and per day.
- The 3D tutor with spoken replies and spoken questions. It shows wherever its Unity build is
  installed, and a student can hide it, which pauses it.

## What changed

- Each environment is a module in `server/agent/environments/`. It says what the page frames,
  how a student is keyed, where the logs come from and which playgrounds the agent knows (task,
  blocks, milestones and how progress is scored). A playground with nothing to score, like
  ZANY's Art Canvas, skips the progress rules.
- The chat lives in Postgres. The old server kept the recent turns in memory, so a restart made
  the tutor forget the conversation. Now the recent chat is read from `messages`, and a reload
  of the page shows the chat again.
- Each reply keeps the situation, prompt, model, settings and tokens that produced it. That
  replaces the old snapshots table, which kept one row per session.
- The client posts a question to `/turns` and gets the reply back in the same call. The old
  client made two calls, one to store the message and one for the reply.
- The schema is fresh. Its migrations run when the API starts and are tracked in
  `schema_migrations`.
- The Unity form bridge is gone. The web avatar only ever fetched speech, so `/tts` moves behind
  the gate and the open `/generate-feedback-*` routes are not carried over.
- Identity switch tracking is gone, since nothing ever read `switch_events`. Students are
  matched on a key with case and spaces folded, which covers the casing changes it recorded.
- The client uses Carbon, like lm-dashboard and ATLAS.

## How a student is addressed

A student is `(environment, student_key)`. VEXcode VR folds the student ID's case. ZANY joins
the class code and the student ID, because its links name both and two classes can each have
an S01. The API takes the student ID in the path and the class code as a query parameter, and
the server makes the key, so the client never handles keys.

## ZANY

The agent page frames `vr.inviteai.org/?class=…&student=…` with the IDs the student signed in
with, so the agent and ZANY always agree on who the student is. ZANY sends those logs to
ATLAS-invite as link records (`link_record` in its log store), and the agent reads them there
the way lm-dashboard reads study records. `zany.inviteai.org`, the ATLAS study version, refuses
to be framed (`X-Frame-Options: SAMEORIGIN`), so studies are left for later.

## Slices

All six are done, and the agent serves agent.inviteai.org, where vex-pedagogical-agent was.

1. The server core, the schema, the pipeline and VEXcode VR, with tests and CI.
2. ZANY. It needs a read-only role on ATLAS's log store.
3. The Carbon client, with the frame and the chat on top.
4. Proactive check-ins and the live stream.
5. The avatar, speech and spoken questions.
6. Deploying it: the stack, nginx, the webhook and a domain, through infra.
