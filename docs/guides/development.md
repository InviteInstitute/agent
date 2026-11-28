# Development

[Quickstart](../quickstart.md) gets the stack running on your machine. This page covers the rest.

## Make Targets

Run `make` to list them.

| Target | What it does |
| --- | --- |
| `make install` | installs the server in `server/.venv` and the client's packages |
| `make dev` | starts Postgres, the API on :8005 and the client on :5173, all reloading as you edit |
| `make down` | stops the dev stack |
| `make test` | runs the server's tests and the client's |
| `make lint` | checks the server with ruff and the client with prettier |
| `make format` | formats both |
| `make build` | builds the client into `client/dist` |

Where Docker needs sudo, pass the command in, like `make dev COMPOSE='sudo docker compose'`.

## The Tests

The server's tests use pytest. The ones that touch the database need `TEST_DATABASE_URL`, which
`make test` points at an `agent_test` database in the dev Postgres. Any throwaway Postgres 18 works.

```bash
docker run -d --rm --name agent-test-db -e POSTGRES_PASSWORD=test -e POSTGRES_DB=agent_test \
  -p 127.0.0.1:55432:5432 postgres:18
cd server
TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/agent_test .venv/bin/pytest -q
```

The fixtures in `server/tests/fixtures/` are real sessions, one file per case. The client's tests
use Vitest and run with `npm --prefix client test`.

CI (`.github/workflows/ci.yml`) runs ruff, the server's tests against Postgres 18, the image build,
prettier, the client's tests and the client build on every pull request.

## Operator Commands

```bash
python -m agent migrate                      # apply the database migrations
python -m agent load vexcode-vr FILE...      # keep the records in NDJSON log files
python -m agent sync vexcode-vr              # read every new record from the source
python -m agent fetch-voice                  # download the tutor's voice model
```

The API applies the migrations itself when it starts. They live in `server/migrations/` and are
tracked in `schema_migrations`.

## Deploying

The site deploys from `main`. A push makes GitHub call the INVITE server's webhook, which runs
`/usr/local/bin/agent-deploy.sh` (in InviteInstitute/infra), and that runs `scripts/deploy.sh`
here as `ubuntu`.

1. It refuses to run over uncommitted changes, then pulls with `--ff-only`.
2. It rolls Postgres and the API with `docker compose -f compose.yml`, and waits for `/healthz`.
3. It builds the client and swaps it in whole. The previous build stays in `client/dist.prev`.

A pull that only changes `docs/`, `README.md`, `zensical.toml` or `.github/` leaves everything
running, since neither the image nor the client holds the docs.

nginx serves `client/dist` and `avatar/`, and passes `/v1` to the API on 127.0.0.1:8005. The Unity
build of the tutor is installed by hand with `avatar/install.sh` and is kept across deploys.

So shipping a change means merging a pull request into `main`. Don't run `docker compose up` on the
server by hand, because it would also read `compose.override.yml`, the dev setup.

## The Docs

The docs are the pages in `docs/`, with their nav in `zensical.toml`. They are published as the
INVITE Agent section of [docs.inviteai.org](https://docs.inviteai.org/agent/), which also holds the
ZANY, ATLAS and Learner Modeling Dashboard docs. That site's theme, home page and build live in
InviteInstitute/docs, and the INVITE server rebuilds it within two minutes of a change here. The
design notes and plans in `docs/superpowers/` stay out of the site.

To check the pages on your machine, install Zensical and build them the way the site does.

```bash
pip install zensical==0.1.3
zensical serve            # http://localhost:4000, reloads as you edit
zensical build --strict   # fails on a broken link or anchor
```

`.github/workflows/docs.yml` keeps the pages up to date on every push to `main`. It calls the docs
bot that zany, atlas-invite and lm-dashboard share, which lives in InviteInstitute/lm-dashboard as
`.github/workflows/docs-bot.yml` and `scripts/docs_sync.py`. This repo's settings for it are in
`.github/docs-bot.toml`.

1. The bot sends the diff of the push, the code and the current docs to NCSA's Lumen. It asks
   glm-5.3 first, then glm, then deepseek-v4.1, one try each. Its instructions are the writing rules and skills from [Maharsh17/claude-config](https://github.com/Maharsh17/claude-config),
   read fresh on each run. A push that only changes the docs skips the call.
2. The model returns only the pages that the change made wrong or incomplete. The script writes
   them, and `zensical build --strict` checks that every link and page still holds.
3. If any page changed, the job commits it to `main` as `github-actions[bot]`.

The job needs the repository secret `LUMEN_API_KEY`. It runs one push at a time, so two quick pushes
never race to commit the docs. A push the bot makes starts no workflow, and the deploy skips a
docs-only commit.

`.github/docs-bot.toml` says which pages the bot may write and which code it reads. To try it on
your machine, set `LUMEN_API_KEY` and run lm-dashboard's script from the root of this repo. It only
edits files in your checkout, so review them with `git diff`.

```bash
python ../lm-dashboard/scripts/docs_sync.py --style ../claude-config
```

Edit the docs by hand whenever you like. The bot works from what is on `main`, so it keeps your
changes and only fixes what the code made wrong.
