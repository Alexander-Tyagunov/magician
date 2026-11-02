# `plan.json` — schema `magician.plan/1`

`plan.json` is the single source of a plan. `plan.md` (what `/orchestrate` and `/ward` execute) and
`plan.html` (the walkthrough a person reviews) are rendered from it by `plan-render`; never edit
those two by hand. A complete worked example: [plan-example.json](plan-example.json).

Paths inside the plan are relative to the project root. Never write an absolute path under a home
directory, a credential, a token or a private key anywhere in the file — `plan-render check`
refuses the plan.

## Top level

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema` | string | yes | Exactly `"magician.plan/1"` |
| `feature` | string | yes | Kebab-case slug; also the plan directory suffix (`<date>-<feature>`) |
| `title` | string | yes | Human title, one line |
| `version` | integer ≥ 1 | yes | Starts at 1; bump by exactly 1 on every revision (`plan-render all` snapshots the previous version into `history/plan.v<n>.json`) |
| `status` | enum | yes | `draft` · `in_review` · `approved` · `rejected` |
| `spec` | string | yes | Path of the approved spec |
| `research` | string[] | no | Paths of `/magic` research files the plan drew on |
| `constraints` | string[] | yes (may be empty) | Global Constraints, one per entry, copied **verbatim** from the spec — version floors, dependency limits, naming rules, platform requirements. Every step inherits them |
| `context` | object | yes | Step 0 of the walkthrough — see below |
| `waves` | object[] | yes | Execution waves in order — see below |
| `steps` | object[] | yes | The tasks, in execution order — see below |
| `metrics` | object | no | Derived totals; `plan-render` recomputes them from `steps`, so omit or keep consistent |
| `sources` | object[] | no | `{id, label, href}` — spec sections, research files, kg output the plan cites. Ids `S1…Sn` |

### `context`

| Field | Type | Meaning |
|---|---|---|
| `summary` | string | One paragraph: what exists today and what the feature changes |
| `stack` | string[] | Detected stack, e.g. `["nextjs", "postgres"]` |
| `archetype` | string | `web` · `api` · `cli` · `library` · `mobile` · `infra` |
| `blast` | object[] | `{path, files, hits}` rows from `kg blast` on the spec's named paths. Omit when kg is not indexed — never estimate |
| `components` | object[] | `{id, label, layer, exists}` — nodes of the architecture map |
| `edges` | object[] | `{from, to}` between component ids — arrows of the map |

**What a component is.** One box on the architecture map: a module, service, table, page, job or
external system that a step can touch. Keep it coarse — 4 to 12 components for a typical feature,
one per thing a reviewer would recognise by name. `exists: false` marks a component the plan
creates; the map draws it with a "new" badge when its first step lights it up. Ids are kebab-case
(`reports-api`, `csv-stream`), unique, and referenced by `steps[].touches` and `edges`. `layer` is a
free string, but keep the set to at most 6 distinct values across the plan (the map draws one
horizontal band per layer): the conventional set is `ui`, `api`, `logic`, `data`, `infra`, `tests`.

### `waves[]`

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `W1`, `W2`, … in order |
| `title` | string | Short label shown on the timeline (`Foundations`, `Core`, `Wire and verify`) |
| `steps` | string[] | Step ids in this wave, in order |

Every step appears in exactly one wave, and `steps[i].wave` names that wave. Steps in one wave that
are `parallel: true` are dispatched together by `/orchestrate`; `parallel: false` steps run one at
a time, in order, after the wave's parallel group.

### `steps[]`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | `T<n>` where `n` is the step's 1-based position in `steps`. Task `n` in `plan.md` is this step; a deferred step keeps its number |
| `wave` | string | yes | Wave id |
| `kind` | enum | yes | Exactly one of `context` · `decision` · `change` · `verify` · `rollout` (most steps are `change`); any other value is a violation |
| `layer` | string | yes | Any non-empty string; the conventional set is `logic` · `architecture` · `data` · `infra` · `api` · `ui` · `tests` · `docs`. Keep at most 6 distinct values across the plan (the map and charts cycle 6 colours) |
| `title` | string | yes | Component name, as in `### Task N: <title>` |
| `intent` | string | yes | One paragraph: why this step exists and what it delivers |
| `parallel` | boolean | yes | `true` when the step shares no written file and no dependency with other parallel steps of its wave |
| `depends_on` | string[] | yes (may be empty) | Step ids this step needs finished first. A `parallel: true` step may still depend on a step from an earlier wave |
| `files` | object | yes | `{create: [], modify: [], test: []}` — exact paths. `test` holds the test file(s) the step writes |
| `touches` | string[] | yes | Component ids the step changes; they light up on the map. Every id must exist in `context.components` |
| `red` | object | yes | `{test, code, run}` — the failing test: `test` is `path::name`, `code` the actual test code, `run` the command that proves it fails |
| `green` | object | yes | `{sketch, run}` — the minimal implementation sketch (code or precise prose) and the command that proves it passes (normally the same as `red.run`); `run` is required |
| `verify` | string[] | yes, ≥ 1 | The **exact commands that will be run** to prove the step is done (test, lint, type-check) — the step's definition of done, run verbatim by `/ward` and `/orchestrate`. Take them, in this order, from: the project's `.claude/skills/verify/SKILL.md` when present; `REVIEW.md` when present (its verification commands, nit caps and skip paths); the stack lore's commands (`npm test -- <pattern>`, `pytest -q <path>`, `go test ./...`, …); else what the spec names. Never a placeholder such as "run the tests". Read-only or test commands only — never a destructive command |
| `risk` | object | yes | `{level, note}` — `level` is exactly `low` · `medium` · `high` (enforced); `note` says what could go wrong (empty for `low`) |
| `effort` | object | yes | `{minutes}` — integer estimate for one implementer; 5 to 60 is the useful range |
| `diff_sketch` | string | no | Unified-diff-style sketch of the change, `-`/`+` lines, at most 40 lines. Shown in the side panel for `change` steps |
| `infographic` | object | no | `{type, title, data}` — `type` is `bar` · `line` · `pie`; `data` is `[[label, number], …]` (max 6 rows). Only with real numbers from the spec, the research or kg output — never invented. Omit when there is nothing to chart |
| `screens` | string[] | no | Paths of `/conjure` mockup screenshots for `ui` steps (linked, never inlined) |
| `review` | object | yes | `{status, note, edited_text}` — `status` is `pending` · `approved` · `deferred` · `edited` · `changed`. New plans: `pending`, empty strings |
| `history` | object[] | no | `[{v, changed: [field, …], summary?, diff?}]` appended by a revision, one entry per version that touched the step: `v` the version that changed it, `changed` the field names, `summary` one line shown in the step's "changed" banner (the page falls back to the field list), `diff` an optional `-`/`+` text shown as "what changed" |

