---
name: unravel
description: Systematic debugging with a mandatory hypothesis preflight — no code changes before evidence; one change at a time, then a regression test. Use whenever a problem is reported or something misbehaves — "I have a bug / it's broken / not working / crashing", an error/exception/stack trace, a regression, a test failure, or a production issue/outage when the app is deployed. Grounds the investigation with /magic + the knowledge graph (kg query/blast) for comprehensive root-cause research.
allowed-tools: Read, Grep, Glob, Bash
argument-hint: <bug or error description>
---

# /unravel — Systematic Debugging

Debug systematically. No random changes in the hope something helps.

Scale `/effort` to bug complexity — use xhigh for deep, multi-layer root-cause hunts. See [lore/models.md](../../lore/models.md).

<HARD-GATE>
State your hypothesis and evidence BEFORE reading any code or making any change. This prevents the most common AI debugging failure: making changes without understanding the cause.
</HARD-GATE>

## Process

### Phase 1: Hypothesis Preflight
1. **Describe the symptom** — exact error message, stack trace, reproduction steps
2. **State what you believe is wrong** — one sentence: "I believe X is failing because Y"
3. **State what evidence would confirm or refute it**
4. Ask: "Does this hypothesis match what you're seeing, or do you have a different theory?" **End your turn. Do not read any code or make any change until the user agrees or redirects.**

### Phase 2: Evidence Gathering
5. **Read relevant code** — only the code related to the hypothesis. If a knowledge-graph index exists, `kg query "<symptom/error/symbol>"` to jump straight to the relevant `file:line` (and `kg neighbors`/`kg blast` to see what interacts with it) instead of broad greps — then read just those ranges.
6. **Add targeted logging/assertions** if needed — not scattered throughout
7. **Run the failing case** — capture exact output
   - If the bug involves an unfamiliar error, library, or framework behavior, use `/magic` (context7 + web) to gather external evidence — known issues, version-specific bugs, correct API usage — and fold it into the hypothesis ranking in Phase 3.

### Phase 3: Hypothesis Testing
8. **Rank hypotheses** by likelihood based on evidence (most likely first)
9. **Test the most likely hypothesis** — make one change, observe result
10. If refuted, mark it off and test the next

### Phase 4: Fix and Verify
11. **Implement the fix** for the confirmed root cause
12. **Write a regression test** that would have caught this bug
13. **Run full test suite** — no new failures
14. **Commit** with message explaining root cause: `fix: <root cause>, not just symptom` — in auto mode, confirm with the user before committing (the commit is a side effect).

## Anti-Patterns (Never Do These)
- Making 3 changes at once to "see what helps"
- Reading the entire codebase before forming a hypothesis
- Fixing the symptom without understanding the cause
- Skipping the regression test

## Completion Signal

"Root cause confirmed: <explanation>. Fix applied and regression test added. Run /certify."
