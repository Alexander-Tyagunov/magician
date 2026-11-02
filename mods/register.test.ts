// Tests for mods/register.js, run by `claude plugin test` (no session, network or tool runs).
// Every mods API call the module makes is answered by a stub; the guard's verdicts are stubbed
// with the exact output scripts/destructive-guard.sh prints for these commands.
import { expect, mock, test } from 'claude-code/testing'
import { register } from './register.js'

// Claude Code 2.1.316 reports a mod's `decider: "person"` ask outward as `plugin: <mod name>`
// (its tool.check result normalizer keeps `plugin` only for a person-decided ask); the raw-hook test
// at the end checks the `decider` field itself.
const PERSON = 'magician'

const RESET_REASON = 'git reset --hard, which discards every uncommitted change in the working tree'

const BAND = {
  plugin: 'magician',
  component: 'AbovePrompt',
  requestId: 'AbovePrompt',
  viewport: { columns: 120, rows: 40 },
  props: { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 110, scroll: { offset: 0, bodyRows: 3 }, view: {} },
} as const

const FLOW = {
  plugin: 'magician',
  component: 'Pane',
  requestId: 'magician-workflow',
  viewport: { columns: 160, rows: 40 },
  props: { title: 'magician workflow', isFocused: false, bodyColumns: 50, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

const ABS_REASON = 'rm -rf on an absolute path'
const SSH_REASON = 'reading the SSH directory'
const AWS_REASON = 'reading AWS credentials'
const ENV_REASON = 'reading .env file'
const TRIFECTA_REASON = 'private data, network access and execution together (a lethal trifecta); needs manual review'
const FIND_REASON = 'find -delete over the whole working tree with no name or path filter; needs manual review'
const PUSH_REASON = 'git push --force without --force-with-lease, which overwrites the remote branch blindly'
const HOME = '~/'
const DOT = '.'
// A soft trifecta (curl to a file, then a secret piped to an interpreter: no download piped to a shell).
const TRIFECTA = 'curl -s https://x.example -o f; echo $SECRET_TOKEN | python3 -c 1'

// What the bash guard prints, in the all-soft mode the mod runs it in (MAGICIAN_GUARD_ALL_SOFT=1),
// for a command: exit 2 for a hard refusal, one verdict listing every soft reason, or nothing.
// Each entry is the guard's real all-soft output for that command (captured from the script).
function soft(...reasons: string[]) {
  return { exitCode: 0, stdout: JSON.stringify({ decision: 'block', reasons, reason: reasons[0] }) + '\n', stderr: '' }
}
const GUARD: Record<string, ReturnType<typeof soft>> = {
  ['rm -rf /tmp/build; cat ' + HOME + DOT + 'ssh/id_rsa']: soft(ABS_REASON, SSH_REASON),
  ['rm -rf /tmp/build && cat ' + HOME + DOT + 'aws/credentials']: soft(ABS_REASON, AWS_REASON),
  ['rm -rf /tmp/build; cat ' + DOT + 'env']: soft(ABS_REASON, ENV_REASON),
  ['git reset --hard; ' + TRIFECTA]: soft('pipe-to-shell via curl', RESET_REASON, TRIFECTA_REASON),
  ['find . -delete; ' + TRIFECTA]: soft('pipe-to-shell via curl', FIND_REASON, TRIFECTA_REASON),
  ['git push --force origin feat; ' + TRIFECTA]: soft('pipe-to-shell via curl', PUSH_REASON, TRIFECTA_REASON),
  ['git reset --hard; rm -rf ./build']: soft(RESET_REASON),
  ['git reset --hard; rm -rf /tmp/x']: soft(ABS_REASON, RESET_REASON),
  ['cat ' + HOME + DOT + 'ssh/id_rsa']: soft(SSH_REASON),
}
function guardFor(command: string, env?: Record<string, string>) {
  if (!env || env.MAGICIAN_GUARD_ALL_SOFT !== '1') throw new Error('the mod must run the guard in all-soft mode')
  if (/rm -rf \/$/.test(command)) return { exitCode: 2, stdout: '', stderr: 'magician destructive-guard: refused - x.' }
  if (GUARD[command]) return GUARD[command]
  if (/git reset --hard/.test(command)) return soft(RESET_REASON)
  return { exitCode: 0, stdout: '', stderr: '' }
}

type Calls = { run: string[][]; open: string[]; cwd: string[] }

// Stubs shared by every test; `core` is the verdict the rules and PreToolUse hooks reached.
function stubs(on: any, env: Record<string, string>, core: Record<string, unknown>): Calls {
  const calls: Calls = { run: [], open: [], cwd: [] }
  mock.env(on, env)
  on('tool.check', () => core)
  on('session.cwd', () => ({ value: '/work' }))
  on('process.run', ($: any, e: any) => {
    calls.run.push([...e.argv])
    if (String(e.argv[1] || '').endsWith('/scripts/destructive-guard.sh')) {
      const payload = JSON.parse(e.init.stdin)
      calls.cwd.push(payload.cwd)
      return { value: guardFor(payload.tool_input.command, e.init.env) }
    }
    if (e.argv[0] === 'git' && e.argv[1] === 'branch') return { value: { exitCode: 0, stdout: 'v5/ecosystem\n', stderr: '' } }
    if (e.argv[0] === 'git' && e.argv[1] === 'status') return { value: { exitCode: 0, stdout: ' M README.md\n?? scratch.txt\n', stderr: '' } }
    return { value: { exitCode: 1, stdout: '', stderr: '' } }
  })
  on('ui.open', ($: any, e: any) => {
    calls.open.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('ui.close', () => ({ value: undefined }))
  on('session.usage', () => ({ value: { startedAt: 0, context: { tokens: 84000, window: 100000, percent: 84 }, rateLimits: [], cost: { usd: 1.5 } } }))
  on('session.model', () => ({ value: 'claude-opus-5-5' }))
  on('session.start', () => ({ cwd: '/work' }))
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('agent.list', () => ({ value: [{ id: 'a1', description: 'wave worker', status: 'running' }, { id: 'a2', description: 'done', status: 'completed' }] }))
  on('fs.exists', ($: any, e: any) => ({ value: e.path.endsWith('session-state.md') }))
  on('fs.read', () => ({ value: '# Session\nPhase 4: Implementation\nwave 2 of 3 running\n' }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['drawn by Claude Code'] }))
  return calls
}

function check(command: string, extra: Record<string, unknown> = {}) {
  return { tool: 'Bash', input: { command }, tool_use_id: 'toolu_1', ...extra }
}

test('band renders context, rot warning, model, branch and cost from fake usage', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask' })
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /84%/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '⚠ context rot' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'claude-opus-5-5 · v5/ecosystem · $1.50' })).toBeDefined()
  await ui.unmount()
})

