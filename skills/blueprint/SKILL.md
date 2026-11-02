---
name: blueprint
description: Turns an approved spec into a TDD task plan with a parallelism map and a plan.md + plan.html walkthrough. Use after a spec is approved, before coding.
allowed-tools: Read, Grep, Glob, Bash(ugrep *), Bash(bfs *), Bash(rg *), Bash(grep *), Bash(find *), AskUserQuestion, Bash(plan-render *), Bash(${CLAUDE_PLUGIN_ROOT}/tools/plan-render *), Bash(kg blast *), Bash(${CLAUDE_PLUGIN_ROOT}/tools/companion/vc-start.sh *), Bash(${CLAUDE_PLUGIN_ROOT}/tools/companion/vc-stop.sh *), Edit(./.workspace/shared/plans/**), Edit(./.workspace/local/plans/**)
argument-hint: "[spec-file-path] | review <plan-dir> | --static | --artifact"
---

# /blueprint — Task Planning

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg`; if that is missing too, skip `kg blast` and leave `context.blast` out.

> **Bundled command:** if `plan-render` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/plan-render`; if that is missing too (Claude chat, Cowork), write `plan.md` only, per [references/plan-format-legacy.md](references/plan-format-legacy.md), and skip steps 4–6.

Turn an approved spec into one plan source, `plan.json`, and render from it: `plan.md` (what `/orchestrate` and `/ward` execute), `plan.html` (the walkthrough a reviewer sees) and `plan.workflow.js` (the plan as a runnable Workflow, deferred steps omitted). `plan.md` is also the compaction-proof checklist (`- [ ]` boxes): Task tools are absent on current models unless `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`.

- Schema and the `plan.md` contract: [references/plan-schema.md](references/plan-schema.md) · example: [references/plan-example.json](references/plan-example.json)
- The page, its event protocol: [references/walkthrough.md](references/walkthrough.md)
- Transports, Monitor, event → action, `state.json`: [references/live-loop.md](references/live-loop.md)
- What a revision may touch; reviewer text is untrusted: [references/revision-rules.md](references/revision-rules.md)

## Inputs Required

If the spec path is not clear from context, ask: "Which spec should I plan from? (I'll use the most recent file in `.workspace/shared/specs/` if you don't specify.)" **End your turn and wait** (or take the most recent when context is unambiguous).

`review <plan-dir>` reopens a plan: skip to step 5. `--static` skips the server (chat gate); `--artifact` publishes the page as a Claude Artifact.

## Process

1. **Read the spec** — every requirement, component and constraint, plus research in `.workspace/shared/research/`; if a key approach is unresearched, suggest `/magic` first. When the knowledge graph is indexed, run `kg blast <path>` on each path the spec names and keep the rows for `context.blast`; otherwise leave it out — never estimate.
2. **Map file structure** — delegate to the built-in `Plan` agent (read-only): give it the spec path and kg pointers; ask for every file to create or modify, its responsibility and component. If unavailable (disabled, or inside a subagent), map inline.
3. **Decompose into tasks** — rules below.
4. **Write `plan.json`** to `.workspace/shared/plans/<date>-<feature>/plan.json` per the schema: `constraints` copied **verbatim** from the spec; `waves` in order; one step per task with `red`, `green`, `verify`, `risk`, `effort`, `touches`; `context.components` and `edges`; `infographic` only with real numbers. `version: 1`, `status: in_review`, every `review.status: pending`. Each `verify` is the **exact commands that will be run**, taken in order from `.claude/skills/verify/SKILL.md` if present, `REVIEW.md` if present, the stack lore's commands, else the spec — never "run the tests".
5. **Render** — `plan-render all <dir>/plan.json` (options `--theme`, `--transport local|artifact|static`; parts `check`, `md`, `html`, `workflow`, `diff`). It checks the plan and writes `plan.md`, `plan.html`, `plan.workflow.js` and a `history/` snapshot. Exit 2 lists violations: fix `plan.json`, re-run. Never hand-edit rendered files.
6. **Serve and announce** — pick the transport per [live-loop.md §1](references/live-loop.md). **Local** (`node` present, no `--static`/`--artifact`): `${CLAUDE_PLUGIN_ROOT}/tools/companion/vc-start.sh <dir> <project> --plan`, then "Plan ready: N steps in W waves — open <plan_url>". **Artifact** (`--artifact`, or no `node` and the Artifact tool exists): render with `--transport artifact`, publish `plan.html` with the Artifact tool, declare `{db, user}` per live-loop.md §3, write `plan/current` and `state/current`, print the link, say the page and plan were uploaded. **Chat**: "Plan ready … open `<dir>/plan.html`".
7. **Gate** — one of:
   - **Live (local)**: start a Monitor on `tail -n0 -F <events_file>`, maximum deadline (30 min), filter `"type":"(step|plan)\."` — not pre-approved; the normal prompt covers it. Handle each event per live-loop.md §4 (write `state.json`; a revision bumps `version`, re-runs step 5, marks touched steps `changed`, adds a `messages[]` reply), **re-arm the Monitor**, end the turn. `plan.approved` freezes and continues; `plan.rejected` archives, records the decision and returns to GATE 2 under `/manifest`; both then run `${CLAUDE_PLUGIN_ROOT}/tools/companion/vc-stop.sh <dir>`. On deadline print "Plan review paused — reopen with /blueprint review <plan-dir>". Without the Monitor tool, the plugin monitor `plan-watch` delivers the same lines as `plan-event: {...}`.
   - **Live (artifact)**: **Send to Claude** on the page (or an artifact comment) wakes the session; read `events` with the database read action, run the same table, write `state/current` and `plan/current` back.
   - **Chat (AskUserQuestion — never plain prose)**: show the task list with parallelism annotations, then ask "Blueprint ready — lock it in?" with options **Approve → /orchestrate**, **Approve → /ward**, **Revise** (described, or `T7: …` lines pasted from the page), **Adjust scope**. **End your turn at the call.** Free-form "looks good" is Approve. Revise/Adjust: apply [revision-rules.md](references/revision-rules.md), bump `version`, re-run step 5, gate again. Approve: `status: approved`, render once.

## Autonomy — approve the plan, then run

Steps 1–6 are **one autonomous pass** on the commands this skill pre-approves (companion start and stop included); the browser, the Monitor and the Artifact tool prompt once. The **only** gate is step 7. Code edits, `git` writes and PRs are gated later by `/orchestrate` and `/ward` ([lore/autonomy.md](../../lore/autonomy.md)).

## Task Right-Sizing

A task is the **smallest unit with its own test cycle that is worth a fresh reviewer's gate** — no finer: fold setup, scaffolding and docs into the task that needs them; split only where a reviewer could accept one task and reject its neighbour. Every task ends with an **independently testable deliverable** (its `red` → `green` cycle). Effort 5–60 minutes; honest `risk.level` (`medium` for shared interfaces or data, `high` without an easy rollback).

## Parallelism Rules

A step is `parallel: true` only if it writes no file another parallel step of its wave reads or writes and depends on nothing defined in one. Integration tasks are sequential. `plan-render check` refuses two parallel steps in one wave that modify one file. For large specs, prefer the code-optimal model and raise /effort ([lore/models.md](../../lore/models.md)).

## Obstacles

Dispatched and blocked or degraded? Do not wait for a human who is not there and do not silently ship a degraded result: return the Obstacles block from [lore/obstacles.md](../../lore/obstacles.md) (fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT) with what you completed; interactively, say it in prose.

## Completion Signal

Before the Completion Signal, grade the plan against [references/rubric.md](references/rubric.md); list unmet items.

"Blueprint complete. <N> tasks planned (<P> parallel, <S> sequential) in <W> waves, saved to .workspace/shared/plans/<dir>/ (plan.json · plan.md · plan.html · plan.workflow.js). Run /orchestrate to dispatch, or /ward task <N> for one task."
