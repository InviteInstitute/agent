# INVITE Agent

A tutor for middle school students who code robots in block-based environments. The agent page
frames the student's coding environment and floats a chat on top of it. When a student asks for
help, or looks stuck, the agent reads what the student's code and robot are actually doing and
gives one short, specific hint.

It works in VEXcode VR, in ZANY, and in ZANY inside an ATLAS study, and each site picks which
ones it serves.

The docs are at [docs.inviteai.org/agent](https://docs.inviteai.org/agent/), built from `docs/`.
To run it on your own machine, start with the [Quickstart](docs/quickstart.md).
[Development](docs/guides/development.md) covers the tests and the lint, and
[docs/design.md](docs/design.md) has the design notes.

## On the INVITE server

The site deploys from `main`. A push makes GitHub call the webhook, which runs
`/usr/local/bin/agent-deploy.sh` (in InviteInstitute/infra), and that runs `scripts/deploy.sh`
here as `ubuntu`. It pulls, rolls Postgres and the API with `docker compose -f compose.yml`, checks
`/healthz`, then builds the client and swaps it in whole. nginx serves `client/dist` and
`avatar/`, and passes `/v1` to the API on 127.0.0.1:8005.

The checkout's `.env` holds the site's settings and secrets. The Lumen key comes from
`/etc/lumen.env`. ZANY's read-only login and `AGENT_STUDY_SECRET`, which checks ATLAS's study
tickets, come from `/etc/agent/zany.env`. ATLAS holds the same secret as `agent_study_secret`. The
Unity build of the tutor is installed by hand with `avatar/install.sh` and is kept across deploys.

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
