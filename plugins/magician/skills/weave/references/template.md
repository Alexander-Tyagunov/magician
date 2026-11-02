# /weave — Workflow template (copy and adapt)

This is the magician-grade delivery pipeline as a native `Workflow` script. Adapt the
`UNITS` list and the prompts to the task; keep the guardrails. Pass it to the `Workflow`
tool as `{script: "..."}`. It mirrors the shape an agent reaches for by hand (sequential
TDD per unit → certify → parallel multi-lens review → adversarial verify → bounded remediate loop → consolidate), but with kg grounding, self-contained prompts, write gates, and a terminating evaluator-optimizer loop built in.

Key API reminders: `meta` must be a pure literal; `agent(prompt, {label, phase, schema, stallMs, model, effort, agentType, isolation})`; `pipeline(items, ...stages)` (no barrier); `parallel(thunks)` (barrier); `phase()`, `log()`. `Date.now()`/`Math.random()` are unavailable — vary by index. Worktree isolation only when parallel agents mutate files.

**Return budgets.** Every `agent()` carries a `schema` whose strings have a `maxLength` (summary ≤ 1200 chars, evidence ≤ 2000, each finding ≤ 600) plus `files_changed[]` and `obstacles[]` (the 8 fields of [lore/obstacles.md](../../../lore/obstacles.md)), so the orchestrator receives distilled results, never raw logs; the runtime validates the JSON (`MAX_STRUCTURED_OUTPUT_RETRIES`). `label` names each agent in the run view; `stallMs` is its per-agent silence budget before a restart.

**Fan-out and the prompt cache.** Siblings of a `parallel()` are held up to `CLAUDE_CODE_WORKFLOW_PREFIX_STAGGER_MS` (default 5000) so they read the first agent's cached prefix; keep the shared part of a prompt (conventions, repo pointers, the return contract) *first* and the per-unit part *last*, and leave the stagger at its default unless the siblings share no prefix. Effort: `medium` for implementation turns, `high` for certify/review/security turns; on Bedrock/Vertex/gateways hold one level (an effort change drops the cache there).

