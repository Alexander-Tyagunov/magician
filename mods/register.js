// magician mods (experimental): a status band above the prompt, a person-decided confirm for
// blast-radius shell commands, and a workflow pane. Claude Code mods are a research-preview API
// (Claude Code 2.1.304 or later for `decider: "person"` and `e.isReadOnly`); see README "Mods".
//
// Opt-in: nothing happens unless MAGICIAN_MODS=1 is set in the environment Claude Code runs in.
// register(on, options) receives no `$`, and a hooks module has no Node.js APIs, so the flag cannot
// be read at load time: the hooks always load (`claude plugin validate` lists them), and each one
// reads the flag first with $.env.get and, when it is unset, passes the event straight on with
// next(e), draws nothing and opens nothing. Because the module loads either way, every deny stays
// in scripts/destructive-guard.sh, which runs as a plugin PreToolUse hook whatever this mod does.
//
// Ordering (docs: plugins/mods/events "Where settings hooks run in the order"): plugin PreToolUse
// hooks, the bash guard among them, run after the last mod calls next, and tool.check fires after
// them and the permission rules. So `await next(e)` in the tool.check hook below already holds the
// guard's verdict. This mod never answers with a run verdict of its own: it returns that verdict
// unchanged, an `ask` that only a person can approve (decider "person"; refused where nobody can
// be asked), or a deny where the guard's soft stage names a credential read or code execution that
// nothing else denied. It turns a deny into an ask only when the deny came from a PreToolUse hook
// (`decided.hook`) and the guard, run in its all-soft mode, names blast-radius reasons and no other.

// ---- the guard's soft verdicts, verbatim from scripts/destructive-guard.sh ----
// tests/claude/test_mods.py parses the guard and checks that these two lists together are exactly
// its soft_block reasons (variables as written in the guard), so a new soft reason fails the test
// until it is classified here.
//
// Blast-radius shapes: the guard's soft deny becomes a person-decided ask with a preview.
export const CONFIRM_REASONS = [
  'git push --force to main or master without --force-with-lease',
  'git push --force without --force-with-lease, which overwrites the remote branch blindly',
  'git reset --hard, which discards every uncommitted change in the working tree',
  'rm -rf on an absolute path',
  'rm -rf on the whole working directory, dot or star; needs manual review',
  'rm -rf with no path, deleting whatever xargs feeds it; needs manual review',
  'find -delete over the whole working tree with no name or path filter; needs manual review',
  'truncate of a file outside the working directory; needs manual review',
]

// Credential reads, code execution and over-long commands: the guard's deny stands untouched.
export const KEEP_DENY_REASONS = [
  '$TOO_LONG',
  'pipe-to-shell via $_dlsrc',
  'the ${EVALWORD} builtin used with dynamic content',
  'reading the SSH directory',
  'reading AWS credentials',
  'reading gcloud credentials',
  'reading Azure credentials',
  'reading .env file',
  'private data, network access and execution together (a lethal trifecta); needs manual review',
]

