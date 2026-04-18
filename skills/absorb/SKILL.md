---
name: absorb
description: Processes scrutiny findings — triage, fix criticals and highs, document declines with rationale
keep-coding-instructions: true
---

# /absorb — Review Integration

Process the findings from /scrutinize systematically.

## Triage Order

1. **Critical** — fix immediately, do not proceed until resolved
2. **High** — fix before any PR
3. **Medium** — fix if straightforward, document if deferred
4. **Low** — address at discretion, note in PR description

## Process Per Finding

For each finding (Critical and High first):

1. **Read the finding** — understand root cause, not just symptom
2. **Fix it** — use /forge or direct edit as appropriate
3. **Run the affected test** — verify fix works
4. **Run full test suite** — no regressions
5. **Mark resolved** in the findings list

For each declined finding:

Document rationale: "Declined: <reason> — <alternative approach if any>"

## Decline Criteria (when it's acceptable to decline)

- Low-severity suggestion conflicts with team conventions
- Simplification would reduce readability
- Security finding is a false positive (document why)

Never decline Critical or High findings without escalating. When considering declining one, ask: "I'm considering declining [finding] because [reason]. Do you agree, or should I fix it anyway?" **End your turn. Wait for explicit confirmation before declining.**

## Summary Report

After all findings processed:
```
=== ABSORB SUMMARY ===
Fixed:    N (list)
Deferred: N (list with rationale)
Declined: N (list with rationale)

Run /certify to verify clean state.
```

## Completion Signal

"Absorb complete. All critical/high findings resolved. Run /certify, then /seal."
