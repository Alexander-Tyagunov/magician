#!/usr/bin/env node
// tests/e2e/plan_walkthrough.spec.js — local-only Playwright pass over the plan walkthrough page.
// NOT part of scripts/gate.sh or CI (needs a browser and Node). Run: node tests/e2e/plan_walkthrough.spec.js
//
// Part 1 (static page, file://): keyboard contract, review marks, chat-line fallback.
// Part 3 (artifact transport): the same page with --transport artifact and a mock `window.claude.use("db")`
//   (the real capability only exists inside the Artifact host): events land in the `events` collection,
//   state/current and plan/current snapshots drive the revising ring and the v2 hot-swap, an
//   invalid_argument write turns the controls read-only, and a null capability falls back to static.
// Part 2 (live page): starts tools/companion/vc-start.sh --plan when it exists and node is present,
//   opens the served page, posts a change request from the toolbar, writes a plan.json + state.json
//   revision into the plan dir exactly as the /blueprint skill would, asserts the card hot-swaps with
//   the v2 badge and the "what changed" panel, approves the plan, and asserts plan.approved landed in
//   events.jsonl. Skipped with a message when the companion or node is missing.
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync, spawnSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..', '..');
const TOOL = path.join(ROOT, 'tools', 'plan-render');
const FIXTURE = path.join(ROOT, 'tests', 'claude', 'fixtures', 'plans', 'valid.json');
const VC_START = path.join(ROOT, 'tools', 'companion', 'vc-start.sh');
const VC_STOP = path.join(ROOT, 'tools', 'companion', 'vc-stop.sh');

let passed = 0, failed = 0;
function check(name, ok, extra) { if (ok) { passed++; console.log('  ok   ' + name); } else { failed++; console.log('  FAIL ' + name + (extra ? ' — ' + extra : '')); } }
async function waitFor(fn, ms = 8000, step = 100) { const t0 = Date.now(); for (;;) { const v = await fn(); if (v) return v; if (Date.now() - t0 > ms) return null; await new Promise(r => setTimeout(r, step)); } }

async function staticPass(browser, tmp) {
  console.log('Part 1 — static page (file://)');
  const html = path.join(tmp, 'static.html');
  execFileSync('python3', [TOOL, 'html', FIXTURE, '-o', html]);
  const page = await browser.newPage();
  const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + html);
  check('transport resolves to static', (await page.evaluate(() => window.__magicianPage.link())) === 'static');
  check('step 0 is the context', (await page.textContent('#progress')).startsWith('Step 0 / 12'));
  await page.keyboard.press('ArrowRight');
  check('→ moves to T1', (await page.textContent('#progress')).includes('T1'));
  await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowLeft');
  check('← moves back', (await page.textContent('#progress')).includes('Step 1 /'));
  check('card not busy', (await page.getAttribute('#detail', 'aria-busy')) === 'false');
  await page.keyboard.press('a');
  check('A approves the step (tally)', (await page.textContent('#tally')).includes('1 approved'));
  check('approve button pressed state', (await page.getAttribute('[data-act="approve"]', 'aria-pressed')) === 'true');
  await page.keyboard.press('c');
  check('C opens the change sheet', await page.isVisible('#sheet'));
  check('sheet explains the static fallback', (await page.textContent('#sheet-text')).includes('static'));
  await page.fill('#cr', 'use a managed Redis instead of self-hosted');
  await page.keyboard.press('Enter');
  check('Enter sends; sheet closes', !(await page.isVisible('#sheet')));
  const log = await page.$$eval('#helperlog .msg', els => els.map(e => e.textContent));
  check('helper transcript holds the request', log.some(t => t.includes('[T1] use a managed Redis')), JSON.stringify(log.slice(-3)));
  check('chat line composed (T1: …)', log.some(t => t.includes('T1: use a managed Redis')), JSON.stringify(log.slice(-3)));
  check('step is NOT marked revising on a static page', !(await page.textContent('#tally')).includes('revising'));
  await page.keyboard.press('h');
  check('H opens the helper', !(await page.getAttribute('#helper', 'hidden')));
  check('helper status says static', (await page.textContent('#helperstatus')).startsWith('Static'));
  await page.keyboard.press('Escape');
  check('Esc closes the helper and moves focus to its button', (await page.evaluate(() => document.activeElement.id)) === 'helperbtn');
  await page.evaluate(() => document.activeElement.blur());
  await page.keyboard.press('?');
  check('? opens keyboard help', (await page.getAttribute('#help', 'open')) !== null);
  await page.click('#showmd');
  check('plan document dialog opens with Task headings', (await page.$$('#mdbody h3')).length === 12);
  await page.keyboard.press('Escape');
  check('Esc closes the dialog', !(await page.isVisible('#mddlg')));
  check('Esc returns focus to the opener', (await page.evaluate(() => document.activeElement.id)) === 'showmd');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => document.activeElement.blur());
  await page.keyboard.press(' ');
  check('Space plays', (await page.getAttribute('#play', 'aria-pressed')) === 'true');
  await page.keyboard.press(' ');
  check('Space pauses', (await page.getAttribute('#play', 'aria-pressed')) === 'false');
  // tab order: skip link first (fresh document position)
  await page.reload();
  await page.keyboard.press('Tab');
  check('skip link is first in the tab order', (await page.evaluate(() => document.activeElement.className)) === 'skip');
  check('no page errors', errors.length === 0, errors.join(' | '));
  await page.close();
}

