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
| Spec complete | graded against [conjure's rubric](../skills/conjure/references/rubric.md), unmet items listed | "the user approved it" |
| Plan complete | graded against [blueprint's rubric](../skills/blueprint/references/rubric.md), unmet items listed | `plan-render check` passed |
| Research complete | graded against [magic's rubric](../skills/magic/references/rubric.md), unmet items listed | "enough sources" |
| Post-mortem complete | graded against [autopsy's rubric](../skills/autopsy/references/rubric.md), unmet items listed | the timeline is written |

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

## Low/medium-effort turns — paste the paragraph, only then

At `low` or `medium` effort the 5.5 models sometimes skip verification before claiming done (Anthropic's
Sonnet 5.5 guidance recommends a system-prompt paragraph that requires a real test/build run). Spawn
prompts and skill steps that run at `low`/`medium` (implementation turns in [ward](../skills/ward/SKILL.md),
[orchestrate](../skills/orchestrate/SKILL.md), [weave](../skills/weave/SKILL.md)) include this paragraph
verbatim:

> Before you report any step as done, fixed or passing, run the real test, build or type-check command
> for it in this turn and read its output. Do not infer the result from the diff or from an earlier run.
> If the command cannot run, say so and report the step as unverified.

Do **not** add it on `high`/`xhigh` runs: there it is the self-verification reminder that
[model-behavior.md](model-behavior.md) forbids — the gates above already demand evidence, and the model
re-checks itself. The paragraph is a floor for cheap turns, not a second gate.

## Language-invariant rigor

The verification bar does not bend to the language of the conversation. Anthropic's research on how
Claude's *expressed* values vary across models & languages found the *same* request **tends to** draw
**more rigor in some languages and more warmth/accommodation in others** — challenging assumptions and
asking for evidence most in English & Russian, warmer and more deferential elsewhere — an unchosen drift
(a tendency, not a guarantee). For a
verification-first plugin that is a bug, not a feature: a review, a security pass, a "is this actually
done?" check, and the willingness to push back on a risky action must be **equally hard in every
language**. Match the user's language for **tone**; never for **standards** — same evidence gate, same
pushback, same honest flagging of uncertainty, whether the conversation is in English or not.
(Anthropic research: anthropic.com/research/claude-values-models-languages.)

## Where this applies

Skills that finish work apply this gate _before_ their completion signal:
[certify](../skills/certify/SKILL.md) is the runnable suite; [seal](../skills/seal/SKILL.md) never
ships on an unverified branch; [ward](../skills/ward/SKILL.md) proves RED→GREEN;
[unravel](../skills/unravel/SKILL.md) proves the original symptom is gone;
[orchestrate](../skills/orchestrate/SKILL.md) trusts the **diff**, not a subagent's report. This is the
discipline behind [certify] — the command is the proof, the claim comes after.
