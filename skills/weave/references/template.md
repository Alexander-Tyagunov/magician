# /weave — Workflow template (copy and adapt)

This is the magician-grade delivery pipeline as a native `Workflow` script. Adapt the
`UNITS` list and the prompts to the task; keep the guardrails. Pass it to the `Workflow`
tool as `{script: "..."}`. It mirrors the shape an agent reaches for by hand (sequential
TDD per unit → certify → parallel multi-lens review → adversarial verify → bounded remediate loop → consolidate), but with kg grounding, self-contained prompts, write gates, and a terminating evaluator-optimizer loop built in.

Key API reminders: `meta` must be a pure literal; `agent(prompt, {label, phase, schema, model, effort, agentType, isolation})`; `pipeline(items, ...stages)` (no barrier); `parallel(thunks)` (barrier); `phase()`, `log()`. `Date.now()`/`Math.random()` are unavailable — vary by index. Worktree isolation only when parallel agents mutate files.

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

const IMPL = { type:'object', additionalProperties:false,
  properties:{ unit:{type:'string'}, green:{type:'boolean'}, commit:{type:'string'},
    files:{type:'array',items:{type:'string'}}, summary:{type:'string'} },
  required:['unit','green','summary'] }
const CERT = { type:'object', additionalProperties:false,
  properties:{ unit:{type:'string'}, pass:{type:'boolean'}, evidence:{type:'string'} },
  required:['unit','pass'] }
const FINDINGS = { type:'object', additionalProperties:false,
  properties:{ findings:{type:'array',items:{type:'object', additionalProperties:false,
    properties:{ severity:{type:'string'}, file:{type:'string'}, issue:{type:'string'},
      fix:{type:'string'}, confidence:{type:'string'} }, required:['severity','file','issue'] }} },
  required:['findings'] }
const VERDICT = { type:'object', additionalProperties:false,
  properties:{ real:{type:'boolean'}, why:{type:'string'} }, required:['real'] }

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
    `STEPS: write a FAILING test first → make it pass (green) → refactor. Run the unit's tests. ` +
    `Commit exactly once with a clear message referencing ${u.id}. Do NOT push, open/merge a PR, or touch unrelated files.\n` +
    `RETURN: {unit:"${u.id}", green, commit, files[], summary}`,
    { label:`impl:${u.id}`, phase:'Implement', schema: IMPL, effort:'high' })
  if (!impl || !impl.green) { log(`⚠ ${u.id}: not green — left for manual follow-up`); continue }

  phase('Certify')
  const cert = await agent(
    `Verify ONE unit is actually done. Self-contained prompt.\nUNIT: ${u.id} — ${u.goal}\n` +
    `Run the project's tests, type-check, lint, and build (only what applies). Report pass/fail with evidence. Make no code changes.\n` +
    `RETURN: {unit:"${u.id}", pass, evidence}`,
    { label:`certify:${u.id}`, phase:'Certify', schema: CERT })
  done.push({ u, impl, cert })
}

// ── Review: PARALLEL multi-lens per delivered unit (independent perspectives) ──
phase('Review')
const reviewed = await parallel(done.map(d => () =>
  parallel(LENSES.map(L => () =>
    agent(
      `Review the change for unit ${d.u.id} through the ${L} lens only. Self-contained.\n` +
      `INTENT: ${d.u.goal}\nFILES: ${(d.impl.files||[]).join(', ')}\n` +
      `Read the diff for this unit's commit (${d.impl.commit || 'latest for '+d.u.id}) and the surrounding code (use kg neighbors/blast for context). ` +
      `Report only real, reachable issues in the FINDINGS format.`,
      { label:`review:${L}:${d.u.id}`, phase:'Review', schema: FINDINGS, agentType:`magician:${L}` })
  )).then(rs => ({ ...d, findings: rs.filter(Boolean).flatMap(r => r.findings || []) }))
))

// ── Verify: adversarially refute every Critical/High before it counts ──
phase('Verify')
const confirmed = await parallel(reviewed.flatMap(d =>
  (d.findings || []).filter(f => /critical|high/i.test(f.severity)).map(f => () =>
    agent(
      `Try to REFUTE this finding against the actual code. Default to real=false if uncertain.\n` +
      `FILE: ${f.file}\nISSUE: ${f.issue}\nUnit: ${d.u.id}. Read the cited code and decide.`,
      { label:`verify:${d.u.id}`, phase:'Verify', schema: VERDICT })
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
      `RETURN: {unit:"${uid}", pass, evidence}`,
      { label: `remediate:${uid}`, phase: 'Remediate', schema: CERT, effort: 'high' })
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
        { label: `re-review:${L}:${uid}`, phase: 'Remediate', schema: FINDINGS, agentType: `magician:${L}` })
    )).then(rs => ({ uid, findings: rs.filter(Boolean).flatMap(r => r.findings || []) }))
  }))
  const reverified = (await parallel(rereviewed.flatMap(d =>
    (d.findings || []).filter(f => /critical|high/i.test(f.severity)).map(f => () =>
      agent(
        `Try to REFUTE this finding against the actual code. Default real=false if uncertain.\n` +
        `FILE: ${f.file}\nISSUE: ${f.issue}\nUnit: ${d.uid}. Read the cited code and decide.`,
        { label: `re-verify:${d.uid}`, phase: 'Remediate', schema: VERDICT })
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