**Kinds.** `change` is a normal TDD task. `decision` records an option chosen between alternatives
(its `intent` lists the options and why); it still carries `red`/`green`/`verify` when a test can
pin the decision, otherwise `verify` holds the command that shows the chosen shape. `verify` is a
step whose only work is running checks (`/certify`-style), `rollout` orders flags, migrations and
release steps. `context` is reserved for the walkthrough's Step 0 and is not written in `steps`.

**Effort** is in minutes per step. **Risk** levels: `low` (reversible, local), `medium` (touches a
shared interface, data or state), `high` (migration, infra, or anything without an easy rollback).

### `metrics` (derived)

`{steps, parallel, sequential, minutes, by_layer}` where `by_layer` maps layer → step count.
`plan-render` derives the same numbers from `steps` for the Completion Signal and the charts.

## Validation (`plan-render check`, exit 2 with one line per violation)

- Strict JSON: no `NaN`/`Infinity`, no duplicate keys. `schema` is `magician.plan/1`; required fields present with the types above; total size ≤ 256 KiB.
- Step ids are `T<n>` and equal the step's 1-based position; wave and component ids are plain (`[A-Za-z0-9][A-Za-z0-9_.-]*`, never `__proto__`/`constructor`); every step in exactly one wave; `steps[i].wave` matches.
- No control characters anywhere. Line breaks only in `intent`, `diff_sketch`, `red.code`, `green.sketch`, `review.edited_text` and `context.summary`, and no line there may start with `#`, a code fence or `- [ ]` (it would forge `plan.md` structure). `history[]` entries are `{v: int ≥ 1, changed: [string], summary?: string, diff?: string}`.
- `kind` is one of the five kinds; `risk.level` is one of the three levels; `layer` is a non-empty string.
- Every `depends_on` entry resolves to an existing step and never to the step itself; no dependency cycles; a step depends only on steps in its own or an earlier wave; a `parallel: true` step never depends on a `parallel: false` step of the same wave (parallel steps run first). A dependency on a deferred step is a warning, not a violation.
- A `parallel: true` step never shares a `create`, `modify` or `test` path (compared after stripping a leading `./`) with another `parallel: true` step in the same wave.
- Every step has `red.run`, `green.run` and at least one `verify` command.
- Every `touches` id and every `edges` endpoint exists in `context.components`; component ids unique.
- `version` is a positive integer ≤ 10000; `effort.minutes` is a non-negative integer. `plan-render all` refuses a version lower than the newest `history/plan.v<n>.json`, refuses to overwrite `history/plan.v<n>.json` with different bytes for the same version (bump the version), and refuses a `history/` that is a symbolic link. `md` and `html` run `check` first and render nothing on a violation.
- `diff_sketch` ≤ 40 lines; `infographic.data` ≤ 6 rows.
- No secrets (credential patterns on the JSON text and on every decoded string, plus a secret-named key such as `token` or `password` holding a long value), only project-relative paths in `files.*` (no leading `/`, drive letter, `~`, backslash or `..`), and no destructive command forms (`rm -rf`, `git push --force`, `git reset --hard`, `find … -delete`, a download piped into a shell, `terraform destroy`, `kubectl delete`, …) in `red.run`, `green.run` or `verify`.

