# Depth levels, grounding & verification

## The depth gate (AskUserQuestion)

Present these as the options. Phrase the question to reflect the change you found in Phase 0 (e.g. "This is a 30-file, +2969/−323 change touching a GraphQL contract and a decision engine — how deep should I go?").

| Depth | Lenses | `/effort` | Grounding (`/magic`) | Adversarial verify | Best for |
|---|---|---|---|---|---|
| **Quick** | correctness only | low–med | none | criticals only | tiny diffs, a quick sanity pass |
| **Standard** *(default)* | correctness, security, simplification | medium | light (PR desc + in-repo specs) | each Critical/High once | everyday PRs |
| **Deep** | + tests/verifier | high | yes — external docs/domain when unfamiliar | refute every Critical/High | important PRs, security-sensitive, epic MRs |
| **Exhaustive** | all 4, loop-until-dry | xhigh | yes — full PRD/spec/story traceability | multi-vote (≥2 independent) per High+ | epics, migrations, contract changes, releases |

Map the choice onto reasoning effort with `/effort`, and prefer the latest code-optimal model; if the session is on an older model than the depth warrants, **suggest** the upgrade rather than switching silently. See [lore/models.md](../../../lore/models.md).

Scale agent count to depth and diff size, not a fixed number: a 3-file PR at Deep doesn't need 4 agents arguing; a 60-file epic at Exhaustive may warrant per-area finders.

## Grounding via /magic

Review against **external truth**, not assumptions — the difference between "this looks off" and "this violates the documented contract / spec for this interface". Invoke `/magic` (or do focused `context7`/web lookups inline) when the change involves:

- an unfamiliar **framework / library / API** (resolve version-correct behavior — `context7`),
- a **protocol, spec, or domain** you can't review from first principles (payments, auth, addressing, crypto, GraphQL federation…),
- a **security topic** where current CVEs / advisories matter,
- a **PRD / spec / story** the code must satisfy (pull it as a traceability target).

`/magic` saves findings to `.workspace/shared/research/` and returns the artifact path; pass that path into each reviewer's context so the whole panel reviews against the same grounding. If grounding already exists in `.workspace/shared/research/`, read it instead of re-researching.

## Adversarial verification

A finding is a claim; treat it like one. Before it reaches the report, **try to disprove it** against the actual code and the change's intent:

- Re-read the cited `file:line` and enough surrounding code to confirm the issue is real and reachable, not an artifact of reading the diff out of context.
- Check it isn't already handled elsewhere (guard upstream, validation in a caller, a test that covers it).
- Check it against intent — a "missing case" may be deliberately out of scope per the ticket.

Default to **refuted when uncertain**. At Exhaustive depth, get ≥2 independent verdicts per High+ finding (a second `magician:reviewer`/`magician:sentinel` pass, or distinct lenses) and keep only those that survive a majority. List dropped candidates in the report's **✅ Dropped (false positives)** section — showing your work is dropped builds trust, exactly as a strong human reviewer notes "candidates considered and rejected".

## Very large PRs

For sprawling changes (dozens of files), prefer breadth without losing rigor:
- **Agent teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) when reviewers should challenge each other's findings — e.g. competing-hypothesis debate on a subtle bug.
- **Dynamic workflows** ("workflow" in an auto-mode prompt) to fan a finder across 100s of files and double-check results, when one pass can't hold the whole diff.
Otherwise, partition the diff by area and dispatch one finder per area, then consolidate. Whatever you cap, **say so** in the report — never present a partial sweep as complete.