```javascript
export const meta = {
  name: 'weave-delivery',
  description: 'Deliver N units with TDD, certify, multi-lens review + adversarial verify',
  phases: [
    { title: 'Implement', detail: 'sequential TDD per unit, one commit each' },
    { title: 'Certify',   detail: 'tests/types/lint/build per unit' },
    { title: 'Review',    detail: 'parallel multi-lens per unit' },
    { title: 'Verify',    detail: 'adversarially refute every Critical/High' },
    { title: 'Remediate', detail: 'bounded loop: fix confirmed → re-certify → re-review until clean' },
    { title: 'Consolidate', detail: 'report; commits surfaced; no push (write-gated)' },
  ],
}

// FILL THIS IN from Phase 0: each unit is self-describing, with kg-scoped pointers.
// (Pass file:line pointers from `kg query`/`kg blast`, NOT file contents.)
const UNITS = args && args.units ? args.units : [
  // { id: 'TICKET-1', goal: '...', accept: 'Gherkin AC / DoD', scope: 'src/a.ts:120-180, src/b.ts', impact: 'kg blast → src/c.ts' },
]

// Return budgets: every string is bounded so the orchestrator never receives raw logs or
// pasted files — a worker distills (summary ≤ 1200 chars, evidence ≤ 2000) and the runtime
// enforces the schema (JSON validated, up to MAX_STRUCTURED_OUTPUT_RETRIES attempts).
const S = (n) => ({ type:'string', maxLength:n })
const OBSTACLE = { type:'object', additionalProperties:false,   // lore/obstacles.md, 8 fields
  properties:{ STATUS:{ type:'string', enum:['BLOCKED','DEGRADED','NEEDS_CONTEXT'] }, OBSTACLE:S(200),
    BLOCKER:S(400), SEVERITY:{ type:'string', enum:['Critical','High','Medium','Low'] }, WORKAROUND:S(400),
    RECURRENCE:{ type:'string', enum:['First-seen','Recurring','Systemic'] }, SCOPE:S(200), NEXT:S(300) },
  required:['STATUS','OBSTACLE','BLOCKER','SEVERITY','RECURRENCE','SCOPE','NEXT'] }
const OBSTACLES = { type:'array', maxItems:8, items: OBSTACLE }   // empty on a clean run
const FILES = { type:'array', maxItems:200, items:S(300) }
const IMPL = { type:'object', additionalProperties:false,
  properties:{ unit:S(80), green:{type:'boolean'}, commit:S(64),
    files_changed:FILES, summary:S(1200), obstacles:OBSTACLES },
  required:['unit','green','summary','obstacles'] }
const CERT = { type:'object', additionalProperties:false,
  properties:{ unit:S(80), pass:{type:'boolean'}, evidence:S(2000), files_changed:FILES, obstacles:OBSTACLES },
  required:['unit','pass','obstacles'] }
const FINDINGS = { type:'object', additionalProperties:false,
  properties:{ findings:{type:'array', maxItems:40, items:{type:'object', additionalProperties:false,
    properties:{ severity:{ type:'string', enum:['Critical','High','Medium','Low'] }, file:S(300), issue:S(600),
      fix:S(600), confidence:S(40) }, required:['severity','file','issue'] }},
    summary:S(1200), obstacles:OBSTACLES },
  required:['findings','obstacles'] }
const VERDICT = { type:'object', additionalProperties:false,
  properties:{ real:{type:'boolean'}, why:S(600), obstacles:OBSTACLES }, required:['real','obstacles'] }

// Per-agent stall budget (ms): a worker that emits nothing for this long is restarted (up to 5
// times); implementation turns get more than a review lens. Overrides CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS.
const STALL = { impl: 1800000, review: 900000 }

const LENSES = ['reviewer','sentinel','simplifier','verifier']  // magician:<lens> agent types

// ── Implement + certify: SEQUENTIAL so workers don't collide and commits stay 1/unit ──
phase('Implement')
const done = []
for (let i = 0; i < UNITS.length; i++) {
  const u = UNITS[i]
  const impl = await agent(
    `Implement ONE unit with strict TDD on the existing repo. You see none of the parent conversation — this prompt is complete.\n` +
    `GOAL: ${u.goal}\nACCEPTANCE: ${u.accept || 'meet the goal; add meaningful tests'}\n` +
    `SCOPE (read these ranges with Read; locate more via kg query/kg blast — do NOT grep broadly or paste whole files): ${u.scope || '(discover via kg)'}\n` +
    `BLAST/IMPACT: ${u.impact || '(run kg blast on touched files)'}\n` +
    `STEPS: read the repo's conventions first (CLAUDE.md / code-review.md / linter config — lore/code-standards.md) and match them. Write a FAILING test first → make it pass (green) → refactor. Run the unit's tests, formatter, and linter; fix style before committing. ` +
    `Commit exactly once with a clear message referencing ${u.id}. Do NOT push, open/merge a PR, or touch unrelated files.\n` +
    `RETURN: {unit:"${u.id}", green, commit, files_changed[], summary (≤1200 chars, distilled — no logs), obstacles[] (lore/obstacles.md fields; empty when clean)}`,
    { label:`impl:${u.id}`, phase:'Implement', schema: IMPL, effort:'medium', stallMs: STALL.impl })
  if (!impl || !impl.green) { log(`⚠ ${u.id}: not green — left for manual follow-up`); continue }

  phase('Certify')
  const cert = await agent(
    `Verify ONE unit is actually done. Self-contained prompt.\nUNIT: ${u.id} — ${u.goal}\n` +
    `Run the project's tests, type-check, lint, and build (only what applies). Report pass/fail with evidence. Make no code changes.\n` +
    `RETURN: {unit:"${u.id}", pass, evidence (≤2000 chars: the failing lines, not the log), obstacles[]}`,
    { label:`certify:${u.id}`, phase:'Certify', schema: CERT, effort:'high', stallMs: STALL.review })
  done.push({ u, impl, cert })
}