async function livePass(browser, tmp) {
  console.log('Part 2 — live page (companion server)');
  if (!fs.existsSync(VC_START)) { console.log('  skip: tools/companion/vc-start.sh not present'); return; }
  if (spawnSync('node', ['--version']).status !== 0) { console.log('  skip: node not present'); return; }
  const planDir = path.join(tmp, 'plans', '2026-11-01-e2e');
  fs.mkdirSync(planDir, { recursive: true });
  fs.copyFileSync(FIXTURE, path.join(planDir, 'plan.json'));
  execFileSync('python3', [TOOL, 'all', path.join(planDir, 'plan.json')], { cwd: planDir });
  let info;
  try { info = JSON.parse(execFileSync('bash', [VC_START, planDir, 'e2e', '--plan'], { encoding: 'utf8' })); }
  catch (e) { console.log('  skip: companion did not start — ' + (e.stderr || e.message)); return; }
  console.log('  companion: ' + info.plan_url);
  const stateFile = info.state_file, eventsFile = info.events_file;
  try {
    const page = await browser.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(info.plan_url);
    check('__MAGICIAN_LIVE injected', await page.evaluate(() => !!window.__MAGICIAN_LIVE && typeof window.__MAGICIAN_LIVE.base === 'string'));
    check('transport resolves to local', (await page.evaluate(() => window.__magicianPage.link())) === 'local');
    check('footer says live', (await page.textContent('#modenote')).startsWith('Live'));
    // go to T3 and request a change from the toolbar
    for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowRight');
    check('on T3', (await page.textContent('#progress')).includes('T3'));
    await page.click('[data-act="change"]');
    check('sheet says Claude will revise', (await page.textContent('#sheet-text')).includes('Claude will revise this step'));
    await page.fill('#cr', 'split the renderer into md and html modules');
    await page.click('#sheet-ok');
    check('revising ring shown', await waitFor(() => page.$('.revising')));
    check('card aria-busy', (await page.getAttribute('#detail', 'aria-busy')) === 'true');
    check('elapsed counter present', /^\d\d:\d\d$/.test(await page.textContent('#elapsed')));
    check('✎ / ✏ disabled while revising', await page.isDisabled('[data-act="change"]') && await page.isDisabled('[data-act="edit"]'));
    const landed = await waitFor(() => fs.existsSync(eventsFile) && fs.readFileSync(eventsFile, 'utf8').includes('"step.change_request"'));
    check('step.change_request appended to events.jsonl', !!landed);
    const line = landed ? JSON.parse(fs.readFileSync(eventsFile, 'utf8').trim().split('\n').find(l => l.includes('step.change_request'))) : {};
    check('event carries step, text, v', line.step === 'T3' && /managed|split/.test(line.text) && line.v === 1, JSON.stringify(line));
    // the skill: write state.revising, then a v2 plan + state
    fs.writeFileSync(stateFile, JSON.stringify({ version: 1, status: 'in_review', revising: { step: 'T3', started_at: new Date().toISOString() }, changed: [], hint: '', notice: '', messages: [{ ts: new Date().toISOString(), text: 'Revising T3 as asked.' }], steps: {} }));
    check('state.messages shows in the transcript', await waitFor(() => page.$$eval('#helperlog .msg', els => els.some(e => e.textContent.includes('Revising T3 as asked.')))));
    const plan = JSON.parse(fs.readFileSync(path.join(planDir, 'plan.json'), 'utf8'));
    plan.version = 2;
    const t3 = plan.steps.find(s => s.id === 'T3');
    t3.intent = 'REVISED: the Markdown renderer and the HTML renderer are separate modules with one shared loader.';
    t3.files.create.push('tools/plan-render-md');
    t3.review.status = 'changed';
    t3.history = [{ v: 2, changed: ['files.create', 'intent'], summary: 'split renderer per reviewer request' }];
    fs.writeFileSync(path.join(planDir, 'plan.json'), JSON.stringify(plan, null, 1));
    execFileSync('python3', [TOOL, 'all', path.join(planDir, 'plan.json')], { cwd: planDir });
    fs.writeFileSync(stateFile, JSON.stringify({ version: 2, status: 'in_review', revising: null, changed: ['T3'], hint: 'T3 is revised — review it again', notice: '', messages: [{ ts: new Date().toISOString(), text: 'Revising T3 as asked.' }, { ts: new Date().toISOString(), text: 'Done: T3 split into two modules (v2).' }], steps: { T3: { review: 'changed' } } }));
    check('page moves to v2', await waitFor(() => page.evaluate(() => window.__magicianPage.version() === 2), 15000));
    check('v2 badge on the card', await waitFor(() => page.$('[data-badge="version"]')));
    check('badge reads v2', (await page.textContent('[data-badge="version"]')) === 'v2');
    check('card shows the revised intent', (await page.textContent('#detailbody')).includes('REVISED: the Markdown renderer'));
    check('step marked changed (re-review)', (await page.textContent('#detailbody')).includes('changed — re-review'));
    check('revising ring gone', !(await page.$('.revising')) && (await page.getAttribute('#detail', 'aria-busy')) === 'false');
    const changed = await page.$('.whatchanged');
    check('"what changed" panel rendered', !!changed);
    const fields = changed ? await page.$$eval('.whatchanged th[scope="row"]', ths => ths.map(t => t.textContent)) : [];
    check('diff lists files.create and intent in plan-render diff order', JSON.stringify(fields) === JSON.stringify(['files.create', 'intent']), JSON.stringify(fields));
    check('hint shown in the transcript', await page.$$eval('#helperlog .msg', els => els.some(e => e.textContent.includes('T3 is revised — review it again'))));
    check('plan.revised line from Claude', await page.$$eval('#helperlog .msg', els => els.some(e => e.textContent.includes('Plan v2 landed — changed: T3'))));
    check('✎ enabled again', !(await page.isDisabled('[data-act="change"]')));
    // approve everything from the header
    await page.click('#approveplan');
    check('confirm sheet lists unreviewed steps', (await page.textContent('#sheet-text')).includes('are not reviewed yet'));
    await page.click('#sheet-ok');
    const approved = await waitFor(() => fs.readFileSync(eventsFile, 'utf8').includes('"plan.approved"'));
    check('plan.approved landed in events.jsonl', !!approved);
    const ap = approved ? JSON.parse(fs.readFileSync(eventsFile, 'utf8').trim().split('\n').find(l => l.includes('plan.approved'))) : {};
    check('plan.approved carries v2 and the per-step map', ap.v === 2 && ap.steps && Object.keys(ap.steps).length === 12 && ap.steps.T3 === 'approved', JSON.stringify(ap).slice(0, 200));
    check('header shows approved', (await page.textContent('#planstatus')) === 'approved');
    check('no page errors', errors.length === 0, errors.join(' | '));
    console.log('  events.jsonl types: ' + fs.readFileSync(eventsFile, 'utf8').trim().split('\n').map(l => JSON.parse(l).type).join(', '));
    await page.close();
  } finally {
    try { execFileSync('bash', [VC_STOP, planDir], { stdio: 'ignore' }); } catch (_) { try { process.kill(info.pid); } catch (__) {} }
  }
}

