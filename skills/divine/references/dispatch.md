# Dispatching the review lenses

Dispatch all chosen lenses **in parallel** — one message, multiple `Task` calls — so they review independently and don't anchor on each other. Subagent types (registered by the plugin; never read their files by path):

| Lens | Subagent type | Looks for |
|---|---|---|
| Correctness | `magician:reviewer` | logic errors, edge cases, race conditions, error handling, contract breaks |
| Security | `magician:sentinel` | OWASP Top 10, secrets, injection, authz, PII in logs, **supply-chain** (on dep/lockfile changes) |
| Simplification | `magician:simplifier` | over-engineering, premature abstraction, dead code, duplication |
| Tests | `magician:verifier` | coverage of changed behavior, meaningful (non-tautological) assertions, asserts on the *resolved* values not just enums/keys, missing AC/DoD cases |

## Model & effort per lens

Don't let lenses silently inherit the session model — set each `Task`'s tier and effort to fit the subtask (per [lore/subagent-context.md](../../../lore/subagent-context.md) item 6 and [lore/models.md](../../../lore/models.md)). Put the **correctness** and **security** lenses on the latest **coding-optimal** tier at the depth's effort (high/xhigh for Deep/Exhaustive); a narrow lens on a small diff (e.g. simplification) can take a cheaper tier. Suggest a model upgrade rather than switching silently if the session is on an older one.

## The context contract (mandatory)

Each agent sees **none** of this conversation. Every `Task` prompt must be self-contained (see [lore/subagent-context.md](../../../lore/subagent-context.md)).

**Prep once, pass by reference (don't re-dump):** before dispatching, write the diff a single time to a patch artifact (`.workspace/shared/diffs/<ref>.patch` if `.workspace/` exists, else `"$(git rev-parse --git-dir)/magician-review.patch"`) and — if a kg index exists — compute the impact set with `kg blast`/`kg neighbors` on the changed files. Pass both **by path / as a compact list** to every lens. Pasting the full diff (or whole-file contents) into each prompt copies a large payload into the parent's context once per lens and bloats every agent prompt — pass the patch path instead; agents `Read` it.

Build each prompt from this template:

```
You are reviewing a code change for <LENS> only.

GOAL: Find <lens-specific> issues in this change and return them in the FINDING FORMAT below.

CHANGE INTENT: <1–2 sentences: what this PR/MR is supposed to do>
TICKETS / REQUIREMENTS: <linked issues + acceptance criteria / DoD, or "none">
GROUNDING: <path to .workspace/shared/research/<artifact>.md if any, plus key external facts the reviewer needs — e.g. "per the API spec, status code X means Y">

SCOPE — review ONLY the changed files; read surrounding code as needed for context:
- DIFF: read the patch at <path to the .patch artifact written above> (do not expect it inline).
- CHANGED FILES: <path list>
- IMPACT / blast radius: <compact file:line list from kg blast/neighbors of the changed files, or "no kg index" — so you grasp downstream effects without re-reading the whole codebase>

CONVENTIONS: <house style / lint rules / patterns this repo follows>
OUT OF SCOPE: <anything deliberately excluded per the ticket>

For each issue, verify it is real and reachable before reporting it. Default to NOT reporting if uncertain.

FINDING FORMAT (repeat per finding; if none, return "NO FINDINGS"):
SEVERITY: Critical | High | Medium | Low
FILE: path:line
ISSUE: <what is wrong>
IMPACT: <what breaks / who is affected / which requirement it violates>
FIX: <concrete remediation>
CONFIDENCE: High | Medium | Low

If you lack context to review safely, return exactly: NEEDS_CONTEXT: <what you need>.
```

Tailor the GOAL/looks-for line per lens. Reviewers have repo access — instruct each to read the surrounding (unchanged) code around every hunk (and the blast-radius files), not just the diff, so they don't flag issues already handled nearby.

## Severity rubric (keep lenses consistent)

- **Critical** — data loss/corruption, security hole, crash on a normal path, breaks the change's core requirement, or a real CI **merge gate**.
- **High** — wrong behavior on a realistic path, PII/observability leak, missing required test for shipped behavior, contract regression.
- **Medium** — narrower-case bug, weak/tautological test, maintainability risk, missing edge-case coverage.
- **Low** — style, naming, micro-cleanups, optional nits.

## Handling returns

- `NEEDS_CONTEXT` → a gap in *your* prompt: add the missing input and re-dispatch that lens. Don't guess for it.
- Collect all findings, then go to Phase 3 (adversarial verification) before consolidating.
- Carry each finding's `CONFIDENCE` into verification — Low-confidence High-severity claims get the hardest refutation.
