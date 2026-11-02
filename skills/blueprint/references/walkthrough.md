# `plan.html` — the walkthrough

`plan-render html` turns `plan.json` into one self-contained page: inline CSS and JS, the plan
inlined as JSON, a Content-Security-Policy that forbids every remote load, no fonts or libraries
fetched. It opens from `file://`, from a GitHub or Confluence attachment, or from any static host,
and sends nothing anywhere. Light theme by default, dark as the same design; the header's **Plan
theme** control switches, and the first open follows the system preference.

## Layout

```
Header    title · v<n> · N steps · W waves · status chip · review tally   [Plan theme] [Show plan document] [Reject plan] [Approve plan]
Controls  [Play] [Previous] [Next] [Restart] Speed [1×] (cycles 0.5×/1×/2×) · help [?]Step i / n · T<id> <layer>
Timeline  | Context | W1 Foundations (2) | W2 Core (2) | W3 Wire and verify (3) |
Map       layers as horizontal bands (ui · api · logic · data · infra · tests), components as
          nodes, edges as arrows; the current step's `touches` nodes glow; "new" badge on every
          component with exists: false; legend
Detail    kind and layer chips · title · intent · Files (create / modify / test) · RED test and
          its run command · GREEN sketch · Verify commands · Risk · Effort · Depends on · Review
Side      the contextual panel (below)
Footer    Sources S1…Sn · version history (v1, v2, …)
```

The page stacks to one column below 1024 px. Every control is reachable by keyboard, has a visible
focus ring and a 44 px hit area; the step title and the player status are live regions; the map has
a text description for screen readers. With `prefers-reduced-motion`, transitions, the edge
"packet" and the dwell progress line are off; Play still waits the dwell before advancing.

## Player

**Step 0 — Context** shows `context.summary`, the stack, the Global Constraints, the architecture
map with every existing component in neutral, and the blast-radius bars from `kg blast`. **Play**
then walks the steps in `plan.md` order: nodes animate from planned to active, the timeline cursor
moves across waves, the detail panel shows the step. Dwell is adaptive: 4 s plus 0.5 s per 40 words
of the detail panel, clamped to 4–10 s at 1×, halved at 2×, doubled at 0.5×; a thin progress line
under the timeline shows the remaining dwell. Deferred steps appear greyed with a "deferred" chip
and are skipped by Play (Next and Previous still reach them).

## Side panel

| Step | Side panel shows |
|---|---|
| Context (Step 0) | Blast radius bars by directory, then the plan-level charts below |
| any step with `diff_sketch` | The sketch, with `-`/`+` lines coloured |
| `verify` kind, or `tests` layer | A RED → GREEN → REFACTOR cycle inset |
| any step with `infographic` | The step's own chart (bar / line / pie) |
| any step with a `history[]` entry carrying `diff` | A "what changed" block |
| every step | The critical-path Gantt with the current step highlighted (titled "Rollout order" on a `rollout` step) |

Empty state: "No infographic for this step — nothing to chart."

### Plan-level charts (Step 0)

Rendered only when the data exists; an absent chart is correct, not a bug.

| Chart | Source | Shown when |
|---|---|---|
| Tasks per wave (bar) | `waves` | at least 2 waves |
| Effort by layer (donut) | `steps[].layer` × `effort.minutes` | at least 2 layers carry effort |
| Parallel vs sequential (bar) | `steps[].parallel` | always |
| Blast radius (horizontal bars) | `context.blast` | `kg blast` ran |
| Critical path (Gantt) | `waves`, `depends_on`, `effort` | at least 3 steps |
| Risk matrix (3×3 grid of dots) | `risk.level` × `effort` | at least one medium or high risk |
| Per-step custom (bar / line / pie) | `step.infographic` | declared by the planner |

All charts are inline SVG with a title, a description and a hidden data table for screen readers;
series are told apart by pattern as well as colour, at most 6 per chart.

## Transports — how the toolbar reaches the session

