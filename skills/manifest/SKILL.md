---
name: manifest
description: Full autonomous SDLC — design, plan, implement, review, and ship with 4 human approval gates
disable-model-invocation: true
argument-hint: [one-sentence feature description]
---

# /manifest — Full Autonomous SDLC

The complete end-to-end development flow. Four human gates. Everything else runs autonomously.

**Autonomy is the point: gather → plan → memorize → execute.** The human approves the gates below, **not each file read.** Ground via `kg` (not broad grep), memorize the plan + requirements + `kg` pointers + standards to `.workspace/`, and execute the whole plan without prompting per read/search — reads/searches/read-only git are auto-approved (`magician-ui allow`); only writes/commit/push/PR/ticket/destructive ops gate. If you're bombarding the owner with "can I read this?" the run is broken. See [lore/autonomy.md](../../lore/autonomy.md).

`/manifest` is the **greenfield** entry (build something new). For **brownfield** work — recreate an *existing* feature in another app, or change one in place (swap the vendor behind the scenes, redesign, add a capability) — use **`/transmute`**, which comprehends the existing feature first and then drives the same delivery spine (conjure → blueprint → weave → gateways → seal) behind a parity contract.

A full SDLC run is large — prefer the latest model and a high reasoning effort (`/effort high`, or `xhigh` for big features). If the session is on an older model, suggest upgrading before starting. See [lore/models.md](../../lore/models.md).

## Gates (Human Approval Required)

```
GATE 1: Scope approval
GATE 2: Spec approval (after /conjure)
GATE 3: Plan approval (after /blueprint)
GATE 4: PR title and final go-ahead (before /seal)
```

## Process

### Phase 0: Scope Triage [GATE 1]
1. Ask: "What do you want to build?" (one sentence description). **End your turn. Wait for their answer before assessing anything.**
2. Assess scope — is this one coherent feature or multiple independent subsystems?
3. If too large: help decompose into sub-features, each with its own /manifest cycle
4. Present scope to user, then gate with **AskUserQuestion** — options: **Approve** (proceed to Phase 1), **Revise scope** (adjust the boundaries first), **Split into sub-features** (too big — decompose into separate /manifest cycles). **End your turn at the call; wait for the choice.** Treat a free-form "yes / approved / looks good" as Approve; proceed to Phase 1 only on Approve.

### Phase 1: Design [GATE 2]
5. Run /conjure — full design dialogue
   - First, if the feature needs external research (library choice, prior art, API capabilities), run /magic — it saves findings to `.workspace/shared/research/`, which /conjure then reads. Optional; skip when the design is well understood.
6. Write spec to `.workspace/shared/specs/`
7. Gate with **AskUserQuestion** — options: **Approve spec** (proceed to planning), **Request changes** (revise the spec first). **End your turn at the call; wait for the choice.** A free-form "approved / looks good" counts as Approve.

### Phase 2: Planning [GATE 3]
8. Run /blueprint — create task plan with parallelism map
9. Write plan to `.workspace/shared/plans/`
10. Gate with **AskUserQuestion** — options: **Approve plan** (proceed to Phase 3), **Request changes** (revise the plan first). **End your turn at the call; wait for the choice. Do NOT proceed to Phase 3 until Approve arrives.** A free-form "approved / looks good" counts as Approve.

### Phase 3: Isolation [GATE 3.5]
11. Propose a branch name derived from the feature (e.g. `feature/<kebab-case-name>`). Gate with **AskUserQuestion** — options: **Create worktree** (isolate on branch `feature/<name>`), **Work in current branch** (no worktree). **End your turn at the call; wait for the choice.**
    - On **Create worktree**: run `/portal <name>` — passes the name directly, no re-prompting
    - On **Work in current branch**: note "working in current branch" and continue

### Phase 4: Implementation
12. **Proceed immediately after Phase 3 without waiting.** Run /orchestrate — execute all tasks using parallel agents where safe, sequential where required. For a large multi-item plan (many tickets/features/files), prefer **/weave** to deliver them as one native Workflow with guardrails (TDD per unit, kg grounding, certify, multi-lens review + adversarial verify). For a long **unattended** run, pair with **`/goal`** so Claude keeps driving across turns until the completion condition holds.
13. /ward discipline enforced throughout (TDD)

### Phase 5: Verification
14. Run /certify — tests, types, lint, build, evidence collected

### Phase 6: Review
15. Run /scrutinize — 3 specialist reviewers in parallel, then fix critical/high findings (review + remediation are one skill)

### Phase 7: Ship [GATE 4]
16. Run /certify again — clean state after review fixes
17. Ask user for PR title. **Wait for approval.**
18. Run /seal — simplify, commit, PR, monitor CI, merge

## Autonomous Continuation

After each sub-skill completes and prints its completion signal, **immediately proceed to the next phase**. Do not stop and ask "should I continue?" unless the phase is a defined GATE. Blueprint ending with "Run /orchestrate…" is a signal it is done — manifest continues autonomously from there.

## Reporting

After each phase, brief status: "Phase N complete: <what happened>. Starting Phase N+1."

## Completion Signal

"Manifest complete. Feature shipped. Chronicle will record this session at stop."
