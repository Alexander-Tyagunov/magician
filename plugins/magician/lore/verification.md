# Verification — evidence over claims (never say "done" without proof)

A completion claim without fresh evidence is a lie, not efficiency. The most expensive bug is the one
you reported as fixed. This is a HARD discipline for every skill that finishes work.

## The rule

**No "done / fixed / passing / ready" without a verification command run in _this turn_ whose output
you read.** If you haven't run it since the last change, you cannot claim it. Wording games don't
exempt it — "looks correct" is a claim.

## The gate — before any success claim

1. **Name** the command that would prove the claim.
2. **Run** it fresh and complete — not a subset, not a remembered result.
3. **Read** the whole output: exit code, failure count, the actual assertion.
4. **State** the claim _with_ the evidence, or state the real status.

## Evidence table — what each claim actually requires

| Claim | Proof required (this run) | NOT enough |
|---|---|---|
| Tests pass | test command output: 0 failures | "should pass", a prior run |
| Types / lint clean | tool output: 0 errors | a partial check, extrapolation |
| Build succeeds | build exits 0 | "lint passed", logs look fine |
| Bug fixed | the original failing case now passes | code changed, assumed fixed |
| Regression test works | watched it fail RED, then pass GREEN | it passed once |
| **A subagent's task is done** | **the VCS diff shows the change** | **the agent reported "success"** |
| Requirements met | checked line-by-line against the spec | tests are green |
| Feature works | drove the real flow ([verify]/[run]) | unit tests only |

## Red flags — STOP and verify

"should", "probably", "seems to", "looks correct"; celebrating before running ("Great!", "Done!",
"Perfect!"); about to commit / push / open a PR without a fresh run; trusting a subagent's self-report;
"just this once"; tired and wanting it over.

## Rationalizations → reality

| Excuse | Reality |
|---|---|
| "should work now" | run it |
| "I'm confident" | confidence ≠ evidence |
| "the agent said success" | verify with the diff |
| "linter passed" | linter ≠ compiler ≠ tests |
| "partial check is enough" | partial proves nothing |
| "just this once" | no exceptions |

## Where this applies

Skills that finish work apply this gate _before_ their completion signal:
[certify](../source-skills/certify/SKILL.md) is the runnable suite; [seal](../source-skills/seal/SKILL.md) never
ships on an unverified branch; [ward](../source-skills/ward/SKILL.md) proves RED→GREEN;
[unravel](../source-skills/unravel/SKILL.md) proves the original symptom is gone;
[orchestrate](../source-skills/orchestrate/SKILL.md) trusts the **diff**, not a subagent's report. This is the
discipline behind [certify] — the command is the proof, the claim comes after.
