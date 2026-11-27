# API Reference

The API is FastAPI, under `/v1`, in `server/agent/api.py` and `server/agent/app.py`. Every `/v1`
route except the gate's own needs the Turnstile cookie or a valid study ticket. Without one it
answers 403 with `{"error": "turnstile_required"}`, and the page shows the check.

A student is named in the path as `{environment}/students/{student_id}`. Environments that need a
class code take it as `?class_code=`. For `zany-study`, the `X-Study-Ticket` header must name the
same participant and study code, or the route answers 403.

## Routes

| Method and path | What it does |
| --- | --- |
| `GET /healthz` | `{"status": "ok"}` once the database answers. Outside the gate. |
| `POST /v1/turnstile/verify/` | checks a Turnstile token with Cloudflare and sets the cookie |
| `GET /v1/ping` | `{"ok": true}`. The page calls it on load, so the check shows before the student acts. |
| `GET /v1/environments` | the environments this site serves for the sign-in form, and whether spoken questions are on |
| `GET /v1/{environment}/students/{student_id}` | signs a student in. Returns the frame, the current session and its chat. |
| `POST /v1/{environment}/students/{student_id}/turns` | a question or Help, and the agent's reply |
| `GET /v1/{environment}/students/{student_id}/stream` | the student's new check-ins, as server-sent events |
| `POST /v1/{environment}/students/{student_id}/ratings` | a thumb and a note on a reply |
| `PUT /v1/{environment}/students/{student_id}/settings` | a researcher's settings for the student's check-ins |
| `POST /v1/{environment}/students/{student_id}/transcriptions` | a spoken question as text |
| `GET /v1/research/config` | what the research view needs |
| `GET /v1/tts?text=…` | one spoken line as WAV, for the tutor |

## Sign In

`GET /v1/{environment}/students/{student_id}?chat=student` reads the student's newest logs first.
`chat=research` returns the research chat instead.

```json
{
  "environment": "zany",
  "student_id": "S01",
  "class_code": "room-4",
  "frame": "https://vr.inviteai.org/?class=room-4&student=S01",
  "session_id": "…",
  "playground": "Castle Crasher+",
  "messages": [{"id": 1, "role": "agent", "origin": "proactive", "body": "…",
                "response_id": "…", "trigger_type": "wheel_spin", "thumb": null,
                "created_at": "…"}]
}
```

It answers 404 for an environment the site doesn't serve, and 400 for a missing student ID, or a
missing class code where one is needed.

## Turns

`POST /v1/{environment}/students/{student_id}/turns`

| Field | Type | What it is |
| --- | --- | --- |
| `message` | string, up to 2,000 | the question. Empty is the Help button. |
| `overrides` | object or null | a researcher's settings, with `model`, `prompt_template`, `temperature` (0 to 2), `max_tokens` (16 to 4096) and `trim_reply`. With them the turn goes to the research chat. |
| `speak` | boolean | the tutor will say the reply, so the server starts making the clips |

```json
{
  "session_id": "…",
  "student_message_id": 41,
  "playground": "Castle Crasher+",
  "reply": {
    "response_id": "…",
    "body": "Your robot drives forward 200 mm, then stops before the wall. What should happen next?",
    "question_type": "Debugging / Problem Diagnosis",
    "feedback": ["Error Flagging"],
    "speech": ["Your robot drives forward 200 mm, then stops before the wall.", "What should happen next?"]
  },
  "session_tokens": {"used": 5210, "limit": 150000}
}
```

A research turn's reply also has `model`, `prompt` and `tokens`. A student with no logs yet gets
`session_id: null` and a reply asking them to run their project once.

It answers 429 when the browser session or the site is out of tokens, and 502 when the LLM fails.

## The Check-In Stream

`GET /v1/{environment}/students/{student_id}/stream` is a server-sent event stream. It starts at the
newest check-in, so a new connection replays nothing. Each check-in is an event named `checkin`.

```text
event: checkin
data: {"id": 57, "role": "agent", "origin": "proactive", "body": "…", "response_id": "…", "trigger_type": "inactive", "thumb": null, "created_at": "…", "speech": ["…"]}
```

The data is a chat message in the same shape as the messages the sign-in returns, plus `speech` with
one clip per sentence.

A comment line every two seconds keeps proxies from closing it. While it is open, the student counts
as having the page open, so the daemon may check in with them. A study student's page passes the
ticket as `?ticket=` here, since a browser can't set headers on an event stream.

## Ratings And Settings

`POST …/ratings` takes `{"response_id": "…", "thumb": "up" or "down", "comment": "…"}` and answers
204, or 404 when the reply isn't this student's.

`PUT …/settings` takes `{"overrides": {…}}`, the same object a turn takes, and answers 204. `null`
goes back to production.

## Spoken Questions

`POST …/transcriptions` takes a multipart upload named `audio`, up to about a minute of WebM/Opus,
and answers `{"text": "…"}`. It answers 404 when the site has no `TRANSCRIBE_MODEL`, 413 for a
recording that is too long and 502 when the speech model fails.

## The Tutor's Voice

`GET /v1/tts?text=…` answers one spoken line as WAV, up to 500 characters of text. The agent page
builds the link for each sentence of a reply and the tutor's player fetches it. A study student's
page adds `?ticket=`, since the player can't set headers.

## Research Config

`GET /v1/research/config` returns the defaults, the models a researcher can pick, the production
prompt template, the placeholders it can use and this browser session's token use.
