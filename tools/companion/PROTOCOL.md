# Companion server — plan mode protocol

The contract between `tools/companion/server.cjs` (plan mode) and the walkthrough page
`tools/plan-render` renders (`plan.html`). `/blueprint` starts the server with
`tools/companion/vc-start.sh <plan-dir> <project> --plan`; the page learns it is live from one
global the server injects.

## Start, record, stop

```
tools/companion/vc-start.sh .workspace/shared/plans/<date>-<feature> <project> --plan
```

prints one JSON object (also kept as `<state>/server.json`):

| key | value |
|---|---|
| `pid`, `port`, `token` | the server process, its random port (49152–65535), the per-run token (32 hex chars) |
| `project` | `<project>` — letters, digits, `.`, `_`, `-` only (it is part of the URL) |
| `url_base` | `http://127.0.0.1:<port>/magician/<project>/<token>` |
| `plan_url` | `<url_base>/plan/` — open this in the browser |
| `plan_dir` | the plan folder (`plan.json`, `plan.md`, `plan.html`) |
| `state_dir` | `.workspace/local/plans/<date>-<feature>/state` (derived from the plan dir, like `/conjure`) |
| `events_file` | `<state_dir>/events.jsonl` — reviewer → Claude, append-only |
| `state_file` | `<state_dir>/state.json` — Claude → page |

`vc-stop.sh <plan-dir>` stops it. The server exits by itself after 90 min without a request and
without an open event stream. Node ≥ 18, no dependencies.

