# The INVITE Agent inside an ATLAS study

## Why

Researchers want to run a ZANY study in ATLAS where some students code with the INVITE Agent and
some without, so they can compare the two groups. The researcher decides who gets the agent.

## Goals

- A researcher ticks "With the INVITE Agent" on a student in ATLAS, when adding them or later.
- On a ZANY step, a ticked student who may be collected sees ZANY with the agent's edge tab,
  check-ins and tutor on top, the same way the agent wraps ZANY at agent.inviteai.org today.
- Everyone else sees plain ZANY, exactly as now.
- The agent sees that student's study logs, and its chats, ratings and settings are deleted when
  ATLAS deletes the student's records.

## Non-goals

- Random assignment. The researcher picks.
- A per-study or per-step switch.
- Any change to ZANY itself.
- Showing the agent's chats on ATLAS's researcher pages. They stay in the agent's database and its
  own research tools.

## Anti-goals

- A student without consent getting the agent, or the agent keeping anything about them.
- Anyone reading a study student's chat by guessing their ID.
- Breaking "I'm finished" or "Back", which flush ZANY's logs before leaving.

## Constraints

- ATLAS keeps ZANY's study logs only while `collecting()` is true (study active, consent and
  guardian consent obtained). The agent can only see code that ATLAS keeps.
- ZANY's study logs live in `log_record`, keyed by study and participant record. The agent's
  read-only login (`agent_reader`) can only read `link_record` today.
- zany.inviteai.org sends `X-Frame-Options: SAMEORIGIN`, so agent.inviteai.org cannot frame
  `/play/` yet.
- ZANY only answers the `zany:send-logs` message from its own origin.

## Approaches

- **A. ATLAS frames the agent page (picked).** The study page frames agent.inviteai.org instead of
  `/play/` for a ticked student, and the agent page frames `/play/?session=...` the way it frames
  vr.inviteai.org now. This reuses the agent page whole, and it works just like normal ZANY does.
- B. Build the agent's chat into ATLAS's study page as a widget. This is one less frame, but the
  agent client would have to be rebuilt as an embeddable widget and kept working in two ways.
- C. Send the student to agent.inviteai.org for the ZANY step. The student would leave the study
  page and lose "I'm finished" and "Back".

## Design

### ATLAS (atlas-invite)

1. Research Participant gets a check field `with_agent`, labelled "With the INVITE Agent", off
   by default. The researcher pages set it when adding participants and on a student's page,
   and it shows in the participant list and the export.
2. On a ZANY step, `/study` frames the agent when `with_agent` and `collecting()` are both true:
   `https://agent.inviteai.org/study#ticket=<ticket>`. Otherwise it frames `/play/?session=...`
   as now.
3. The ticket is signed with HMAC-SHA256 under a secret shared with the agent
   (`AGENT_STUDY_SECRET`, a file in /etc on the server, never committed). It carries the study
   record, the study code, the participant ID, the study session and an expiry 12 hours out. It
   rides in the URL fragment, so it never reaches a log.
4. Leaving ZANY, the study page sends `zany:send-logs` to the nested ZANY frame (the agent
   frame's first child frame) instead of the agent frame. ZANY sees a message from its own
   origin and answers as today.

### The agent

1. A new environment, `zany-study`, named ZANY. It frames
   `https://zany.inviteai.org/play/?session=<study session>` from the ticket. The student key is
   `<study record>:<participant ID, folded>`, so a study student never mixes with a link student
   who has the same class code and ID.
2. Every `/v1/zany-study/...` call carries the ticket, in an `X-Study-Ticket` header or as
   `?ticket=` on the check-in stream. The server checks the signature and the expiry and takes
   the student from it, never from the path. A valid ticket also passes the Turnstile gate, and
   the token budget counts against the participant.
3. Its sync reads `log_record` for that participant, with its own cursor (`atlas-study`), the way
   `zany` reads `link_record`.
4. It listens for ATLAS's `zany_forgotten` notice (study, participant ID) and deletes that
   student's events, chats and settings. An hourly check forgets any study student whose
   records are all gone from `log_record`.
5. The page at `/study` reads the ticket from the fragment, signs in with it and skips the
   sign-in form. Everything else (edge tab, check-ins, tutor, guide) is the normal page.

### The server (infra)

1. zany.inviteai.org swaps `X-Frame-Options: SAMEORIGIN` for
   `Content-Security-Policy: frame-ancestors 'self' https://agent.inviteai.org`.
2. `agent_reader` gets `SELECT ON log_record`, in the README's runbook.
3. `AGENT_STUDY_SECRET` goes in `/etc/agent/` and in ATLAS's site config, and both are listed in
   `secrets`. The agent's `ENVIRONMENTS` adds `zany-study`.

## Calls made by the builder

- A session deletion makes the agent forget all of that participant's chats, not only that
  session's, because ATLAS's notice names the participant. This errs on the safe side of a
  deletion request.
- A student who withdraws mid-study gets plain ZANY on the next page load, because
  `collecting()` turns false. What the agent already kept stays until a researcher deletes it,
  the same as ZANY's logs.
- The ticket expires after 12 hours. A student past that reloads `/study` and gets a fresh one.
