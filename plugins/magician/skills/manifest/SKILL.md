---
name: "manifest"
description: "Full autonomous SDLC; design, plan, implement, review and ship with 4 human approval gates"
license: "MIT"
metadata: {"claude-code.argument-hint": "[one-sentence feature description]", "claude-code.disable-model-invocation": "true"}
---

# /manifest — Full Autonomous SDLC

The complete end-to-end development flow. Four human gates. Everything else runs autonomously.

**Autonomy is the point: gather → plan → memorize → execute.** The human approves the gates below, **not each file read.** Ground via `kg` (not broad grep), memorize the plan + requirements + `kg` pointers + standards to `.workspace/`, and execute the whole plan without stopping to ask about individual reads/searches — Claude Code's built-in read-only commands never prompt, and anything else prompts once unless the user runs in auto mode or approves it. The gates you stop on are writes/commit/push/PR/ticket/destructive ops. If you're bombarding the owner with "can I read this?" the run is broken. See [lore/autonomy.md](../../lore/autonomy.md).

`/manifest` is the **greenfield** entry (build something new). For **brownfield** work — recreate an *existing* feature in another app, or change one in place (swap the vendor behind the scenes, redesign, add a capability) — use **`/transmute`**, which comprehends the existing feature first and then drives the same delivery spine (conjure → blueprint → weave → gateways → seal) behind a parity contract.