// A tiny in-page stand-in for the artifact `db` capability (collections of docs, add(), doc().onSnapshot()).
const MOCK_DB = `
  window.__mock = { docs: {}, subs: {}, events: [], failWrites: false, nullDb: false };
  function snap(path) { const d = window.__mock.docs[path]; return { id: path.split('/').pop(), exists: !!d, data: () => d, metadata: { fromCache: false, hasPendingWrites: false } }; }
  window.__mock.write = (path, body) => { window.__mock.docs[path] = body; (window.__mock.subs[path] || []).forEach(fn => fn(snap(path))); };
  const db = {
    doc: (path) => ({ path, get: async () => snap(path), onSnapshot: (next, err) => { (window.__mock.subs[path] = window.__mock.subs[path] || []).push(next); setTimeout(() => next(snap(path)), 0); return () => {}; } }),
    collection: (path) => ({ path, add: async (body) => { if (window.__mock.failWrites) throw { code: 'invalid_argument', message: 'write below the rule level' }; window.__mock.events.push(body); return { id: 'e' + window.__mock.events.length }; } }),
  };
  window.claude = { use: (name) => new Promise((resolve) => setTimeout(() => resolve(name === 'db' && !window.__mock.nullDb ? db : null), 20)) };
`;

async function artifactPass(browser, tmp) {
  console.log('Part 3 — artifact transport (mock claude.use("db"))');
  const html = path.join(tmp, 'artifact.html');
  execFileSync('python3', [TOOL, 'html', FIXTURE, '-o', html, '--transport', 'artifact']);
  const page = await browser.newPage();
  const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.addInitScript(MOCK_DB);
  await page.goto('file://' + html);
  check('starts pending, resolves to artifact', await waitFor(() => page.evaluate(() => window.__magicianPage.link() === 'artifact')));
  check('helper status says Artifact', (await page.textContent('#helperstatus')).startsWith('Artifact'));
  check('subscribed once to state/current and plan/current', await page.evaluate(() => (window.__mock.subs['state/current'] || []).length === 1 && (window.__mock.subs['plan/current'] || []).length === 1));
  await page.keyboard.press('ArrowRight'); await page.keyboard.press('a');
  check('step.review written as one events document', await waitFor(() => page.evaluate(() => window.__mock.events.length === 1 && window.__mock.events[0].type === 'step.review' && window.__mock.events[0].step === 'T1' && typeof window.__mock.events[0].ts === 'string')));
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('c'); await page.fill('#cr', 'use yaml'); await page.keyboard.press('Enter');
  check('step.change_request written; ring shown', await waitFor(() => page.evaluate(() => window.__mock.events.some(e => e.type === 'step.change_request' && e.step === 'T2'))) && !!(await page.$('.revising')));
  await page.evaluate(() => window.__mock.write('state/current', { version: 1, status: 'in_review', revising: { step: 'T2', started_at: new Date().toISOString() }, changed: [], hint: '', notice: 'queued behind nothing', messages: [], steps: {} }));
  check('state notice lands in the transcript', await waitFor(() => page.$$eval('#helperlog .msg', els => els.some(e => e.textContent.includes('queued behind nothing')))));
  const plan = JSON.parse(fs.readFileSync(FIXTURE, 'utf8')); plan.version = 2; const t2 = plan.steps.find(s => s.id === 'T2'); t2.intent = 'REVISED for YAML'; t2.review.status = 'changed';
  await page.evaluate((p) => window.__mock.write('plan/current', p), plan);
  await page.evaluate(() => window.__mock.write('state/current', { version: 2, status: 'in_review', revising: null, changed: ['T2'], hint: '', notice: '', messages: [], steps: { T2: { review: 'changed' } } }));
  check('hot-swapped to v2 from the plan document', await waitFor(() => page.evaluate(() => window.__magicianPage.version() === 2)));
  check('v2 badge + revised intent', (await page.textContent('#detailbody')).includes('REVISED for YAML') && (await page.textContent('[data-badge="version"]')) === 'v2');
  { const f = JSON.stringify(await page.$$eval('.whatchanged th[scope="row"]', t => t.map(x => x.textContent))); check('what changed lists intent', f === '["intent"]', f); }
  await page.evaluate(() => { window.__mock.failWrites = true; });
  await page.keyboard.press('a');
  check('invalid_argument turns the controls read-only', await waitFor(() => page.isDisabled('[data-act="approve"]')) && (await page.isDisabled('#approveplan')) && (await page.isDisabled('#helpersend')));
  check('read-only notice', await page.$$eval('#helperlog .msg', els => els.some(e => e.textContent.includes('read-only'))));
  check('no page errors', errors.length === 0, errors.join(' | '));
  await page.close();
  // null capability ⇒ static with the notice
  const p2 = await browser.newPage();
  await p2.addInitScript(MOCK_DB + 'window.__mock.nullDb = true;');
  await p2.goto('file://' + html);
  check('null db falls back to static', await waitFor(() => p2.evaluate(() => window.__magicianPage.link() === 'static')));
  check('"Artifact without a database — reply in chat" notice', await p2.$$eval('#helperlog .msg', els => els.some(e => e.textContent.includes('Artifact without a database — reply in chat'))));
  check('send button composes chat lines again', (await p2.textContent('#helpersend')) === 'Copy chat line');
  await p2.close();
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'plan-e2e-'));
  const browser = await chromium.launch();
  try { await staticPass(browser, tmp); await artifactPass(browser, tmp); await livePass(browser, tmp); }
  catch (e) { failed++; console.log('  ERROR ' + (e.stack || e)); }
  finally { await browser.close(); fs.rmSync(tmp, { recursive: true, force: true }); }
  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
