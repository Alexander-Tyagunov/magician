#!/usr/bin/env node
// magician screen-diff — compare the evidence screenshots of two design versions, pixel by pixel.
//
//   node screen-diff.cjs <dir-v1> <dir-v2> [--out <dir>] [--max-ratio 0.001] [--threshold 0.2] [--engine auto|playwright|stdlib] [--json]
//
// Both folders hold the PNGs capture.md writes (<theme>-<viewport>.png). Every file name present in
// both is compared; a name present in one folder only is reported as added/removed. Comparison uses
// Playwright's own image comparator (the one behind `toHaveScreenshot`) when `playwright` or
// `playwright-core` can be required from the current folder, from this script's location, or from
// a global install (npm global root, or the folder of a `playwright` command on PATH), and writes
// <name>.diff.png to --out (default: <dir-v2>/diff). Without Playwright it decodes the PNGs itself (zlib from the standard
// library, 8-bit RGB/RGBA/grey, non-interlaced) and counts differing pixels; no diff image then.
// --engine auto (default) uses Playwright when found, else the decoder; --engine playwright fails
// with exit 2 when Playwright is not found; --engine stdlib always uses the decoder.
// No other dependency; nothing is installed; nothing is fetched.
//
// Exit 0: every shared screenshot is within --max-ratio. Exit 1: at least one is not (or sizes
// differ). Exit 2: usage error or an unreadable file.
'use strict';
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

function usage(msg) {
  if (msg) process.stderr.write(msg + '\n');
  process.stderr.write('usage: node screen-diff.cjs <dir-v1> <dir-v2> [--out <dir>] [--max-ratio 0.001] [--threshold 0.2] [--engine auto|playwright|stdlib] [--json]\n');
  process.exit(2);
}

function parseArgs(argv) {
  const opts = { dirs: [], out: null, maxRatio: 0.001, threshold: 0.2, engine: 'auto', json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') opts.out = argv[++i];
    else if (a === '--max-ratio') opts.maxRatio = Number(argv[++i]);
    else if (a === '--threshold') opts.threshold = Number(argv[++i]);
    else if (a === '--engine') opts.engine = argv[++i];
    else if (a === '--json') opts.json = true;
    else if (a.startsWith('--')) usage('unknown option ' + a);
    else opts.dirs.push(a);
  }
  if (opts.dirs.length !== 2) usage('two folders are required');
  if (!(opts.maxRatio >= 0 && opts.maxRatio <= 1)) usage('--max-ratio must be between 0 and 1');
  if (!(opts.threshold >= 0 && opts.threshold <= 1)) usage('--threshold must be between 0 and 1');
  if (!['auto', 'playwright', 'stdlib'].includes(opts.engine)) usage('--engine must be auto, playwright or stdlib');
  for (const d of opts.dirs) if (!fs.statSync(d, { throwIfNoEntry: false })?.isDirectory()) usage('not a folder: ' + d);
  if (!opts.out) opts.out = path.join(opts.dirs[1], 'diff');
  return opts;
}

// Playwright's comparator, if present. It returns null when the images match, else
// { errorMessage, diff? } where diff is a PNG buffer highlighting the changed pixels.
// Module names, in order: Playwright >= 1.63 exports the comparator from lib/coreBundle (as
// .utils.getComparator); older releases export it from lib/utils.
const COMPARATOR_MODULES = [
  ['playwright-core/lib/coreBundle', (m) => m && m.utils],
  ['playwright/lib/coreBundle', (m) => m && m.utils],
  ['playwright-core/lib/utils', (m) => m],
  ['playwright/lib/utils', (m) => m],
];

// Folders where a global Playwright can be: the npm global root next to this node binary, the
// npm prefix, and the node_modules folder that holds a `playwright` command found on PATH.
function globalModuleRoots() {
  const roots = [];
  const add = (d) => { if (d && !roots.includes(d) && fs.existsSync(d)) roots.push(d); };
  add(path.join(path.dirname(process.execPath), '..', 'lib', 'node_modules'));
  if (process.env.npm_config_prefix) add(path.join(process.env.npm_config_prefix, 'lib', 'node_modules'));
  for (const dir of (process.env.PATH || '').split(path.delimiter)) {
    if (!dir) continue;
    try {
      const real = fs.realpathSync(path.join(dir, 'playwright'));
      // <root>/node_modules/.bin/playwright -> <root>/node_modules/playwright/cli.js
      let d = path.dirname(real);
      while (d !== path.dirname(d) && path.basename(d) !== 'node_modules') d = path.dirname(d);
      if (path.basename(d) === 'node_modules') add(d);
    } catch (e) { /* no playwright command in this PATH folder */ }
  }
  return roots;
}

// Resolve each module from the project cwd first, then from this script's location (plain
// require, which includes NODE_PATH), then from the global roots.
function loadPlaywrightComparator() {
  const { createRequire } = require('module');
  const loaders = [
    (mod) => createRequire(path.join(process.cwd(), '/'))(mod),
    (mod) => require(mod),
    (mod) => require(require.resolve(mod, { paths: globalModuleRoots() })),
  ];
  for (const load of loaders) {
    for (const [mod, pick] of COMPARATOR_MODULES) {
      try {
        const utils = pick(load(mod));
        if (utils && typeof utils.getComparator === 'function') return utils.getComparator('image/png');
      } catch (e) { /* not installed here; try the next location or name */ }
    }
  }
  return null;
}