`plan-render html --transport auto|local|artifact|static` (default `auto`; `--static` is
`--transport static`) sets `data-review` on the page. The page picks the transport once, at load:

| Transport | When | Events go | State comes from |
|---|---|---|---|
| **local** | the companion served the page and injected `window.__MAGICIAN_LIVE = {v, token, base}` | `POST <base>/events` (JSON ≤ 8 KB) | `GET <base>/state` polled (ETag / 304) every 2 s while a step is revising, 10 s otherwise; `EventSource(<base>/events-stream)` when available; `GET <base>/plan.json` on a new version |
| **artifact** | no `__MAGICIAN_LIVE`, and `window.claude.use` exists (the page runs as a Claude Artifact) | `db.collection("events").add({…event, ts})` — one document per event | `db.doc("state/current").onSnapshot` (same shape as `state.json`) and `db.doc("plan/current").onSnapshot` (the plan JSON) |
| **static** | neither, or `--static` | nowhere — every send composes a chat line (`T7: …`, `plan: …`) and copies it | nothing; marks stay in the tab |

`auto` tries local, then artifact, then static. `--transport artifact` on a page that is not inside an
Artifact host (no `claude.use`), or whose `claude.use("db")` resolves `null`, falls back to static
and says so in the helper: "Artifact without a database — reply in chat". The page never declares
capabilities itself — the skill declares `db` through the Artifact tool, writes `plan/current` and
`state/current` with `db_write`, and reads the `events` collection with `db_list`/`db_query`; the
owner deletes the artifact after the review (nothing is pruned page-side). The artifact page loads
nothing from the network either (same CSP; the capability runtime is same-origin), so the plan
document dialog keeps the pre-rendered Markdown.

## Review toolbar

Each step card has **Approve · Request change · Edit · Defer**, and the header has **Approve plan**
and **Reject plan**. Every action is an event of the §6.2 schema (below). The helper transcript
(✦) records every event the page sent, in order, and every reply from the session.

### Static mode

In a static page the actions keep local marks, summed in the header's tally chip
("3 approved · 1 deferred · 8 pending", updated on every mark) so a reviewer can work through the plan, and every "send" action explains that the
page is static and copies a chat line to the clipboard instead: `T7: use a managed Redis instead of
self-hosted`, `T7: defer (with T9)`, `T7: edit intent — …`, or for the header actions `plan:
approved v1 — defer T4` and `plan: rejected — <reason>`. Nothing leaves the page; the chat gate
(`AskUserQuestion` in `/blueprint`) is where the decision is made. The reviewer pastes those lines
into chat and `/blueprint` revises `plan.json`, bumps `version` and re-renders. **Edit** changes the
step's `intent` only (the text goes verbatim into `plan.md` under **Reviewer edit:**). The footer
reads "Static page — review marks stay in this tab; reply in chat to change the plan"; the helper
panel's status line reads "Static — this page cannot reach the session; reply in chat (e.g. “T7: use
managed Redis”)".

### Live modes (local and artifact)

- **Approve ✓** (`A`) toggles `step.review {step, status: approved|pending}`; **Defer ⏸** (`D`) opens the
  confirm sheet (dependents listed) and sends `step.review {status: deferred}` for the step and each
  dependent; un-defer sends `pending`.
- **Request change ✎** (`C`) sends `step.change_request {step, text, v}` and the card switches to the
  **revising** state: a 40 px ring, "Claude is revising T7 · 00:42" (elapsed from the request, or from
  `state.revising.started_at` once the session confirms), `role="status"`, the whole card
  `aria-busy="true"`, ✎ ✏ ✓ ⏸ disabled, Play paused. The page polls every 2 s. Other steps stay
  reviewable. After **10 minutes** without a revision the ring becomes a static notice "Waiting for
  Claude — check the session" (no spinner forever).
- **Edit ✏** (`E`) sends `step.edit {step, fields: {intent}, v}` and shows the same revising state until
  the session integrates the edit.