Exit codes: 0 valid · 1 the file cannot be read · 2 invalid JSON or violations (one line each) · 64 no subcommand.

Fix every line it prints and re-run; `plan-render all` stops at the first failing check and writes nothing.

## `plan.md` rendering contract

`plan-render md` writes deterministic Markdown that `/orchestrate` and `/ward task <N>` parse:

1. Header: `# Plan: <title>`; `Version: v<n> · Status: <status> · Spec: <spec>`; `Feature: <feature>
   · Steps: <n> (<p> parallel, <s> sequential) · ~<h> h`; one `- Research: <path>` line per research
   file; then the `## Global Constraints` block (`_Every task inherits these — do not restate per
   task._` and one `- ` line per constraint).
2. `## Context` — `context.summary`, a `Stack:` line and the blast-radius table (when `blast` exists).
3. `## Waves` — one line per wave, each step tagged: `- W1 Foundations: T1 (parallel), T2 (parallel)`
   with tags `parallel` · `sequential` · `deferred`; then a ```` ```mermaid ```` block with the wave
   and dependency graph and a one-line execution note.
4. `## Tasks` — one block per non-deferred step, in `steps` order, in the legacy Task shape (see
   [plan-format-legacy.md](plan-format-legacy.md)) extended with the step's fields. The run commands
   sit in backticks after ` — ` on the checklist lines; `Risk:` is `level — note`; `Verify:` joins
   the commands with `&&`; `Create`/`Modify`/`Test` print `—` when empty; the `diff` fence appears
   only with a `diff_sketch`; `Depends on:` only with dependencies; `**Reviewer edit:**` and the
   `edited_text` only for an `edited` step:

   ````
   ### Task 3: CSV stream (T3)
   Parallel: NO (depends on Task 1, Task 2)

   Wave: W2 · Kind: change · Layer: logic

   <intent paragraph>

   **Files:**
   - Create: `src/reports/csv/stream.ts`
   - Modify: —
   - Test: `tests/reports/csv/stream.test.ts`

   - [ ] Write failing test: tests/reports/csv/stream.test.ts::streams_header_then_all_rows — `<red.code>`
   - [ ] Run test: verify FAIL — `npm test -- stream`
   - [ ] Implement: <green.sketch>
   - [ ] Run test: verify PASS — `npm test -- stream`
   - [ ] Commit: `git commit -m "feat: CSV stream"`

   **Verify:** `npm test -- stream` && `npm run lint`
   **Touches:** csv-stream, report-query
   **Risk:** medium — backpressure: Readable.from honours it, a hand-rolled push stream would not
   **Effort:** 25 min

   ```diff
   <diff_sketch>
   ```

   Review: pending
   Depends on: T1, T2
   ````
5. `## Deferred — not executed this run` — the deferred steps, in full, same block shape, so a later
   run can un-defer them. Omitted when nothing is deferred.
6. `## Sources` — one `- S1: [label](href)` line per source (omitted when there are none).
7. Trailer, last line: `<!-- magician.plan/1 v<n> sha256:<hex> -->`. The hash is over the canonical
   JSON of `plan.json` (`json.dumps(plan, sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)`), not the file bytes, so reformatting the file does not change it.
   `/orchestrate` and `/ward` compare `v<n>` with `plan.json.version` and treat a mismatch as a stale
   `plan.md`.

## `plan.html`

One self-contained file: inline CSS and JS, the plan inlined as JSON, a Content-Security-Policy
that forbids every remote load, no fonts or libraries fetched. What it shows and how to drive it:
[walkthrough.md](walkthrough.md).
