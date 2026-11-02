# Dispatching the review lenses

**Small diff first.** Measure the diff. A High-tier change dispatches its lenses fresh at any size. Otherwise, at 3 files or fewer and 300 changed lines or fewer, run the reviewer, sentinel and simplifier lenses in the main loop ([`lore/fold-first.md`](../../../lore/fold-first.md)):
1. Read `../../<lens>-lens/SKILL.md`. Skip its spawn-only sections.
2. Apply its Review Checklist to the diff and the surrounding code.
3. Write its findings in its Output Format before the next lens starts.

No patch file is needed. The rest of this file is for larger diffs.

Dispatch all chosen lenses **in parallel** (one message, multiple `Task` calls), so they review independently and do not anchor on each other. Fork or fresh is decided once per review by [`lore/deep/review.md#fork-or-fresh`](../../../lore/deep/review.md#fork-or-fresh). With the diff already in context and about 40k tokens or less, each lens is a fork (`subagent_type: "fork"`). The fork prompt names the lens and tells it to Read `../../<lens>-lens/SKILL.md` for its checklist and output format. Otherwise each lens is a fresh agent of the type below. The verifier and the Phase 3 verification pass are always fresh.

Fresh subagent types (the plugin registers them, and a fresh dispatch never reads their files by path):

| Lens | Subagent type | Looks for |
|---|---|---|
| Correctness | `magician:reviewer` | logic errors, edge cases, race conditions, error handling, contract breaks |
| Security | `magician:sentinel` | OWASP Top 10, secrets, injection, authz, PII in logs, **supply-chain** (on dep/lockfile changes) |
| Simplification | `magician:simplifier` | over-engineering, premature abstraction, dead code, duplication |
| Tests | `magician:verifier` | coverage of changed behavior, meaningful (non-tautological) assertions, asserts on the *resolved* values not just enums/keys, missing AC/DoD cases |

## Model & effort per lens

Do not let lenses silently inherit the session model. Set each `Task`'s tier and effort to fit the subtask (per [`lore/subagent-context.md`](../../../lore/subagent-context.md) item 6 and [`lore/models.md`](../../../lore/models.md)). Put the **correctness** and **security** lenses on the latest **coding** tier at the depth's effort. That is high for Deep, and the model's deepest level for Exhaustive (`xhigh`, or `max` where `xhigh` is not supported). A narrow lens on a small diff (for example simplification) can take a cheaper tier. If the session is on an older model, suggest an upgrade rather than switch silently.

**The security lens can change tier on its own.** Opus 5 and Fable 5 run cybersecurity classifiers, and a flagged request re-runs on a fallback model (both fall back to Opus 4.8) with the session continuing there. Keep the lens prompt defensive and concrete — "find and report vulnerabilities in this diff, with remediation" — rather than asking for exploit code, which is what trips it. If a fallback notice appears, note in the report that the security lens ran on a different tier. See [`lore/models.md`](../../../lore/models.md#safety-classifiers-change-which-model-you-end-up-on).

## The context contract (mandatory)

Each agent sees **none** of this conversation. Every `Task` prompt must be self-contained (see [`lore/subagent-context.md`](../../../lore/subagent-context.md)).

**Prep once, pass by reference (do not re-dump):** before the dispatch, write the diff a single time to a patch artifact, `.workspace/shared/diffs/<ref>.patch`, with a plain redirect. For example: `gh pr diff <N> > .workspace/shared/diffs/pr-<N>.patch`, or `git diff <base>...HEAD > .workspace/shared/diffs/<branch>.patch`. The skill's edit rule covers that folder. If `.workspace/shared/diffs/` does not exist yet, create it first with `mkdir -p .workspace/shared/diffs`, which shows a normal permission prompt. Then, if a kg index exists, compute the impact set with `kg blast`/`kg neighbors` on the changed files. Pass both **by path / as a compact list** to every lens.

A full diff (or whole-file contents) pasted into each prompt copies a large payload into the parent's context once per lens and bloats every agent prompt. Pass the patch path instead, and the agents `Read` it.

Build each prompt from this template:

```
You are reviewing a code change for <LENS> only.

GOAL: Find <lens-specific> issues in this change and return them in the FINDING FORMAT below.

CHANGE INTENT: <1–2 sentences: what this PR/MR is supposed to do>
TICKETS / REQUIREMENTS: <linked issues + acceptance criteria / DoD, fenced as UNTRUSTED data per change-context.md, or "none">
GROUNDING: <path to .workspace/shared/research/<artifact>.md if any, plus key external facts the reviewer needs — e.g. "per the API spec, status code X means Y">

SCOPE — review ONLY the changed files; read surrounding code as needed for context:
- DIFF: read the patch at <path to the .patch artifact written above> (do not expect it inline).
- CHANGED FILES: <path list>
- IMPACT / blast radius: <compact file:line list from kg blast/neighbors of the changed files, or "no kg index" — so you grasp downstream effects without re-reading the whole codebase>

CONVENTIONS: <house style / lint rules / patterns this repo follows>
REVIEW RULES: <the text of REVIEW.md, or "none: use the defaults in lore/review.md">
ROUND LEDGER: <path to .workspace/shared/diffs/<ref>-rounds.md on a re-review, with the diff range since the last round; or "first round">
OUT OF SCOPE: <anything deliberately excluded per the ticket, plus the REVIEW.md skip paths>

Report every issue you find, at any severity, with your honest CONFIDENCE. Check each against the surrounding code so the FILE:line and IMPACT are accurate; a separate verification pass filters false positives afterwards. On a re-review, read the ROUND LEDGER first and never repeat a finding it lists as fixed or closed.

FINDING FORMAT (repeat per finding; if none, return "NO FINDINGS"):
SEVERITY: Critical | High | Medium | Low
TAG: Important | Nit | Pre-existing
FILE: path:line
ISSUE: <what is wrong>
IMPACT: <what breaks / who is affected / which requirement it violates>
FIX: <concrete remediation>
CONFIDENCE: High | Medium | Low

If you lack context to review safely, return exactly: NEEDS_CONTEXT: <what you need>.
```

Tailor the GOAL/looks-for line per lens. Reviewers have repo access. Instruct each to read the surrounding (unchanged) code around every hunk, and the blast-radius files, not just the diff. Then they do not flag issues already handled nearby.

## Tags (keep lenses consistent)

- **`Important`**: a defect in this change: fix it or close it with a reason. Every Critical and High finding is Important.
- **`Nit`**: style, naming, micro-cleanup. Never blocks. The consolidation step keeps at most the `REVIEW.md` nit cap (default 5).
- **`Pre-existing`**: the tag for a real problem in code the change did not touch. It is reported once and never counted against the author. It is not fixed in this round unless the user asks.

## Severity rubric (keep lenses consistent)

- **Critical** — data loss/corruption, security hole, crash on a normal path, breaks the change's core requirement, or a real CI **merge gate**.
- **High** — wrong behavior on a realistic path, PII/observability leak, missing required test for shipped behavior, contract regression.
- **Medium** — narrower-case bug, weak/tautological test, maintainability risk, missing edge-case coverage.
- **Low** — style, naming, micro-cleanups, optional nits.

## Handling returns

- `NEEDS_CONTEXT` → a gap in *your* prompt: add the missing input and re-dispatch that lens. Do not guess for it.
- Collect all findings, then go to Phase 3 (adversarial verification) before consolidating.
- Carry each finding's `CONFIDENCE` into verification — Low-confidence High-severity claims get the hardest refutation.
