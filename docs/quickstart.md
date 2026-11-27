# Quickstart

This runs the agent on your machine with a sample VEXcode VR session, then asks it a question. It
takes about ten minutes, most of it installing.

You need Docker, [uv](https://docs.astral.sh/uv/), Node 24 and an LLM. Any OpenAI-compatible
endpoint works, a local [Ollama](https://ollama.com) included.

## Start It

```bash
git clone --recurse-submodules https://github.com/InviteInstitute/agent
cd agent
cp .env.example .env        # set POSTGRES_PASSWORD and the LLM
make install                # the server in server/.venv, and the client
make dev                    # Postgres, the API on :8005 and the client on :5173
```

`make dev` uses `compose.override.yml`, which turns the Turnstile check off and reloads the API
and the client as you edit.

For an Ollama on your machine, set these in `.env`, with a model you have pulled. The API runs in
a container, so it reaches your machine as `host.docker.internal`, which `compose.override.yml`
maps to the host. On Linux, Ollama listens on 127.0.0.1 only, so start it with
`OLLAMA_HOST=0.0.0.0 ollama serve` for the container to reach it.

```bash
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_API_KEY=ollama
NAVIGATOR_MODEL=qwen3:8b
```

## Ask About A Sample Session

The tests ship with real sessions from VEXcode VR. Load one and ask about it.

```bash
cd server
DATABASE_URL=postgresql://agent:$POSTGRES_PASSWORD@127.0.0.1:5435/agent \
  .venv/bin/python -m agent load vexcode-vr tests/fixtures/vexcode_vr/01_error_flagging_a.ndjson
curl -s -X POST localhost:8005/v1/vexcode-vr/students/fixture_01_1/turns \
  -H 'content-type: application/json' -d '{"message": "why does my robot not move?"}'
```

The reply comes back with the question type and the feedback classes the agent picked. Open
<http://localhost:5173>, sign in as `fixture_01_1` and the chat shows the same turn.

## Next

- [Development](guides/development.md) has the tests, the lint and how a change ships.
- [Configuration](guides/configuration.md) lists every setting in `.env`.
