---
name: unravel
description: Systematic debugging with a mandatory hypothesis preflight — no code changes before evidence; one change at a time, then a regression test. Use whenever a problem is reported or something misbehaves — "I have a bug / it's broken / not working / crashing", an error/exception/stack trace, a regression, a test failure, or a production issue/outage when the app is deployed. Grounds the investigation with /magic + the knowledge graph (kg query/blast) for comprehensive root-cause research.
allowed-tools: Read, Grep, Glob, Bash, Monitor, AskUserQuestion
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
4. **Hypothesis gate (AskUserQuestion).** Put the hypothesis to the user via **AskUserQuestion** (never bare prose) — "Does this hypothesis match what you're seeing?":
   - **Matches — investigate** *(default)* — the hypothesis fits; proceed to Phase 2 and run Phases 2–4 autonomously.
   - **Different theory** — you have another explanation; share it and I'll re-state the hypothesis before touching anything.

   **End your turn at the tool call. Do not read any code or make any change until the user picks or redirects.** Treat a free-form "yes / matches / looks right" as **Matches — investigate**.

### Autonomy — approve the plan, then run

Once the hypothesis is agreed at the Phase 1 gate, run Phases 2–4 **autonomously**: reading code, `grep`, `kg query`/`blast`/`neighbors`, adding targeted logging, running the failing case (incl. under Monitor), and running the test suite NEVER pause for permission. Re-gate **only** on the real side effect — the **commit** (`git add`/`commit`/`push`, per Phase 4). This does not weaken the Phase 1 HARD-GATE. See [lore/autonomy.md](../../lore/autonomy.md).

### Phase 2: Evidence Gathering
5. **Read relevant code** — only the code related to the hypothesis. If a knowledge-graph index exists, `kg query "<symptom/error/symbol>"` to jump straight to the relevant `file:line` (and `kg neighbors`/`kg blast` to see what interacts with it) instead of broad greps — then read just those ranges.
   - **Read the error and stack trace in full first** — before opening any file. The trace usually names the failing `file:line` and often the fix itself; the top frame shows where it blew up, but the first frame in your own code is usually the real culprit. Feed that symbol straight into `kg query`.
6. **Add targeted logging/assertions** if needed — not scattered throughout
   - In a **multi-component system** (CI → build → sign, api → service → db), instrument each component boundary — log what enters and exits every hop — and run the reproduction **once** to locate exactly where the flow breaks before changing anything. Fix where it actually breaks, not the first place you suspect.
7. **Run the failing case** — capture exact output
   - **Reproduce it consistently before proposing a fix** — pin down the exact steps or inputs that trigger it every time. A bug you can't reproduce on demand isn't understood yet, and a fix for it is a guess you can't verify.
   - For an intermittent or async bug, run the reproduction under the **Monitor tool** so the failing event (a 5xx, a crash, a specific log line) streams back the moment it happens instead of tailing by hand.
   - If the bug involves an unfamiliar error, library, or framework behavior, use `/magic` (context7 + web) to gather external evidence — known issues, version-specific bugs, correct API usage — and fold it into the hypothesis ranking in Phase 3.

### Phase 3: Hypothesis Testing
8. **Rank hypotheses** by likelihood based on evidence (most likely first)
9. **Test the most likely hypothesis** — make one change, observe result
10. If refuted, mark it off and test the next

### Phase 4: Fix and Verify
11. **Implement the fix** for the confirmed root cause
    - **Re-run the ORIGINAL failing symptom** — the exact command or steps from Phase 1 — and confirm it no longer reproduces. A fix isn't done until the symptom you started with is re-run and gone; code changed is not the same as bug fixed. See [lore/verification.md](../../lore/verification.md).
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
