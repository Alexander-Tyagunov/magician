# Depth levels, grounding & verification

## The depth gate (AskUserQuestion)

Present these as the options. Phrase the question to reflect the change you found in Phase 0 (for example "This is a 30-file, +2969/−323 change touching a GraphQL contract and a decision engine — how deep should I go?").

| Depth | Lenses | `/effort` | Grounding (`/magic`) | Adversarial verify | Best for |
|---|---|---|---|---|---|
| **Quick** | correctness only | low–med | none | criticals only (in the main loop on a small diff) | tiny diffs, a quick sanity pass |
| **Standard** *(default)* | correctness, security, simplification | medium | light (PR desc + in-repo specs) | each Critical/High once | everyday PRs |
| **Deep** | + tests/verifier | high | yes — external docs/domain when unfamiliar | refute every Critical/High | important PRs, security-sensitive, epic MRs |
| **Exhaustive** | all 4, loop-until-dry | deepest (`xhigh`, else `max`) | yes — full PRD/spec/story traceability | multi-vote (≥2 independent) per High+ | epics, migrations, contract changes, releases |

The risk tier in `REVIEW.md` sets the floor: a High-tier change (auth, payments, migrations, CI workflow files, secrets) gets **Deep** at least, with the verification stage in a fresh context ([`lore/review.md`](../../../lore/review.md)). The tier comes from the paths the change touches, never from the author.

Map the choice onto reasoning effort with `/effort`, and prefer the latest coding model. If the session is on an older model than the depth warrants, **suggest** the upgrade rather than switch silently. See [`lore/models.md`](../../../lore/models.md).

Scale agent count to depth and diff size, not a fixed number. A 3-file PR at Deep does not need 4 agents, and a 60-file epic at Exhaustive may warrant per-area finders.

**Small diffs stay inline.** Measure the diff first (`git diff --shortstat`, or the PR's `changedFiles`, `additions` and `deletions`). At 3 files or fewer and 300 changed lines or fewer, the reviewer, sentinel and simplifier lenses run in the main loop ([`lore/fold-first.md`](../../../lore/fold-first.md)). Each one uses `agents/<lens>.md` as a checklist. Verification on that path:
- **Quick:** no agent runs. The adversarial check below runs in the main loop. The report says `Verification: in-loop (Quick, small diff)` and offers a Standard re-run for a fresh check.
- **Standard or deeper:** the adversarial check runs in one fresh agent when there is a Critical or High finding to refute. The verifier lens (Deep and Exhaustive) is a fresh agent.
- **A High-tier change** per `REVIEW.md` gets Deep, so its verification is always fresh. A High-tier change dispatches its lenses fresh at any size.

## Grounding via /magic

Review against **external truth**, not assumptions: the difference between "this looks off" and "this violates the documented contract / spec for this interface". Invoke `/magic`, or do focused `context7` or web lookups inline (`context7` is pre-approved when installed, and a web search or page fetch shows Claude Code's normal permission prompt), when the change involves:

- an unfamiliar **framework / library / API** (resolve version-correct behavior — `context7`),
- a **protocol, spec, or domain** you cannot review from first principles (payments, auth, addressing, crypto, GraphQL federation…),
- a **security topic** where current CVEs / advisories matter,
- a **PRD / spec / story** the code must satisfy (pull it as a traceability target).

`/magic` saves findings to `.workspace/shared/research/` and returns the artifact path. Pass that path into each reviewer's context so the whole panel reviews against the same grounding. If grounding already exists in `.workspace/shared/research/`, read it instead of re-researching.

## Blast radius via the knowledge graph

A change is not just the lines in the diff — it is everything that depends on them. At **Deep/Exhaustive** (or any change touching shared/core code), establish the impact set with the knowledge graph instead of guessing:

- `kg check` — if there is an index, for each changed file run `kg blast <file>` to get the transitive dependents (ranked by centrality), and `kg neighbors <file>` for direct callers/imports.
- Feed those `file:line` lists into each reviewer subagent's context. The whole panel shares the same on-disk artifact, so nobody re-explores and there is no context loss. A High-severity finding in a file with a wide blast radius is more urgent than one in a leaf.
- No index (or the user opted out, [`lore/integration-prefs.md`](../../../lore/integration-prefs.md) key `knowledge-graph`) → fall back to `Grep` for references, and offer `kg init` once. Treat any `⚠ stale` flag as a cue to `kg refresh` before trusting the impact set. Details: [knowledge-graph skill](../../knowledge-graph/references/retrieval.md).

## Adversarial verification

A finding is a claim. Treat it like one. Before it reaches the report, **try to disprove it** against the actual code and the change's intent:

- Re-read the cited `file:line` and enough surrounding code to confirm the issue is real and reachable. A diff read out of context produces artifacts.
- Check it is not already handled elsewhere (guard upstream, validation in a caller, a test that covers it).
- Check it against intent — a "missing case" may be deliberately out of scope per the ticket.

In the main loop (Quick on a small diff), do the same three checks against the code, not against your memory of the finding. Default to **refuted when uncertain**. At Exhaustive depth, get ≥2 independent verdicts per High+ finding (a second `magician:reviewer`/`magician:sentinel` pass, or distinct lenses). Keep only those that survive a majority. List dropped candidates in the report's **✅ Dropped (false positives)** section. A visible list of dropped work builds trust, exactly as a strong human reviewer notes "candidates considered and rejected".

## Very large PRs

For sprawling changes (dozens of files), prefer breadth without losing rigor:
- **Agent teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) when reviewers should challenge each other's findings — for example competing-hypothesis debate on a subtle bug.
- **Dynamic workflows** ("workflow" in an auto-mode prompt) to fan a finder across 100s of files and double-check results, when one pass cannot hold the whole diff.
Otherwise, partition the diff by area and dispatch one finder per area, then consolidate. Whatever you cap, **say so** in the report — never present a partial sweep as complete.