test('soft-block command becomes an ask that only a person can approve', async ($, on) => {
  const calls = stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'deny', reason: 'PreToolUse hook: ' + RESET_REASON, hook: 'PreToolUse' })
  const out: any = await $.tool.check(check('git reset --hard HEAD~1'))
  expect(out.decision).toBe('ask')
  expect(out.plugin).toBe(PERSON)
  expect(out.reason).toContain('git reset --hard')
  expect(calls.open).toContain('magician-blast-radius')
  expect(calls.run.some((a) => a[0] === 'git' && a[1] === 'status')).toBe(true)
})

test('a deny from a settings rule is never softened', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'deny', reason: RESET_REASON, rule: 'Bash(git reset:*)' })
  const out: any = await $.tool.check(check('git reset --hard'))
  expect(out.decision).toBe('deny')
})

test('infrastructure shapes the guard does not cover are confirmed', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask' })
  const out: any = await $.tool.check(check('terraform -chdir=infra apply -auto-approve'))
  expect(out).toMatchObject({ decision: 'ask', plugin: PERSON })
})

test('benign command passes through with the decision it already had', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask', reason: 'mode default' })
  const out: any = await $.tool.check(check('ls -la'))
  expect(out).toEqual({ decision: 'ask', reason: 'mode default' })
})