Prefer the latest model. Effort: `medium` for implementation turns, `high` for certify/review/security turns (`xhigh` for a big feature's design/review; `max` only as a frontier opt-in); on Bedrock/Vertex/gateways hold one level (a change drops the cache). See [lore/models.md](../../lore/models.md).

## Gates (Human Approval Required)

```
GATE 1: Scope approval
GATE 2: Spec approval (after /conjure)
GATE 3: Plan approval (after /blueprint)
GATE 4: PR title and final go-ahead (before /seal)
```

## Process

**Plan mode for Phases 0–2 (recommended when interactive).** When the main agent has `EnterPlanMode`, enter plan mode before Phase 0 and **exit it (`ExitPlanMode`) before Phase 3**: plan mode blocks writes. A dispatched `/manifest` has no plan mode and runs as before. Caveats: [references/phase-notes.md](references/phase-notes.md#plan-mode-for-phases-02).

### Phase 0: Scope Triage [GATE 1]
1. Ask: "What do you want to build?" (one sentence description). **End your turn. Wait for their answer before assessing anything.**
2. Assess scope — is this one coherent feature or multiple independent subsystems? When `.workspace/shared/north-star.md` exists, read it and check the feature against it. Say so when the feature does not serve it.
3. If too large: help decompose into sub-features, each with its own /manifest cycle
4. Present scope to user, then gate with **AskUserQuestion** — options: **Approve** (proceed to Phase 1), **Revise scope** (adjust the boundaries first), **Split into sub-features** (too big — decompose into separate /manifest cycles). **End your turn at the call; wait for the choice.** Treat a free-form "yes / approved / looks good" as Approve; proceed to Phase 1 only on Approve.
   - On Approve, write the intent file `.workspace/shared/intents/<date>-<feature>.md` from the scope dialogue (format: [references/phase-notes.md](references/phase-notes.md#intent-file-phase-0)). It is committed with the spec, and `/seal` quotes it in the PR body.

### Phase 1: Design [GATE 2]
5. Run /conjure — full design dialogue
   - First, if the feature needs external research (library choice, prior art, API capabilities), run /magic — it saves findings to `.workspace/shared/research/`, which /conjure then reads. Optional; skip when the design is well understood.
6. Write spec to `.workspace/shared/specs/`
7. Gate with **AskUserQuestion** — options: **Approve spec** (proceed to planning), **Request changes** (revise the spec first). **End your turn at the call; wait for the choice.** A free-form "approved / looks good" counts as Approve.

### Phase 2: Planning [GATE 3]
8. Run /blueprint — create the task plan with its parallelism map
9. /blueprint writes `plan.json` and renders `plan.md` (what /orchestrate executes), `plan.html` (the walkthrough) and `plan.workflow.js` into `.workspace/shared/plans/<date>-<feature>/`, then serves the page live (local companion, or a Claude Artifact) when it can
10. **GATE 3 happens where the page is.** When /blueprint runs its live loop, the reviewer's **Approve plan** on the page is the gate: /blueprint prints its Completion Signal only after `plan.approved`, and `plan.rejected` returns this run to GATE 2 (revise the spec with /conjure, then plan again) — do not add a second chat gate on top. When the page is static or the loop paused ("Plan review paused"), gate with **AskUserQuestion** — options: **Approve plan** (proceed to Phase 3), **Request changes** (revise the plan first). **End your turn at the call; wait for the choice. Do NOT proceed to Phase 3 until Approve arrives.** A free-form "approved / looks good" counts as Approve.

### Phase 3: Isolation [GATE 3.5]
(Leave plan mode here if you entered it — the rest of the run writes files.)
11. Propose a branch name derived from the feature (e.g. `feature/<kebab-case-name>`). Gate with **AskUserQuestion** — options: **Create worktree** (isolate on branch `feature/<name>`), **Work in current branch** (no worktree). **End your turn at the call; wait for the choice.**
    - On **Create worktree**: run `/portal <name>` — passes the name directly, no re-prompting
    - On **Work in current branch**: note "working in current branch" and continue

### Phase 4: Implementation
12. **Proceed immediately after Phase 3 without waiting.** Run /orchestrate — it runs the plan's `plan.workflow.js` as one Workflow when present (the `Workflow` approval prompt applies), else executes the waves with parallel agents where safe, sequential where required. For a large multi-item plan (many tickets/features/files), prefer **/weave** to deliver them as one native Workflow with guardrails (TDD per unit, kg grounding, certify, multi-lens review + adversarial verify). For a long **unattended** run, pair with **`/goal`** so Claude keeps driving across turns until the completion condition holds.
13. /ward discipline enforced throughout (TDD)

### Phase 5: Verification
14. Run /certify — tests, types, lint, build, evidence collected

### Phase 6: Review
15. Run /scrutinize — 3 specialist reviewers in parallel, then fix critical/high findings (review + remediation are one skill)

### Phase 7: Ship [GATE 4]
16. Run /certify again — clean state after review fixes
17. Present the proposed PR title, then gate with **AskUserQuestion** — options: **Approve & create PR** (proceed to /seal with this title), **Revise title** (edit it first), **Cancel** (stop before shipping). **End your turn at the call; wait for the choice.** Treat a free-form "approved / ship it" as Approve; proceed to /seal only on Approve.
18. Run /seal — simplify, commit, PR, watch CI, merge

## Autonomous Continuation

After each sub-skill completes and prints its completion signal, **immediately proceed to the next phase**. Do not stop and ask "should I continue?" unless the phase is a defined GATE. Blueprint ending with "Run /orchestrate…" is a signal it is done — manifest continues autonomously from there.

## Reporting

After each phase, brief status: "Phase N complete: <what happened>. Starting Phase N+1."

## Obstacles

Every dispatched skill or agent returns an Obstacles block on a non-clean run. Roll them up into one report for the human, detect patterns by BLOCKER + SCOPE signature, and memorize a confirmed pattern with `ctx learn --add` in your own words, never verbatim worker text and never secrets. Procedure: [references/phase-notes.md](references/phase-notes.md#obstacles-roll-up). See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

"Manifest complete. Feature shipped. Chronicle records this session at stop (unless session history is turned off)."

## On Codex

Read the Claude Code features this skill names as follows on Codex and ChatGPT (full table: [On Codex](../../lore/skill-authoring.md#on-codex)).

- `/goal`: Codex has the same `/goal` command (outcome, constraints and how to verify); one goal per chat.
- `Workflow` fan-out: run one `codex exec --worktree` per independent unit, or use `/worktree` for parallel chats.
- Subagents (`Task`/`Agent`): Codex subagents are `.codex/agents/*.toml` files (`name`, `description`, `developer_instructions`); the review lenses ship here as `*-lens` skills.
- `AskUserQuestion`: Codex has no question form; ask the same question in prose, with the same options, and wait for the reply.
- Skill commands: `/<skill>` is `$<skill>` on Codex and `@<skill>` in ChatGPT.
