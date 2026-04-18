---
name: manifest
description: Full autonomous SDLC — design, plan, implement, review, and ship with 4 human approval gates
keep-coding-instructions: true
---

# /manifest — Full Autonomous SDLC

The complete end-to-end development flow. Four human gates. Everything else runs autonomously.

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
6. Write spec to `.workspace/shared/specs/`
7. **Wait for spec approval.**

### Phase 2: Planning [GATE 3]
8. Run /blueprint — create task plan with parallelism map
9. Write plan to `.workspace/shared/plans/`
10. **Wait for plan approval.**

### Phase 3: Isolation
11. Run /portal — create git worktree (or skip if disableGit)

### Phase 4: Implementation
12. Run /orchestrate — execute all tasks using parallel agents where safe, sequential where required
13. /ward discipline enforced throughout (TDD)

### Phase 5: Verification
14. Run /certify — tests, types, lint, build, evidence collected

### Phase 6: Review
15. Run /scrutinize — 3 specialist reviewers in parallel
16. Run /absorb — fix critical and high findings

### Phase 7: Ship [GATE 4]
17. Run /certify again — clean state after review fixes
18. Ask user for PR title. **Wait for approval.**
19. Run /seal — simplify, commit, PR, monitor CI, merge

## Reporting

After each phase, brief status: "Phase N complete: <what happened>. Starting Phase N+1."

## Completion Signal

"Manifest complete. Feature shipped. Chronicle will record this session at stop."
