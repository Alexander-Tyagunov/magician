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

Each agent sees **none** of this conversation. Every `Task` prompt must be self-contained (see [lore/subagent-context.md](../../../lore/subagent-context.md)). Build each prompt from this template:

```
You are reviewing a code change for <LENS> only.

GOAL: Find <lens-specific> issues in this change and return them in the FINDING FORMAT below.

CHANGE INTENT: <1–2 sentences: what this PR/MR is supposed to do>
TICKETS / REQUIREMENTS: <linked issues + acceptance criteria / DoD, or "none">
GROUNDING: <path to .workspace/shared/research/<artifact>.md if any, plus key external facts the reviewer needs — e.g. "per the API spec, status code X means Y">

SCOPE — changed files (review ONLY these; read surrounding code as needed for context):
<for each file: path, and its diff hunks; for heavily-changed files, the full current contents>

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

Tailor the GOAL/looks-for line per lens. Keep SCOPE complete — a reviewer that only sees a diff hunk will flag issues already handled in the unchanged surrounding lines.

## Severity rubric (keep lenses consistent)

- **Critical** — data loss/corruption, security hole, crash on a normal path, breaks the change's core requirement, or a real CI **merge gate**.
- **High** — wrong behavior on a realistic path, PII/observability leak, missing required test for shipped behavior, contract regression.
- **Medium** — narrower-case bug, weak/tautological test, maintainability risk, missing edge-case coverage.
- **Low** — style, naming, micro-cleanups, optional nits.

## Handling returns

- `NEEDS_CONTEXT` → a gap in *your* prompt: add the missing input and re-dispatch that lens. Don't guess for it.
- Collect all findings, then go to Phase 3 (adversarial verification) before consolidating.
- Carry each finding's `CONFIDENCE` into verification — Low-confidence High-severity claims get the hardest refutation.