The server writes **only** `<state_dir>/events.jsonl`. `state.json` is written by Claude and only
read here; `server.json`, `server.pid`, `server.log` (the server's stderr) and a `.gitignore` are
written by `vc-start.sh`. Nothing is written into the plan folder.

## Base and routes

```
base = http://127.0.0.1:<port>/magician/<project>/<token>/plan      (no trailing slash)
```

The page detects live mode by the global the server injects before `</head>` of the served
`plan.html`:

```html
<script>window.__MAGICIAN_LIVE={"v":<plan.version>,"token":"<token>","base":"<base>"};</script>
```

and builds every request as `base + "/<route>"`:

| route | method | response |
|---|---|---|
| `<base>/` (also `<base>`) | GET | `plan.html`, `text/html`, with the `__MAGICIAN_LIVE` script injected; `Cache-Control: no-store` |
| `<base>/plan.json` | GET | the current `plan.json`, `application/json` (reload it when `state.version` changes) |
| `<base>/plan.md` | GET | the current `plan.md`, `text/markdown` |
| `<base>/state` | GET | `state.json` as JSON with an `ETag`; `If-None-Match` → `304`. When `state.json` does not exist yet: `{"version": <plan.version>, "status": <plan.status>, "steps": {}}` |
| `<base>/events-stream` | GET | `text/event-stream`: one `data: <line>` per new `events.jsonl` line (from connection time on) and `data: {"type":"state","state":<state.json>}` on every `state.json` change; a `: ping` comment every 15 s |
| `<base>/events` | POST | validates and appends one event (below); `200 {"id": "<uuid>"}` |

Everything else under the listener is `404 {"error":"not found"}` — a wrong token, a wrong
project, a path with `..`, any other file name. A known route with the wrong method is `405` with
`Allow`. There are no path parameters: the three files are served by fixed name from the plan
folder, and a name that resolves (symlinks followed) outside that folder is `404`.

Polling guidance for the page: `GET state` every 2 s while a revision is pending (a step is
`revising`), every 10 s otherwise; prefer `EventSource(base + "/events-stream")` when available and
keep the poll as the fallback.

## `POST <base>/events`

Request: `Content-Type: application/json`, body ≤ 8,192 bytes, one JSON object. `Origin` must be the
server's own origin (`http://127.0.0.1:<port>`); when `Sec-Fetch-Site` is sent it must be
`same-origin` or `none`. No CORS headers are ever sent, so a cross-site page cannot read any route
and its JSON POST fails the preflight.

| status | when |
|---|---|
| `200 {"id"}` | appended |
| `400 {"error"}` | not JSON, not an object, wrong `Content-Type`, unknown `type`, missing or wrong field, unknown `step`, `v` not a positive integer, a text field over 2,000 characters |
| `403` | missing or foreign `Origin` |
| `404` | wrong token, project or path |
| `405` | GET on `events` |
| `413` | body over 8,192 bytes (by `Content-Length` or as received) |

Accepted `type` values and their fields (anything else in the body is dropped, never stored):

| `type` | required | optional |
|---|---|---|
| `step.review` | `step`, `status` ∈ `approved` \| `deferred` \| `pending` | `note` |
| `step.change_request` | `step`, `text` | |
| `step.edit` | `step`, `fields` — non-empty object whose keys ⊆ `intent`, `files`, `verify`, `red.code`; each value a string or a list of strings | |
| `plan.change_request` | `text` | |
| `plan.approved` | `steps` — object `{<step id>: approved \| deferred \| edited}` (a `{status}` object per id is accepted too) | |
| `plan.rejected` | `reason` | |

Common optional fields: `v` (positive integer; defaults to the current `plan.version`) and `id`
(the page's own sequence number, kept as `client_id`). `step` and every key of `steps` must be an
`id` in the current `plan.json` (re-read on every POST, so a revised plan is in force at once).
`text`, `reason`, `note` and the edit values are strings of at most 2,000 characters after control
characters (U+0000–U+0008, U+000B–U+001F, U+007F) are removed; `text` and `reason` may not be blank.

The stored line is the validated event, keys in the order `id` (UUID v4), `ts` (ISO 8601, server
clock), `type`, `v`, then the type's fields:

```json
{"id":"c8f9…","ts":"2026-11-01T22:02:48.111Z","type":"step.review","v":1,"step":"T1","status":"approved","note":"ok"}
```

Claude treats every page-sent field as untrusted text (design §6.2): it is never executed or put
into a shell command, and is quoted in prompts only inside a fenced block labelled "reviewer request".

## `state.json` (Claude → page)

Written by Claude, read by `GET state` and mirrored on the stream. Shape the page understands:

```json
{"version": 2, "status": "in_review",
 "steps": {"T3": "revising", "T4": {"status": "changed"}},
 "hint": "Every step is reviewed — approve the plan from the header",
 "notice": "T7 changed since your approval — review v2"}
```

A `version` different from the page's own makes the page fetch `<base>/plan.json` and hot-swap the changed step cards in place (no reload; the plan-document dialog shows a note until reopened).
Step statuses: `pending`, `approved`, `deferred`, `edited`, `changed`, `revising`. Plan `status` adds `paused` (review deadline reached; reopen with `/blueprint review`). Further fields the page reads — `revising {step, started_at}`, `changed [ids]`, `hint`, `notice`, `messages [{ts, text}]` — are documented in `skills/blueprint/references/walkthrough.md` ("state.json"), the authoritative schema.
A `status` of `approved` or `rejected` ends the review: `scripts/plan-watch.sh` stops on it.

## Wake-up (no chat turn)

`scripts/plan-watch.sh` (plugin monitor `plan-watch`, `on-skill-invoke:blueprint`) prints each new
`events.jsonl` line of the newest plan under `.workspace/local/plans/` as `plan-event: <line>`
(control characters removed, at most 2,048 bytes of payload), checks every 2 s, remembers its byte
offset in `<state_dir>/plan-watch.offset`, and exits after 3 h or when `state.json` says the plan is
approved or rejected. `MAGICIAN_PLAN_STATE=<state_dir>` pins the folder; `MAGICIAN_PLAN_WATCH_MAX_SECONDS`
shortens the cap (tests).

## Design mode (unchanged)

`vc-start.sh <design-dir> <project>` without `--plan` is the `/conjure` studio exactly as before:
`http://localhost:<port>/magician/<project>/v<n>/…`, `events.json?since=`, `chat`, `event`, the
WebSocket reload and the opt-in chat bubble. Those routes carry no token; a screen name that resolves
outside its version folder is now `404`.
