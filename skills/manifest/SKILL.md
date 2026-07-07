---
name: manifest
description: Full autonomous SDLC — design, plan, implement, review, and ship with 4 human approval gates
disable-model-invocation: true
argument-hint: [one-sentence feature description]
---

# /manifest — Full Autonomous SDLC

The complete end-to-end development flow. Four human gates. Everything else runs autonomously.

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
4. Present scope to user. **End your turn. Wait for explicit approval before proceeding to Phase 1.**

### Phase 1: Design [GATE 2]
5. Run /conjure — full design dialogue
   - First, if the feature needs external research (library choice, prior art, API capabilities), run /magic — it saves findings to `.workspace/shared/research/`, which /conjure then reads. Optional; skip when the design is well understood.
6. Write spec to `.workspace/shared/specs/`
7. **Wait for spec approval.**

### Phase 2: Planning [GATE 3]
8. Run /blueprint — create task plan with parallelism map
9. Write plan to `.workspace/shared/plans/`
10. **Wait for plan approval. Do NOT proceed to Phase 3 until explicit approval arrives.**

### Phase 3: Isolation [GATE 3.5]
11. Propose a branch name derived from the feature (e.g. `feature/<kebab-case-name>`). Ask:
    > "Ready to create a worktree for isolation. I'll use branch `feature/<name>`. Create it now, or work directly on the current branch?"
    **End your turn. Wait for their reply.**
    - If they confirm: run `/portal <name>` — passes the name directly, no re-prompting
    - If they decline: note "working in current branch" and continue

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