// ── Review: PARALLEL multi-lens per delivered unit (independent perspectives) ──
phase('Review')
const reviewed = await parallel(done.map(d => () =>
  parallel(LENSES.map(L => () =>
    agent(
      `Review the change for unit ${d.u.id} through the ${L} lens only. Self-contained.\n` +
      `INTENT: ${d.u.goal}\nFILES: ${(d.impl.files_changed||[]).join(', ')}\n` +
      `Read the diff for this unit's commit (${d.impl.commit || 'latest for '+d.u.id}) and the surrounding code (use kg neighbors/blast for context). ` +
      `Report only real, reachable issues in the FINDINGS format.`,
      { label:`review:${L}:${d.u.id}`, phase:'Review', schema: FINDINGS, agentType:`magician:${L}`, stallMs: STALL.review })
  )).then(rs => ({ ...d, findings: rs.filter(Boolean).flatMap(r => r.findings || []) }))
))

// ── Verify: adversarially refute every Critical/High before it counts ──
phase('Verify')
const confirmed = await parallel(reviewed.flatMap(d =>
  (d.findings || []).filter(f => /critical|high/i.test(f.severity)).map(f => () =>
    agent(
      `Try to REFUTE this finding against the actual code. Default to real=false if uncertain.\n` +
      `FILE: ${f.file}\nISSUE: ${f.issue}\nUnit: ${d.u.id}. Read the cited code and decide.`,
      { label:`verify:${d.u.id}`, phase:'Verify', schema: VERDICT, stallMs: STALL.review })
      .then(v => ({ unit: d.u.id, finding: f, real: !!(v && v.real) }))
  )))

// ── Remediate: bounded evaluator-optimizer loop — fix confirmed → re-certify → re-review until clean ──
// This is the loop /weave advertises: run it by default, don't just hand back a to-do list.
phase('Remediate')
const MAX_ROUNDS = (args && args.maxRounds) || 3          // round cap so the loop always terminates
const TOKEN_FLOOR = 40000                                 // stop if the shared budget is nearly spent
let open = confirmed.filter(Boolean).filter(x => x.real)
let round = 0
while (open.length && round < MAX_ROUNDS && (!budget.total || budget.remaining() > TOKEN_FLOOR)) {
  round++
  log(`Remediate round ${round}: ${open.length} confirmed Critical/High`)
  const byUnit = {}
  for (const x of open) (byUnit[x.unit] ||= []).push(x.finding)
  // Fix + re-certify each touched unit (self-contained, TDD, write-gated)
  const fixed = await parallel(Object.keys(byUnit).map(uid => () => {
    const d = done.find(x => x.u.id === uid) || { u: { id: uid, goal: '' } }
    const list = byUnit[uid].map(f => `- [${f.severity}] ${f.file}: ${f.issue}${f.fix ? ' → ' + f.fix : ''}`).join('\n')
    return agent(
      `Remediate confirmed review findings for unit ${uid} with strict TDD, then re-certify. Self-contained — you see none of the parent conversation.\n` +
      `GOAL: ${d.u.goal}\nFINDINGS TO FIX:\n${list}\n` +
      `For each finding: add/adjust a FAILING test capturing the correct behavior → fix → green. Locate code via kg query/kg blast; read only cited ranges. ` +
      `Then run this unit's tests + type-check + lint + build. Commit the fix referencing ${uid} (one fixup commit). Do NOT push or touch unrelated units.\n` +
      `RETURN: {unit:"${uid}", pass, evidence (≤2000 chars), files_changed[], obstacles[]}`,
      { label: `remediate:${uid}`, phase: 'Remediate', schema: CERT, effort: 'medium', stallMs: STALL.impl })
      .then(c => ({ uid, pass: !!(c && c.pass) }))
  }))
  const touched = fixed.filter(r => r.pass).map(r => r.uid)
  if (!touched.length) { log('No unit re-certified clean this round — stopping loop'); break }
  // Re-review ONLY the touched units through all lenses, then re-verify Critical/High
  const rereviewed = await parallel(touched.map(uid => () => {
    const d = done.find(x => x.u.id === uid)
    return parallel(LENSES.map(L => () =>
      agent(
        `Re-review unit ${uid} AFTER remediation, ${L} lens only. Self-contained.\n` +
        `INTENT: ${d ? d.u.goal : ''}\nRead the latest diff for ${uid} (kg neighbors/blast for context). Report only real, reachable issues in FINDINGS format.`,
        { label: `re-review:${L}:${uid}`, phase: 'Remediate', schema: FINDINGS, agentType: `magician:${L}`, stallMs: STALL.review })
    )).then(rs => ({ uid, findings: rs.filter(Boolean).flatMap(r => r.findings || []) }))
  }))
  const reverified = (await parallel(rereviewed.flatMap(d =>
    (d.findings || []).filter(f => /critical|high/i.test(f.severity)).map(f => () =>
      agent(
        `Try to REFUTE this finding against the actual code. Default real=false if uncertain.\n` +
        `FILE: ${f.file}\nISSUE: ${f.issue}\nUnit: ${d.uid}. Read the cited code and decide.`,
        { label: `re-verify:${d.uid}`, phase: 'Remediate', schema: VERDICT, stallMs: STALL.review })
        .then(v => ({ unit: d.uid, finding: f, real: !!(v && v.real) }))
    )))).filter(Boolean).filter(x => x.real)
  // Carry forward still-open findings for units that did NOT re-certify clean this round —
  // otherwise an unfixed unit's confirmed Critical/High vanish into a false "clean" convergence.
  const carried = open.filter(x => !touched.includes(x.unit))
  open = carried.concat(reverified)
}

