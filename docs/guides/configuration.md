# Configuration

Every setting is an environment variable. Locally they go in `.env`, copied from `.env.example`.
On the INVITE server the checkout's `.env` holds the site's settings, and two files in `/etc` add
the secrets the stack shares with other apps.

| File | What it adds |
| --- | --- |
| `/etc/lumen.env` | `OPENAI_API_KEY`, the agent's key for NCSA Lumen |
| `/etc/agent/zany.env` | `ZANY_LOG_DSN` and `AGENT_STUDY_SECRET` |

The server reads each setting when it needs it, through `server/agent/config.py`.

## The Site

| Setting | Default | What it does |
| --- | --- | --- |
| `ENVIRONMENTS` | `vexcode-vr` | the environments this site serves, by id, comma separated, from `vexcode-vr`, `zany` and `zany-study`. An unknown id stops the API from starting. |
| `POSTGRES_PASSWORD` | none | the agent's own database. Required. |
| `API_PORT` | `8005` | the API's port on 127.0.0.1, where nginx reaches it |
| `DB_DATA` | a named volume | where Postgres keeps its files. Production uses `/data/agent/postgres`. |

## The LLM

| Setting | Default | What it does |
| --- | --- | --- |
| `OPENAI_BASE_URL` | none | any OpenAI-compatible endpoint. Production uses `https://lumen.ncsa.illinois.edu/v1`. |
| `OPENAI_API_KEY` | none | its key |
| `NAVIGATOR_MODEL` | `qwen3.8-27b` | the model students' replies come from |
| `LLM_TIMEOUT_S` | `30` | how long one call may take |

## The Log Sources

| Setting | Default | What it does |
| --- | --- | --- |
| `INVITE_HUB_BASE_URL` | `https://inviteinstitutehub.org` | where VEXcode VR's logs are |
| `INVITE_HUB_TOKEN` | none | a token for the Hub, or set the next two to get one |
| `INVITE_HUB_USERNAME`, `INVITE_HUB_PASSWORD` | none | a Hub login |
| `ZANY_LOG_DSN` | none | the read-only login to ATLAS-invite's log store, for `zany` and `zany-study` |
| `AGENT_STUDY_SECRET` | none | checks ATLAS's study tickets. Without it no ticket is valid. |
| `STUDENT_RECENCY_HOURS` | `24` | how far back a fresh database's first read reaches, and which students the check-in daemon looks at |

## Check-Ins

| Setting | Default | What it does |
| --- | --- | --- |
| `CHECKINS_ENABLED` | `false` | turns the check-in daemon on. It messages real students, so turn it on on purpose. |
| `TRIGGER_DISABLED` | none | trigger types to find and keep but not act on, like `inactive,explorer` |
| `CHECKIN_INTERVAL_S` | `5` | seconds between passes while check-ins go out |
| `CHECKIN_IDLE_MAX_S` | `30` | the longest gap between passes while nothing happens |

## The Tutor's Voice

The 3D tutor shows wherever its Unity build is installed (see `avatar/README.md`). There is no
setting for it, and students can hide it.

| Setting | Default | What it does |
| --- | --- | --- |
| `TTS_VOICE` | `af_heart` | `af_heart`, `am_puck`, `bf_isabella` or `bm_fable` |
| `TTS_SPEED` | `1.0` | how fast it talks |
| `TRANSCRIBE_MODEL` | none | the speech-to-text model the LLM endpoint serves, for spoken questions. Empty turns the microphone off. Production uses `granite-speech-4.1-2b-plus`. |

## The Gate And The Budgets

| Setting | Default | What it does |
| --- | --- | --- |
| `TURNSTILE_SECRET` | none | Cloudflare Turnstile's secret |
| `SESSION_SECRET` | none | a long random value that signs the gate's cookie. Required while the gate is on. |
| `TURNSTILE` | `on` | `off` turns the gate off. Only `compose.override.yml` sets it, for local work. |
| `LLM_SESSION_TOKEN_LIMIT` | `150000` | LLM tokens one browser session may spend |
| `LLM_DAILY_TOKEN_LIMIT` | `3000000` | LLM tokens the whole site may spend in a day, check-ins included |
| `VITE_TURNSTILE_SITE_KEY` | INVITE's site key | the widget's site key, read when the client is built |
