# Phase C — Shared delivery engine

How a confirmed dossier + approved parity contract become a shipped change. This is the spine both
modes share; the mode deltas ([port-mode.md](port-mode.md), [integrate-mode.md](integrate-mode.md))
only add what's specific. Everything here **reuses existing skills** — `/transmute` orchestrates, it
doesn't reimplement delivery.

Prerequisite: Phase B is approved (SKILL.md HARD-GATE #2). All writes are gated (HARD-GATE #7).

---

## C1 — Design (only if the UX changes)

If the change alters the UI (a redesign, or a port that needs its own look), invoke **`/conjure`** and
hand it the **dossier path**. `/conjure` already reads `.workspace/shared/research/`, produces the
approved spec + `design-tokens.css` + `spec.md`. Skip this for a pure vendor-swap that preserves the
UX — there is nothing to redesign, and G5 will require the UX to stay identical.

## C2 — Plan

Invoke **`/blueprint`** with the **dossier + parity-contract paths** as the spec/requirements input.
It produces a TDD task plan (PARALLEL/SEQUENTIAL map) in `.workspace/shared/plans/`. This
decomposition is what seeds C3's stories and C4's units — it is **not** discarded when tickets are
created; the blueprint tasks *become* the tickets. (For a small PORT with no tickets, the blueprint
plan is consumed directly as the units in C4.)

## C3 — Tickets (INTEGRATE, or on request)

When the user wants the work tracked (the vendor-migration pattern — "create jiras, epics, and
implement all of it"), invoke **`/jira`**: an **epic** + **stories**, each story linked to the epic (and to any
existing epic the user names). `/jira` owns its write gates and its own opt-out. This is optional for
PORT; default-on for a real INTEGRATE initiative.

## C4 — Build via /weave  (the engine + the parity loop)

Invoke **`/weave`** to build the change as ONE native `Workflow` — it already carries the guardrails
(TDD per unit, `kg` grounding, certify, multi-lens review + adversarial verify, write gates, no
context loss) and a terminating evaluator-optimizer remediate loop. `/transmute` adds two things:

**1. Tickets → units (makes "epic → implement all of it" real).** When C3 created stories, populate
`args.units` **from those stories** — `/weave` already pulls ticket detail via `magician:jira`:

```
unit.id = ticket key · unit.goal = the story · unit.accept = the story's AC
```

Pass only the seam `/weave` can't derive from a ticket; **don't pre-compute `kg` scope/blast here** —
`/weave`'s Phase 0 already grounds every unit with `kg query`/`kg blast` for its files + blast radius,
so leave that to it (one place owning the kg contract). When there are no tickets, units come from the
`/blueprint` plan instead.

**2. The parity loop (evaluator-optimizer).** In addition to `/weave`'s review/remediate loop, the
build must satisfy the parity contract. Have the optimizer build, then a **fresh-model evaluator**
diff the candidate against the **behavioral** golden (`<f>-golden/behavioral/` — **never**
environmental) plus the perf/cost budgets, and loop until it passes — bounded by a round cap +
`budget.remaining()` floor so it always terminates. Concretely, extend the weave template
([../../weave/references/template.md](../../weave/references/template.md)) with a parity stage per unit:

- optimizer: implement/adjust the unit (TDD, one commit).
- evaluator (fresh agent, `schema`): given the behavioral golden fixtures + the budgets, return
  `{parity: bool, perf_ok: bool, cost_ok: bool, diffs: [...]}` — comparing **semantics/shapes**, not
  environment.
- loop the unit while `!parity || !perf_ok || !cost_ok` and rounds remain; carry forward unresolved
  units (don't let an unfixed unit vanish into a false "clean").

Runnable shape — **inline the concrete golden path + budgets you already hold from Phase B**; do NOT
make the weave worker re-open the parity file (that would be lower-level rework, HARD-GATE #1):

```javascript
const PARITY = { type:'object', additionalProperties:false, properties:{
  parity:{type:'boolean'}, perf_ok:{type:'boolean'}, cost_ok:{type:'boolean'},
  diffs:{type:'array',items:{type:'string'}} }, required:['parity','perf_ok','cost_ok'] }

const GOLDEN = '.workspace/shared/research/<feature>-golden/behavioral/'  // inlined from Phase B
const BUDGET = { p95: '<ms>', cost: '<per-call>' }                        // inlined from the parity contract
let round = 0, ok = false
while (!ok && round < (args.maxRounds || 3) && (!budget.total || budget.remaining() > 40000)) {
  round++
  const v = await agent(
    `Evaluate unit ${u.id} for BEHAVIORAL parity. Read the golden fixtures at ${GOLDEN} and diff the ` +
    `candidate's input→output SEMANTICS/shapes (NOT domain/IDs/styling). Check p95 ≤ ${BUDGET.p95}, ` +
    `cost ≤ ${BUDGET.cost}. Return {parity,perf_ok,cost_ok,diffs}.`,
    { label:`parity:${u.id}`, phase:'Parity', schema: PARITY })
  log(`parity ${u.id} r${round}: parity=${v?.parity} perf=${v?.perf_ok} cost=${v?.cost_ok}`) // transcript ⇒ /goal can see it
  ok = v && v.parity && v.perf_ok && v.cost_ok
  if (!ok) { /* optimizer: fix against v.diffs (TDD) → re-certify → re-loop */ }
}
```

The `log(...)` line surfaces the verdict to the Workflow transcript so a `/goal` run (C5) reads real
parity evidence.

INTEGRATE cutover specifics (strangler facade, feature flag, parallel-run returning the old path,
canary) are in [integrate-mode.md](integrate-mode.md); PORT target-seam specifics are in
[port-mode.md](port-mode.md).

## C5 — Long unattended run (optional)

For a big migration you want to run across turns unattended:
- **`/goal`** — set the completion condition to the parity contract, e.g. *"every flow reproduces the
  behavioral golden outputs, the full suite exits 0, p95 ≤ budget — or stop after N turns."* The
  `/goal` evaluator is tool-less, so the build MUST **print test / perf / parity evidence to the
  transcript** each turn, or the evaluator can't see progress. Keep it a **compact per-turn summary**
  (pass/fail counts · p95 vs budget · parity-diff count) — full logs stay in `.workspace/` artifacts
  so the transcript doesn't balloon across turns.
- **`/loop [interval]`** — time-paced polling for batch/CI waits. **Honest limit:** on Vertex there's
  no Monitor push, so this is a fixed-interval tick (seconds+), not instant reaction; say so.

---

## Then: gateways → ship

After the build converges, run **Phase D gateways** (SKILL.md — the hard gate), then hand off to
**`/seal`** for the gated ship. Do not emit the completion signal until the applicable gateways are
green. Review the shipped change with `/divine`; if anything went sideways, `/autopsy`.
