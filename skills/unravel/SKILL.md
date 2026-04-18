---
name: unravel
description: Systematic debugging with mandatory hypothesis preflight — no random code changes
keep-coding-instructions: true
---

# /unravel — Systematic Debugging

Debug systematically. No random changes in the hope something helps.

<HARD-GATE>
State your hypothesis and evidence BEFORE reading any code or making any change. This prevents the most common AI debugging failure: making changes without understanding the cause.
</HARD-GATE>

## Process

### Phase 1: Hypothesis Preflight
1. **Describe the symptom** — exact error message, stack trace, reproduction steps
2. **State what you believe is wrong** — one sentence: "I believe X is failing because Y"
3. **State what evidence would confirm or refute it**
4. Get user agreement before proceeding

### Phase 2: Evidence Gathering
5. **Read relevant code** — only the code related to the hypothesis
6. **Add targeted logging/assertions** if needed — not scattered throughout
7. **Run the failing case** — capture exact output

### Phase 3: Hypothesis Testing
8. **Rank hypotheses** by likelihood based on evidence (most likely first)
9. **Test the most likely hypothesis** — make one change, observe result
10. If refuted, mark it off and test the next

### Phase 4: Fix and Verify
11. **Implement the fix** for the confirmed root cause
12. **Write a regression test** that would have caught this bug
13. **Run full test suite** — no new failures
14. **Commit** with message explaining root cause: `fix: <root cause>, not just symptom`

## Anti-Patterns (Never Do These)
- Making 3 changes at once to "see what helps"
- Reading the entire codebase before forming a hypothesis
- Fixing the symptom without understanding the cause
- Skipping the regression test

## Completion Signal

"Root cause confirmed: <explanation>. Fix applied and regression test added. Run /certify."