// Blast-radius shapes the guard does not cover (it has no infrastructure rules). Only ever an ask.
export const EXTRA_CONFIRM = [
  { re: /(^|[\s;&|(])terraform(\s+-\S+)*\s+(apply|destroy)\b/, reason: 'terraform apply/destroy changes real infrastructure', preview: 'Dry run first: terraform plan (or terraform plan -destroy).' },
  { re: /(^|[\s;&|(])tofu(\s+-\S+)*\s+(apply|destroy)\b/, reason: 'tofu apply/destroy changes real infrastructure', preview: 'Dry run first: tofu plan.' },
  { re: /(^|[\s;&|(])kubectl\s+(\S+\s+)*delete\b/, reason: 'kubectl delete removes cluster resources', preview: 'Dry run first: add --dry-run=client -o name to list what would go.' },
  { re: /(^|[\s;&|(])helm\s+(uninstall|delete)\b/, reason: 'helm uninstall removes a release', preview: 'Dry run first: helm uninstall --dry-run.' },
]

export const ROT_WARN = 80 // tools/magician-statusline _rot(): warning glyph from 80 %
export const ROT_SEVERE = 92 // and the red glyph from 92 %
const BAND_YELLOW = 70 // _band_color(): yellow from 70 %, red from 90 %
const BAND_RED = 90
const STATE_FILE = '.workspace/local/session-state.md'
const BLAST_PANE = 'magician-blast-radius'
const FLOW_PANE = 'magician-workflow'
const GUARD_TIMEOUT_MS = 5000
const PREVIEW_TIMEOUT_MS = 3000

// ---- module state (resets on reload; nothing here is persisted) ----
let enabled // undefined until the first hook reads MAGICIAN_MODS
const band = { pct: undefined, model: '', effort: '', branch: '', cost: undefined }
const flow = { phase: '', wave: '', workers: 0, spawned: [] }
let blast = null // { command, reason, preview } for the pane, while a confirm is pending

// ---- pure helpers (exported for the tests) ----
export function bar(pct, width = 10) {
  const p = Math.max(0, Math.min(100, Math.round(pct)))
  const fill = Math.round((width * p) / 100)
  return '█'.repeat(fill) + '░'.repeat(width - fill)
}

export function rotWarning(pct) {
  if (typeof pct !== 'number') return ''
  if (pct >= ROT_SEVERE) return '🔴 context rot'
  if (pct >= ROT_WARN) return '⚠ context rot'
  return ''
}

export function bandColor(pct) {
  if (typeof pct !== 'number') return 'gray'
  if (pct >= BAND_RED) return 'red'
  if (pct >= BAND_YELLOW) return 'yellow'
  return 'green'
}

export function bandSegments(s) {
  const out = []
  if (typeof s.pct === 'number') {
    const pct = Math.round(s.pct)
    out.push({ text: '[' + bar(pct) + '] ' + pct + '%', color: bandColor(pct) })
    const rot = rotWarning(pct)
    if (rot) out.push({ text: rot, color: pct >= ROT_SEVERE ? 'red' : 'yellow' })
  }
  if (s.effort) out.push({ text: '🧠 ' + s.effort, color: 'cyan' })
  const meta = []
  if (s.model) meta.push(s.model)
  if (s.branch) meta.push(s.branch)
  if (typeof s.cost === 'number' && s.cost > 0) meta.push('$' + s.cost.toFixed(2))
  if (meta.length) out.push({ text: meta.join(' · '), dim: true })
  return out
}

// Phase and wave from the free-form session-state notes /manifest, /orchestrate and /weave keep.
export function parseSessionState(text) {
  const found = { phase: '', wave: '' }
  if (typeof text !== 'string') return found
  const phases = [...text.matchAll(/\bphase\s*[:#]?\s*(\d+)(?:\s*[:\-–—]\s*([^\n|·]{1,40}))?/gi)]
  if (phases.length) {
    const m = phases[phases.length - 1]
    found.phase = m[1] + (m[2] ? ' ' + m[2].trim() : '')
  }
  const waves = [...text.matchAll(/\bwave\s*[:#]?\s*(\d+)(?:\s*(?:\/|of)\s*(\d+))?/gi)]
  if (waves.length) {
    const m = waves[waves.length - 1]
    found.wave = m[1] + (m[2] ? '/' + m[2] : '')
  }
  return found
}

export function extraConfirm(command) {
  if (typeof command !== 'string') return null
  for (const x of EXTRA_CONFIRM) if (x.re.test(command)) return x
  return null
}

// ---- helpers that call the mods API (top-level functions, so validate traces their calls) ----
async function isEnabled($) {
  if (enabled === undefined) {
    try {
      enabled = (await $.env.get('MAGICIAN_MODS')) === '1'
    } catch {
      enabled = false
    }
  }
  return enabled
}

// Runs the real guard on the command, in its all-soft mode (MAGICIAN_GUARD_ALL_SOFT=1, set only
// here, in the env of this one run), and reads its verdict: hard (exit 2), soft with EVERY soft
// reason it matched, none, or error. The guard only reads the text; it never executes the command.
// `cwd` is the hook event's own working directory when it carries one, else the session's.
async function guardVerdict($, e, command) {
  try {
    const cwd = typeof e.cwd === 'string' && e.cwd ? e.cwd : await $.session.cwd()
    const payload = JSON.stringify({ tool_name: 'Bash', tool_input: { command }, cwd })
    const r = await $.process.run(['bash', $.plugin.root + '/scripts/destructive-guard.sh'], {
      stdin: payload,
      env: { MAGICIAN_GUARD_ALL_SOFT: '1' },
      timeoutMs: GUARD_TIMEOUT_MS,
    })
    if (r.exitCode === 2) return { kind: 'hard' }
    if (r.exitCode !== 0) return { kind: 'error' }
    const out = (r.stdout || '').trim()
    if (!out) return { kind: 'none' }
    const v = JSON.parse(out)
    if (!v || v.decision !== 'block' || typeof v.reason !== 'string') return { kind: 'error' }
    // An all-soft verdict lists every reason; a guard without that mode lists only `reason`.
    const reasons = Array.isArray(v.reasons) && v.reasons.length ? v.reasons.map(String) : [v.reason]
    return { kind: 'soft', reason: v.reason, reasons }
  } catch {
    return { kind: 'error' }
  }
}

// A soft verdict may become a person-decided ask only when every reason in it is a blast-radius
// shape and none is a credential read, code execution or over-long command.
export function allConfirmable(reasons) {
  if (!Array.isArray(reasons) || !reasons.length) return false
  return reasons.every((r) => CONFIRM_REASONS.includes(r) && !KEEP_DENY_REASONS.includes(r))
}

// The deny being converted must be the guard's own: it came from a PreToolUse hook (the `hook`
// origin field Claude Code sets on a tool.check result) and from no settings rule. Attribution is
// by origin field, never by matching the reason text.
export function isGuardDeny(decided) {
  return !!decided && decided.decision === 'deny' && decided.hook === 'PreToolUse' && decided.rule === undefined && decided.setting === undefined
}

// A short read-only preview of what the command would touch. Only fixed, read-only git argv.
async function preview($, reason) {
  let argv = null
  if (reason.startsWith('git reset --hard') || reason.startsWith('rm -rf') || reason.startsWith('find -delete')) argv = ['git', 'status', '--short']
  else if (reason.startsWith('git push --force')) argv = ['git', 'log', '--oneline', '-5', '@{upstream}..HEAD']
  if (!argv) return ''
  try {
    const r = await $.process.run(argv, { timeoutMs: PREVIEW_TIMEOUT_MS })
    if (r.exitCode !== 0) return ''
    const lines = (r.stdout || '').split('\n').filter(Boolean)
    const head = lines.slice(0, 12).join('\n')
    return lines.length > 12 ? head + '\n… ' + (lines.length - 12) + ' more' : head
  } catch {
    return ''
  }
}

async function showBlast($, command, reason, text) {
  blast = { command: command.length > 400 ? command.slice(0, 400) + '…' : command, reason, preview: text }
  try {
    await $.ui.open({ id: BLAST_PANE, title: 'magician: confirm' })
  } catch {}
  $.ui.invalidate('ui.render')
}

async function confirm($, e, command, reason, text) {
  if (e.tool_use_id) await showBlast($, command, reason, text)
  return { decision: 'ask', decider: 'person', reason: 'magician blast radius: ' + reason + '. Approve only if you meant it.' }
}

async function refreshBand($) {
  try {
    const u = await $.session.usage()
    band.pct = u && u.context ? u.context.percent : undefined
    band.cost = u && u.cost ? u.cost.usd : undefined
  } catch {}
  try {
    band.model = await $.session.model()
  } catch {}
  try {
    const r = await $.process.run(['git', 'branch', '--show-current'], { timeoutMs: 2000 })
    band.branch = r.exitCode === 0 ? (r.stdout || '').trim() : ''
  } catch {
    band.branch = ''
  }
  $.ui.invalidate('ui.render')
}

async function refreshFlow($) {
  try {
    if (await $.fs.exists(STATE_FILE)) {
      const found = parseSessionState(await $.fs.read(STATE_FILE))
      flow.phase = found.phase
      flow.wave = found.wave
    } else {
      flow.phase = ''
      flow.wave = ''
    }
  } catch {}
  try {
    const agents = await $.agent.list()
    flow.workers = (agents || []).filter((a) => ['pending', 'running', 'waiting'].includes(a.status)).length
  } catch {}
  if (flow.phase || flow.wave || flow.workers > 0) {
    try {
      await $.ui.open({ id: FLOW_PANE, title: 'magician workflow' })
    } catch {}
  }
  $.ui.invalidate('ui.render')
}

// ---- the hooks ----
export function register(on) {
  on('session.start', async ($, e, next) => {
    if (await isEnabled($)) await refreshBand($)
    return next(e)
  })

  // Effort and model of the main loop's requests, read as they pass; the step is never changed.
  on('turn.step', async function* ($, e, next) {
    if (!e.agentId && (await isEnabled($))) {
      if (e.effort !== undefined) band.effort = String(e.effort)
      if (e.model) band.model = e.model
    }
    return yield* next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (await isEnabled($)) {
      await refreshBand($)
      if (blast) {
        blast = null
        try {
          await $.ui.close({ id: BLAST_PANE })
        } catch {}
      }
    }
    return next(e)
  })

  // I1: the status band above the prompt. Read-only: it only draws.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (!(await isEnabled($))) return next(e)
    const segs = bandSegments(band)
    if (!segs.length) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const children = [Text({ color: 'magenta', children: ['✦'] })]
    for (const s of segs) children.push(Text(s.dim ? { dimColor: true, children: [s.text] } : { color: s.color, children: [s.text] }))
    const line = Box({ key: 'magician-band', flexDirection: 'row', columnGap: 1, children })
    const theirs = await next(e)
    return theirs ? Box({ flexDirection: 'column', children: [theirs, line] }) : line
  })

  // I2: blast-radius confirm. Never answers with a run verdict of its own.
  on('tool.check', { tool: 'Bash' }, async ($, e, next) => {
    const decided = await next(e)
    if (e.isReadOnly || !(await isEnabled($))) return decided
    const command = e.input && typeof e.input.command === 'string' ? e.input.command : ''
    if (!command) return decided
    const isDeny = !!decided && decided.decision === 'deny'
    const verdict = await guardVerdict($, e, command)
    if (verdict.kind === 'hard') {
      // The guard refuses this shape. Its deny stands; if the guard did not run, a person decides.
      if (isDeny) return decided
      return { decision: 'ask', decider: 'person', reason: 'magician destructive guard refuses this command shape; it did not run here, so you decide.' }
    }
    if (verdict.kind === 'soft') {
      if (!allConfirmable(verdict.reasons)) {
        // A credential read, code execution or over-long command (alone or next to a blast-radius
        // shape): the guard's deny stands, and if nothing denied it, this answer is a deny too,
        // the same as the hard path refuses toward safety.
        if (isDeny) return decided
        const keep = verdict.reasons.find((r) => KEEP_DENY_REASONS.includes(r)) || verdict.reasons.find((r) => !CONFIRM_REASONS.includes(r)) || verdict.reason
        return { decision: 'deny', reason: 'magician destructive guard: ' + keep + '.' }
      }
      // Turn a deny into an ask only when it is the guard's own soft verdict.
      if (isDeny && !isGuardDeny(decided)) return decided
      return confirm($, e, command, verdict.reason, await preview($, verdict.reason))
    }
    const extra = extraConfirm(command)
    if (extra && !isDeny) return confirm($, e, command, extra.reason, extra.preview)
    return decided
  }).catch(async ($, e, next) => {
    // Fail toward a person, never toward running. A deny reached before the failure stands; only
    // a check that failed with no deny in hand becomes a person-decided ask. Never an allow.
    // (A catch handler's next(e) hands back the verdict the hook already received, when the hook
    // had called next before it failed; see the mods docs' `next.called ? next(e) : ...` pattern.)
    if (next.called) {
      try {
        const prior = await next(e)
        if (prior && prior.decision === 'deny') return prior
      } catch {}
    }
    return { decision: 'ask', decider: 'person', reason: 'magician blast-radius check failed (' + next.error.kind + '); you decide.' }
  })

  // I3: workflow pane, refreshed as turns start and workers spawn. Observes only.
  on('turn.start', async ($, e, next) => {
    if (await isEnabled($)) await refreshFlow($)
    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    if (await isEnabled($)) {
      flow.spawned = [...flow.spawned, (e.subagentType || 'agent') + (e.description ? ': ' + e.description : '')].slice(-3)
      await refreshFlow($)
    }
    return next(e)
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== BLAST_PANE && e.requestId !== FLOW_PANE) return next(e)
    if (!(await isEnabled($))) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const rows = []
    if (e.requestId === BLAST_PANE) {
      if (!blast) {
        rows.push(Text({ dimColor: true, children: ['No command is waiting for a decision.'] }))
      } else {
        rows.push(Text({ color: 'yellow', children: ['⚠ ' + blast.reason] }))
        rows.push(Text({ children: ['$ ' + blast.command] }))
        rows.push(Text({ dimColor: true, children: [blast.preview ? 'Would touch:' : 'No preview for this shape.'] }))
        if (blast.preview) rows.push(Text({ children: [blast.preview] }))
        rows.push(Text({ dimColor: true, children: ['Answer in the permission dialog; magician cannot approve it for you.'] }))
      }
    } else {
      rows.push(Text({ children: ['Phase: ' + (flow.phase || '-')] }))
      rows.push(Text({ children: ['Wave: ' + (flow.wave || '-')] }))
      rows.push(Text({ children: ['Workers: ' + flow.workers] }))
      for (const s of flow.spawned) rows.push(Text({ dimColor: true, children: ['· ' + s] }))
    }
    return Box({ flexDirection: 'column', children: rows })
  })
}