// ── Consolidate. Report. DO NOT push — write-gated. ──
phase('Consolidate')
return {
  delivered: done.map(d => ({ unit: d.u.id, green: d.impl.green, certified: !!(d.cert && d.cert.pass), commit: d.impl.commit })),
  remediationRounds: round,
  openFindings: open,     // empty when the loop converged clean
  // Roll-up of every worker's obstacles[] (lore/obstacles.md consumer protocol): kept apart from
  // the deliverables so a BLOCKED/DEGRADED unit never reads as done.
  obstacles: done.flatMap(d => [...(d.impl.obstacles || []), ...((d.cert && d.cert.obstacles) || [])].map(o => ({ unit: d.u.id, ...o }))),
  note: open.length
    ? `Ran ${round} remediation round(s); ${open.length} Critical/High still open (round cap or budget floor hit). Resolve, then ship via /seal (gated).`
    : `Ran ${round} remediation round(s); no confirmed Critical/High remain. One commit per unit, NOT pushed — ship via /seal (gated).`,
}
```

## Adapting it

- **Different shape?** Independent units with no shared state → make Implement a `pipeline()` with `isolation:'worktree'` per worker (then merge). Need a cross-unit pass (dedup, shared scaffolding) → add a `parallel()` barrier before Implement.
- **Tune the remediate loop.** The default runs the evaluator-optimizer (fix → re-certify → re-review) until clean, bounded by `MAX_ROUNDS` (override via `args.maxRounds`) and a `budget.remaining()` floor. Set `maxRounds: 1` for a single-pass report; raise it for hard changesets. It re-reviews only the touched units each round, and never pushes — write-gated.
- **Scale to budget** — if a token target was set, gate loops on `budget.remaining()`; otherwise cap finder/lens counts to the unit count.
- **Parity / mirror deliveries (make set B mirror set A 1:1).** When each unit must mirror a gold item — same purpose, justified per-item deviations (e.g. platform B's stories mirroring platform A's) — a generic FINDINGS/verify pass will **green-light *folding*** (one unit silently absorbing several gold purposes) because it only checks "covers the purpose." Encode the 1:1 rule in the evaluator schema and fail anything that violates it:

    ```javascript
    const PARITY = { type:'object', additionalProperties:false, properties:{
      unit:{type:'string'}, mirrors_gold:{type:'boolean'},   // covers exactly the gold item's purpose
      single_purpose:{type:'boolean'},                        // ONE purpose — NO folding of several gold items into one
      correct_id:{type:'boolean'}, deviations_justified:{type:'boolean'},
      issues:{type:'array',items:{type:'string'}} },
      required:['unit','mirrors_gold','single_purpose','correct_id','deviations_justified'] }
    ```
  A unit passes only when `mirrors_gold && single_purpose && correct_id && deviations_justified`; a folded/multi-purpose unit is a **failure that loops back for a split**, not a pass. (Skipping `single_purpose` is what forces a whole corrective second run after the fact.) For a full comprehend→parity job — a gold standard ported to targets with a behavioral-vs-environmental split + a parity contract — reach for **`/transmute`**, which encodes exactly this.
- The non-negotiables (TDD, kg grounding, certify, review+verify, write gates, self-contained prompts) stay in every variant.
