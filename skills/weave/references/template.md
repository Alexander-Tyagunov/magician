# /weave — Workflow template (copy and adapt)

This is the magician-grade delivery pipeline as a native `Workflow` script. Adapt the
`UNITS` list and the prompts to the task; keep the guardrails. Pass it to the `Workflow`
tool as `{script: "..."}`. It mirrors the shape an agent reaches for by hand (sequential
TDD per unit → certify → parallel multi-lens review → adversarial verify → consolidate),
but with kg grounding, self-contained prompts, and write gates built in.

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

// ── Consolidate (barrier already done). Report. DO NOT push — write-gated. ──
phase('Consolidate')
const real = confirmed.filter(Boolean).filter(x => x.real)
return {
  delivered: done.map(d => ({ unit: d.u.id, green: d.impl.green, certified: !!(d.cert && d.cert.pass), commit: d.impl.commit })),
  confirmedFindings: real,
  note: 'Implemented on the current branch, one commit per unit. NOT pushed. Resolve confirmed Critical/High, then ship via /seal (gated).',
}
```

## Adapting it

- **Different shape?** Independent units with no shared state → make Implement a `pipeline()` with `isolation:'worktree'` per worker (then merge). Need a cross-unit pass (dedup, shared scaffolding) → add a `parallel()` barrier before Implement. Tighten the verify loop into evaluator-optimizer (review → fix → re-review) by looping while confirmed Critical/High remain and `budget.remaining()` allows.
- **Remediation in-pipeline?** Add a stage after Verify that dispatches a fix agent per confirmed finding (self-contained, TDD), then re-certifies. Keep it gated if it would push.
- **Scale to budget** — if a token target was set, gate loops on `budget.remaining()`; otherwise cap finder/lens counts to the unit count.
- The non-negotiables (TDD, kg grounding, certify, review+verify, write gates, self-contained prompts) stay in every variant.