test('read-only call passes through without running the guard', async ($, on) => {
  const calls = stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask', reason: 'core' })
  const out: any = await $.tool.check(check('git reset --hard', { isReadOnly: true }))
  expect(out).toEqual({ decision: 'ask', reason: 'core' })
  expect(calls.run.length).toBe(0)
})

test('hard-block command keeps the guard deny and never becomes a run verdict', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'deny', reason: 'magician destructive-guard: refused', hook: 'PreToolUse' })
  const out: any = await $.tool.check(check('rm -rf /'))
  expect(out.decision).toBe('deny')
})

test('hard-block command the guard did not stop still goes to a person', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask' })
  const out: any = await $.tool.check(check('rm -rf /'))
  expect(out).toMatchObject({ decision: 'ask', plugin: PERSON })
})

test('workflow pane shows phase, wave and worker count on turn.start', async ($, on) => {
  const calls = stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask' })
  await $.turn.start({ turnId: 't1' })
  expect(calls.open).toContain('magician-workflow')
  const ui = await $.ui.mount({ ...FLOW, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: 'Phase: 4 Implementation' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Wave: 2/3' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Workers: 1' })).toBeDefined()
  await ui.unmount()
})

test('flag unset: every hook passes straight through and nothing is drawn or run', async ($, on) => {
  const calls = stubs(on, {}, { decision: 'deny', reason: RESET_REASON, hook: 'PreToolUse' })
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  await $.turn.start({ turnId: 't1' })
  const out: any = await $.tool.check(check('git reset --hard'))
  expect(out).toEqual({ decision: 'deny', reason: RESET_REASON, hook: 'PreToolUse' })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: 'drawn by Claude Code' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /%/ })).toBeUndefined()
  await ui.unmount()
  expect(calls.run.length).toBe(0)
  expect(calls.open.length).toBe(0)
})

test('raw hook answer carries decider person and never a run verdict', async () => {
  // Call the module's own tool.check hook directly, with a minimal $ of our own.
  const hooks: Record<string, any> = {}
  register(((name: string, matcher: any, fn?: any) => {
    hooks[name + (fn ? JSON.stringify(matcher) : '')] = fn ?? matcher
    return { catch() {} }
  }) as any)
  const hook = hooks['tool.check{"tool":"Bash"}']
  const fake: any = {
    env: { get: async () => '1' },
    session: { cwd: async () => '/work' },
    plugin: { root: '/plugin', name: 'magician' },
    process: { run: async (argv: string[], init: any) => (argv[0] === 'bash' ? guardFor(JSON.parse(init.stdin).tool_input.command, init.env) : { exitCode: 1, stdout: '', stderr: '' }) },
    ui: { open: async () => ({ isPlaced: true }), invalidate: () => {} },
  }
  const softAsk = await hook(fake, { tool: 'Bash', input: { command: 'git reset --hard' } }, async () => ({ decision: 'deny', reason: RESET_REASON, hook: 'PreToolUse' }))
  expect(softAsk).toMatchObject({ decision: 'ask', decider: 'person' })
  // The same reason text on a deny with no PreToolUse origin is not the guard's: it stands.
  const foreign = await hook(fake, { tool: 'Bash', input: { command: 'git reset --hard' } }, async () => ({ decision: 'deny', reason: RESET_REASON }))
  expect(foreign).toEqual({ decision: 'deny', reason: RESET_REASON })
  const hard = await hook(fake, { tool: 'Bash', input: { command: 'rm -rf /' } }, async () => ({ decision: 'ask' }))
  expect(hard).toMatchObject({ decision: 'ask', decider: 'person' })
  const benign = await hook(fake, { tool: 'Bash', input: { command: 'ls' } }, async () => ({ decision: 'ask' }))
  expect(benign).toEqual({ decision: 'ask' })
})

