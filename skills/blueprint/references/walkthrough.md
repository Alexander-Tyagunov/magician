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

## Review toolbar (static mode)

Each step card has **Approve · Request change · Edit · Defer**, and the header has **Approve plan**
and **Reject plan**. In a static page these keep local marks, summed in the header's tally chip
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

**Show plan document** opens a dialog with `plan.md` rendered as HTML (headings, tables, task
lists, code, the wave and dependency graph as pre-rendered SVG), with **Copy plan** (raw Markdown)
and **Close**. It is the same text `/orchestrate` executes.

## Helper panel (✦)

The floating ✦ button opens a side panel with the connection line (static mode: "Static — this
page cannot reach the session; reply in chat …") and a transcript area. In static mode the message box composes a line in the `T7: …` or `plan: …`
shape and offers to copy it for pasting into chat; the scope switch (**This step** / **Whole plan**)
picks the prefix.

## Keyboard map

| Key | Action |
|---|---|
| Space | Play / Pause |
| ← / → | Previous / Next step |
| R | Restart from Step 0 |
| S | Cycle speed 0.5× → 1× → 2× |
| A | Approve the current step (tally) |
| C | Request a change (opens the sheet) |
| E | Edit the current step's intent (opens the sheet) |
| D | Defer / un-defer the current step |
| H | Toggle the helper panel |
| ? | Keyboard help |
| Esc | Close the open sheet or dialog |
| Enter / Shift+Enter | Send / newline inside a sheet |

Tab order: header actions → controls → timeline (arrow keys move the cursor) → map (nodes are
buttons; Enter opens the first step that touches the node) → detail → side panel → footer. A
"Skip to step detail" link is first in the tab order.

## Live loop (4.19)

The same page, served by the companion server, sends each toolbar action to the Claude session as
an event, shows a "revising" ring while the step is rewritten, and hot-swaps the revised step with
a version badge and a diff; Artifact mode publishes the page as a Claude Artifact with the same
toolbar. Neither is part of the static page: the tallies and the "reply in chat" notice are the
whole review contract in 4.18.