// Minimal PNG decoder: 8-bit depth, colour types 0 (grey), 2 (RGB), 4 (grey+alpha), 6 (RGBA),
// no interlace. Returns { width, height, channels, data } with data as raw samples.
function decodePng(buf) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (buf.length < 8 || !buf.subarray(0, 8).equals(sig)) throw new Error('not a PNG');
  let pos = 8, width = 0, height = 0, depth = 0, ctype = 0, interlace = 0;
  const idat = [];
  while (pos + 8 <= buf.length) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString('ascii', pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4);
      depth = data[8]; ctype = data[9]; interlace = data[12];
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    pos += 12 + len;
  }
  if (depth !== 8 || interlace !== 0) throw new Error('unsupported PNG (need 8-bit, non-interlaced)');
  const channels = { 0: 1, 2: 3, 4: 2, 6: 4 }[ctype];
  if (!channels) throw new Error('unsupported PNG colour type ' + ctype);
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = width * channels;
  const out = Buffer.alloc(stride * height);
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    const cur = out.subarray(y * stride, (y + 1) * stride);
    for (let i = 0; i < stride; i++) {
      const a = i >= channels ? cur[i - channels] : 0;
      const b = prev[i];
      const c = i >= channels ? prev[i - channels] : 0;
      let v = line[i];
      if (filter === 1) v += a;
      else if (filter === 2) v += b;
      else if (filter === 3) v += (a + b) >> 1;
      else if (filter === 4) {
        const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        v += (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
      } else if (filter !== 0) throw new Error('bad PNG filter ' + filter);
      cur[i] = v & 255;
    }
    prev = cur;
  }
  return { width, height, channels, data: out };
}

// Fallback comparison: a pixel differs when any channel differs by more than threshold * 255.
function compareDecoded(a, b, threshold) {
  if (a.width !== b.width || a.height !== b.height || a.channels !== b.channels) {
    return { sizeMismatch: true, ratio: 1, pixels: 0, total: 0 };
  }
  const tol = Math.round(threshold * 255);
  const total = a.width * a.height;
  let pixels = 0;
  for (let p = 0; p < total; p++) {
    const o = p * a.channels;
    for (let c = 0; c < a.channels; c++) {
      if (Math.abs(a.data[o + c] - b.data[o + c]) > tol) { pixels++; break; }
    }
  }
  return { sizeMismatch: false, ratio: pixels / total, pixels, total };
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const [dirA, dirB] = opts.dirs;
  const pngs = (d) => new Set(fs.readdirSync(d).filter((f) => f.toLowerCase().endsWith('.png') && !f.endsWith('.diff.png')));
  const a = pngs(dirA), b = pngs(dirB);
  const comparator = opts.engine === 'stdlib' ? null : loadPlaywrightComparator();
  if (!comparator && opts.engine === 'playwright') usage('--engine playwright: Playwright not found');
  const results = [];
  let failed = false;
  for (const name of [...new Set([...a, ...b])].sort()) {
    if (!a.has(name)) { results.push({ name, status: 'added' }); continue; }
    if (!b.has(name)) { results.push({ name, status: 'removed' }); continue; }
    const bufA = fs.readFileSync(path.join(dirA, name));
    const bufB = fs.readFileSync(path.join(dirB, name));
    if (bufA.equals(bufB)) { results.push({ name, status: 'same', engine: comparator ? 'playwright' : 'stdlib', ratio: 0 }); continue; }
    if (comparator) {
      const r = comparator(bufA, bufB, { maxDiffPixelRatio: opts.maxRatio, threshold: opts.threshold });
      if (!r) { results.push({ name, status: 'same', ratio: 0, engine: 'playwright' }); continue; }
      let diffPath = null;
      if (r.diff) {
        fs.mkdirSync(opts.out, { recursive: true });
        diffPath = path.join(opts.out, name.replace(/\.png$/i, '.diff.png'));
        fs.writeFileSync(diffPath, r.diff);
      }
      failed = true;
      // Playwright reports "<n> pixels (ratio <r> of all image pixels) are different."; the
      // PNG header gives the size, so the ratio here is exact.
      const m = /(\d+) pixels/.exec(r.errorMessage || '');
      const total = bufB.length >= 24 ? bufB.readUInt32BE(16) * bufB.readUInt32BE(20) : 0;
      const extra = m && total ? { ratio: Number((Number(m[1]) / total).toFixed(6)), pixels: Number(m[1]), total } : {};
      results.push({ name, status: 'changed', engine: 'playwright', ...extra, message: r.errorMessage, diff: diffPath });
      continue;
    }
    let r;
    try { r = compareDecoded(decodePng(bufA), decodePng(bufB), opts.threshold); }
    catch (e) { process.stderr.write(name + ': ' + e.message + '\n'); process.exit(2); }
    const status = r.sizeMismatch ? 'size-mismatch' : (r.ratio > opts.maxRatio ? 'changed' : 'same');
    if (status !== 'same') failed = true;
    results.push({ name, status, engine: 'stdlib', ratio: Number(r.ratio.toFixed(6)), pixels: r.pixels, total: r.total });
  }
  if (opts.json) process.stdout.write(JSON.stringify({ a: dirA, b: dirB, maxRatio: opts.maxRatio, results }, null, 2) + '\n');
  else {
    for (const r of results) {
      const extra = r.ratio !== undefined && r.status !== 'same' ? ` (${(r.ratio * 100).toFixed(2)}% of pixels)` : '';
      process.stdout.write(`${r.status.padEnd(13)} ${r.name}${extra}${r.diff ? ' -> ' + r.diff : ''}\n`);
    }
    process.stdout.write(`${results.filter((r) => r.status === 'same').length} same, ${results.filter((r) => r.status !== 'same').length} differ (engine: ${comparator ? 'playwright' : 'stdlib'})\n`);
  }
  process.exit(failed ? 1 : 0);
}

main();
