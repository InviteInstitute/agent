# INVITE Agent

A tutor for middle school students who code robots in block-based environments. The agent page
frames the student's coding environment and floats a chat on top of it. When a student asks for
help, or looks stuck, the agent reads what the student's code and robot are actually doing and
gives one short, specific hint.

It works in three environments, and each site picks which ones it serves.

| Environment | What the page frames | Where the student's logs come from |
| --- | --- | --- |
| VEXcode VR | `research-vr.vex.com` | the Invite Institute Hub |
| ZANY | `vr.inviteai.org`, with the student's class and ID in the link | ATLAS-invite's log store |
| ZANY in an ATLAS study | `zany.inviteai.org/play/` for the student's study session | ATLAS-invite's log store |

All of them log in VEXcode VR's format, so the measurements, the pedagogy and the chat are the
same in each. Only the log source differs.

In an ATLAS study, a researcher ticks "With the INVITE Agent" on a student, and ATLAS frames
`agent.inviteai.org/study` for that student with a signed ticket in the link. Nobody signs in
there. The ticket says who the student is and which session to frame.

## How a reply is made

1. The server reads the student's newest logs from their environment's source.
2. It measures the current playground stretch of the session. That means progress toward the
   goal, the work pattern (trial and error, snap and test, stalled), persistence and the last
   error the robot reported.
3. The study's flowchart turns those into feedback classes like Error Flagging or Reassure.
4. A small classifier call sorts the question into one of four question types, each with its
   own scaffolding.
5. One reply call gets the student's actual program, the measured facts, the recent chat, the
   scaffolding and the feedback classes, and writes at most two short sentences.

Every reply is kept with the situation, prompt, model and settings that produced it, so research
can always see why the agent said what it said!

Students see only the chat. The research view, where a researcher picks a model and edits the
prompt, is at `/research` (agent.inviteai.org/research). Its replies go to a research chat, apart
from what students see.

## Run it locally

You need Docker, [uv](https://docs.astral.sh/uv/) and an LLM. Any OpenAI-compatible endpoint
works, a local [Ollama](https://ollama.com) included.

```bash
git clone --recurse-submodules https://github.com/InviteInstitute/agent
cd agent
cp .env.example .env        # set POSTGRES_PASSWORD and the LLM
make install                # the server, in server/.venv
make dev                    # Postgres, the API on :8005 and the client on :5173
```

Load a sample session and ask about it:

```bash
cd server
DATABASE_URL=postgresql://agent:$POSTGRES_PASSWORD@127.0.0.1:5435/agent \
  .venv/bin/python -m agent load vexcode-vr tests/fixtures/vexcode_vr/01_error_flagging_a.ndjson
curl -s -X POST localhost:8005/v1/vexcode-vr/students/fixture_01_1/turns \
  -H 'content-type: application/json' -d '{"message": "why does my robot not move?"}'
```

`make test` runs the tests, `make lint` checks the code. The design and what is still to come
are in [docs/design.md](docs/design.md).

## On the INVITE server

The site deploys from `main`. A push makes GitHub call the webhook, which runs
`/usr/local/bin/agent-deploy.sh` (in InviteInstitute/infra), and that runs `scripts/deploy.sh`
here as `ubuntu`. It pulls, rolls Postgres and the API with `docker compose -f compose.yml`, checks
`/healthz`, then builds the client and swaps it in whole. nginx serves `client/dist` and
`avatar/`, and passes `/v1` to the API on 127.0.0.1:8005.

The checkout's `.env` holds the site's settings and secrets. The Lumen key comes from
`/etc/lumen.env` and ZANY's read-only login from `/etc/agent/zany.env`. `AGENT_STUDY_SECRET` in
`.env` checks ATLAS's study tickets, and ATLAS holds the same secret as `agent_study_secret`. The Unity build of the
tutor is installed by hand with `avatar/install.sh` and is kept across deploys.

## Layout

| Path | What is there |
| --- | --- |
| `server/agent/environments/` | one module per environment, with its frame, its log source and its playgrounds |
| `server/agent/situation.py` | the measurements, and the facts in words for the prompt |
| `server/agent/pedagogy.py` | feedback classes, question types and the prompt |
| `server/agent/feedback.py` | the one pipeline that questions and check-ins share |
| `server/agent/api.py` | the `/v1` routes |
| `server/vendor/agent-lm-packages` | the shared learner-model engine (a submodule) |
| `client/` | the page, in React, dressed like ZANY and VEXcode VR |
| `avatar/` | the 3D tutor's page, and where its Unity build is installed |

## License

AGPL-3.0, like the repositories this one replaces.