- **Hot-swap.** When `state.version` is greater than the page's version the page fetches `plan.json`
  (local) or takes the `plan/current` document (artifact), diffs every step against the version it
  holds — one level of nesting, sorted field names, exactly the order `plan-render diff` prints, minus
  `review.*` — and replaces the step objects in place: a changed step gets a **v<n>** badge
  (`data-badge="version"`), `review.status = changed` ("changed — re-review" chip, yellow banner) and a
  **What changed (v1 → v2)** block in the side panel: a field / before / after table plus the
  `history[].summary` and `diff` the skill wrote. Steps the state lists in `changed` are marked the same
  way. The page jumps to the step it was waiting on. Local marks on unchanged steps survive. The page
  never reloads; the plan document dialog notes that it still shows the originally rendered version.
- **Stale events.** Every event carries `v`. If the state announces a newer version while a step is
  being marked, the event is not sent and the transcript says so; stream lines with an older `v`
  are ignored with a notice. A `step.review` for a step the session revised afterwards is answered
  by the session through `state.notice` ("T7 changed since your approval — review v2").
- **Approve plan** (header): always enabled while `status` is `draft`/`in_review` and no revision is
  in flight (a confirm sheet lists unreviewed steps); sends `plan.approved {v, steps: {T1: approved, …,
  T4: deferred}}` with every step's final status. **Reject plan** sends `plan.rejected {v, reason}`.