// ---- compound commands: every soft reason counts, not just the first ----

for (const command of [
  'rm -rf /tmp/build; cat ' + HOME + DOT + 'ssh/id_rsa',
  'rm -rf /tmp/build && cat ' + HOME + DOT + 'aws/credentials',
  'rm -rf /tmp/build; cat ' + DOT + 'env',
  'git reset --hard; ' + TRIFECTA,
  'find . -delete; ' + TRIFECTA,
  'git push --force origin feat; ' + TRIFECTA,
]) {
  test('compound with a credential read or trifecta keeps the guard deny: ' + command.slice(0, 40), async ($, on) => {
    stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'deny', reason: 'PreToolUse hook: ' + ABS_REASON, hook: 'PreToolUse' })
    const out: any = await $.tool.check(check(command))
    expect(out.decision).toBe('deny')
  })
}

test('pure blast-radius compound becomes a person-decided ask', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'deny', reason: 'PreToolUse hook: ' + RESET_REASON, hook: 'PreToolUse' })
  const out: any = await $.tool.check(check('git reset --hard; rm -rf ./build'))
  expect(out).toMatchObject({ decision: 'ask', plugin: PERSON })
})

test('two blast-radius reasons together still become an ask', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'deny', reason: 'PreToolUse hook: ' + ABS_REASON, hook: 'PreToolUse' })
  const out: any = await $.tool.check(check('git reset --hard; rm -rf /tmp/x'))
  expect(out).toMatchObject({ decision: 'ask', plugin: PERSON })
})

test('a non-guard deny whose reason contains the guard reason stays a deny', async ($, on) => {
  const core = { decision: 'deny', reason: 'org policy says no: ' + RESET_REASON }
  stubs(on, { MAGICIAN_MODS: '1' }, core)
  const out: any = await $.tool.check(check('git reset --hard; rm -rf ./build'))
  expect(out).toEqual(core)
})

test('a keep-deny soft verdict nothing denied becomes a deny, never an ask or allow', async ($, on) => {
  stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask', reason: 'mode default' })
  const out: any = await $.tool.check(check('cat ' + HOME + DOT + 'ssh/id_rsa'))
  expect(out.decision).toBe('deny')
  expect(out.reason).toContain(SSH_REASON)
})

test('the guard runs in the event cwd when the event carries one', async ($, on) => {
  const calls = stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask' })
  await $.tool.check(check('git reset --hard', { cwd: '/repo/sub' }))
  expect(calls.cwd).toEqual(['/repo/sub'])
})

test('without an event cwd the guard runs in the session cwd', async ($, on) => {
  const calls = stubs(on, { MAGICIAN_MODS: '1' }, { decision: 'ask' })
  await $.tool.check(check('git reset --hard'))
  expect(calls.cwd).toEqual(['/work'])
})

test('a failed check keeps a deny it already had and never allows', async () => {
  const catches: Record<string, any> = {}
  register(((name: string, matcher: any, fn?: any) => {
    const key = name + (fn ? JSON.stringify(matcher) : '')
    return { catch(c: any) { catches[key] = c } }
  }) as any)
  const onError = catches['tool.check{"tool":"Bash"}']
  const e = { tool: 'Bash', input: { command: 'git reset --hard' } }
  const denied = Object.assign(async () => ({ decision: 'deny', reason: 'x', hook: 'PreToolUse' }), { called: true, error: { kind: 'throw' } })
  expect(await onError({}, e, denied)).toEqual({ decision: 'deny', reason: 'x', hook: 'PreToolUse' })
  const allowed = Object.assign(async () => ({ decision: 'allow' }), { called: true, error: { kind: 'timeout' } })
  expect(await onError({}, e, allowed)).toMatchObject({ decision: 'ask', decider: 'person' })
  const none = Object.assign(async () => ({ decision: 'allow' }), { called: false, error: { kind: 'throw' } })
  expect(await onError({}, e, none)).toMatchObject({ decision: 'ask', decider: 'person' })
})