- **Helper panel** (`H`): status line "Live · same session · events.jsonl" or "Artifact · database ·
  events collection"; scope **This step** sends `step.change_request`, **Whole plan** sends
  `plan.change_request {text, v}`. `state.hint` (Claude's suggestion, shown once per distinct text),
  `state.notice` (system line) and every `state.messages[]` entry (Claude's replies, shown once per
  `ts+text`) land in the transcript; `#livenote`, a visually-hidden `role="status"` region, announces
  them even while the panel is closed.
- **Read-only.** In artifact mode a write rejected with `invalid_argument` (or a revoked/absent
  capability) turns every control read-only with a notice — the viewer can still read and comment on
  the artifact. Writes are serialised (one at a time); each event document is ≤ 8 KB.

### Events the page sends (`events.jsonl` lines / `events` documents)

| `type` | fields |
|---|---|
| `step.review` | `step`, `status` ∈ approved \| deferred \| pending, `note?` |
| `step.change_request` | `step`, `text` (≤ 2,000 chars) |
| `step.edit` | `step`, `fields` ⊆ {intent, files, verify, red.code} |
| `plan.change_request` | `text` |
| `plan.approved` | `steps` map `{id: approved \| deferred \| edited}` |
| `plan.rejected` | `reason` |

Every event also carries `id` (page sequence), `v` (the plan version the page holds) and `ts`
(ISO 8601). The companion re-validates and stores its own `id`; the artifact document is the event
as sent. All of it is untrusted text for the session (design §6.2).

## state.json

The session writes `<state_dir>/state.json` (local) or the `state/current` document (artifact)
after every event it handles; the page reads it and nothing else. Write exactly this shape:

```json
{
  "version": 2,
  "status": "in_review",
  "revising": {"step": "T7", "started_at": "2026-11-01T22:02:48Z"},
  "changed": ["T7", "T9"],
  "hint": "Every step is reviewed — approve the plan from the header",
  "notice": "T4 changed since your approval — review v2",
  "messages": [{"ts": "2026-11-01T22:03:10Z", "text": "Revising T7: switching to managed Redis; T9 follows."}],
  "steps": {"T1": {"review": "approved"}, "T7": {"review": "changed"}, "T4": {"review": "deferred"}}
}
```

| field | type | meaning |
|---|---|---|
| `version` | int | the `plan.version` currently on disk / in `plan/current`; when it exceeds the page's version the page loads the new plan and hot-swaps |
| `status` | `draft` \| `in_review` \| `approved` \| `rejected` | the plan status; `approved`/`rejected` ends the review |
| `revising` | `{step, started_at}` or `null` | the step being rewritten (ring + 2 s polling) and when it started (ISO 8601); `null` when idle; `{"step": "plan", …}` for a whole-plan request |
| `changed` | `[id, …]` | steps the last revision touched; the page marks them `changed` (re-review) — normally the same ids whose `review.status` is `changed` in `plan.json` |
| `hint` | string | Claude's suggestion to the reviewer (shown as a Claude line once per distinct text; `""` for none) |
| `notice` | string | a system notice (dropped stale event, ignored review, error; shown once per distinct text; `""` for none) |
| `messages` | `[{ts, text}, …]` | Claude's replies, append-only, in order; the page shows each entry once (keyed by `ts` + `text`); keep the list bounded (last 50) |
| `steps` | `{id: {review: status}}` | the review status per step as the session knows it: `pending` \| `approved` \| `deferred` \| `edited` \| `changed` \| `revising` (`{id: "<status>"}` and `{id: {status}}` are read too) |

Rules the page relies on: write the whole document each time (atomic replace); bump `version`
only after `plan.json`, `plan.md` and `plan.html` are rendered for that version (the page fetches
`plan.json` as soon as it sees the new number); set `revising` before starting a rewrite and clear
it in the same write that bumps `version`; never put page-sent text into `hint`/`notice` unescaped
from a shell — they are plain strings the page HTML-escapes.

**Show plan document** opens a dialog with `plan.md` rendered as HTML (headings, tables, task
lists, code, the wave and dependency graph as pre-rendered SVG), with **Copy plan** (raw Markdown)
and **Close**. It is the same text `/orchestrate` executes.

## Helper panel (✦)

The floating ✦ button opens a side panel with the connection line (static: "Static — this page
cannot reach the session; reply in chat …"; local: "Live · same session · events.jsonl"; artifact:
"Artifact · database · events collection") and the transcript: every event the page sent, every
Claude reply (`state.messages`, `state.hint`), every system notice. The message box has a scope
switch (**This step** / **Whole plan**); in static mode it composes a line in the `T7: …` or
`plan: …` shape and copies it for pasting into chat. Keyboard: `H` toggles; Enter sends, Shift+Enter
newline, Esc closes and returns focus to the ✦ button.

## Keyboard map

| Key | Action |
|---|---|
| Space | Play / Pause |
| ← / → | Previous / Next step |
| R | Restart from Step 0 |
| S | Cycle speed 0.5× → 1× → 2× |
| A | Approve the current step |
| C | Request a change (opens the sheet) |
| E | Edit the current step's intent (opens the sheet) |
| D | Defer / un-defer the current step |
| H | Toggle the helper panel |
| ? | Keyboard help |
| Esc | Close the open sheet, dialog or helper |
| Enter / Shift+Enter | Send / newline inside a sheet |

Shortcuts are ignored while a text field, button or link has focus (so Space and Enter act on the
control), and while a step is revising or the view is read-only.

Tab order: header actions → controls → timeline (arrow keys move the cursor) → map (nodes are
buttons; Enter opens the first step that touches the node) → detail → side panel → footer. A
"Skip to step detail" link is first in the tab order. Live regions: the step title, the player
status, the revising ring, the toast and `#livenote` (session notices).

## plan.workflow.js

`plan-render workflow` (and `plan-render all`) also emits a Claude Code Workflow script from the
same plan: `meta` first (name `<feature>-plan`, one phase per wave), then per wave `phase()`,
`parallel([…])` of `agent()` calls for the parallel steps, sequential `agent()` calls in dependency
order, `log()` lines between phases; each prompt is the Task block from `plan.md` plus the Global
Constraints and the bounded return schema from `skills/weave/references/template.md` (summary ≤
1200, `files_changed[]`, `commit`, `obstacles[]` with the 8 fields). Deferred steps are omitted.
The generator never emits `Date.now()`, `Math.random()`, `new Date()` or `import()`, checks the
file (balanced brackets, closed strings, forbidden tokens outside strings) and runs `node --check`
when Node is present. Byte-identical for the same `plan.json`.
