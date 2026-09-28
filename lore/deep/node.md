# node — deep dive

> On-demand companion to `lore/node.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Runtime & event loop](#runtime-and-event-loop) · [Modules & packaging](#modules-and-packaging) · [Async, streams & core APIs](#async-streams-and-apis) · [Errors, diagnostics & security](#errors-diagnostics-and-security) · [Testing & tooling](#testing-and-tooling)

## Runtime & event loop <a id="runtime-and-event-loop"></a>

Server-side Node.js runtime: event loop, libuv, modules, streams, scaling. Assumes javascript/typescript lore for language + microtask mechanics. Version facts verified against nodejs.org docs + release schedule (2026-07). Deno/Bun noted only as alternatives.

### Version baseline (LTS lines)

Verify with `node -v` and `process.versions`. As of 2026-07:
- **24 (Krypton)** — **Active LTS** (since 2025-10-28), EOL 2028-04-30. Default target for new work.
- **22 (Jod)** — **Maintenance LTS**, EOL 2027-04-30.
- **20 (Iron)** — **EOL 2026-04-30** (past). **18 (Hydrogen)** — EOL 2025-04-30.
- **DON'T** ship on 18/20 — unsupported, no security patches. **DO** run CI on both 22 and 24.

### Event loop phases (know cold)

One loop thread. Each iteration runs these phases in fixed order, each with a FIFO queue:
1. **timers** — `setTimeout` / `setInterval` callbacks whose threshold elapsed.
2. **pending callbacks** — deferred system I/O callbacks (e.g. TCP `ECONNREFUSED`).
3. **idle, prepare** — internal only.
4. **poll** — retrieve I/O events; run I/O callbacks; block here waiting for I/O if nothing else pending. Most application callbacks fire here.
5. **check** — `setImmediate` callbacks.
6. **close callbacks** — `'close'` events (`socket.on('close')`).

### nextTick vs Promise microtasks (Node-specific)

Between **every** callback (not just between phases) Node drains two queues, in this strict order:
1. **`process.nextTick` queue** — fully drained first (highest priority).
2. **Promise microtask queue** (`.then`/`await`/`queueMicrotask`) — then fully drained.

Only then does the loop advance. So per synchronous chunk: `sync → nextTick → promises → phase callbacks`.

```js
setImmediate(() => console.log('immediate'));
setTimeout(() => console.log('timeout'), 0);
Promise.resolve().then(() => console.log('promise'));
process.nextTick(() => console.log('nextTick'));
console.log('sync');
// sync, nextTick, promise, then timeout/immediate (order varies in main module)
```

- **DON'T** recurse `process.nextTick` (or microtasks) unbounded — starves I/O; the loop never reaches **poll**. Use `setImmediate` to yield instead.
- **DO** prefer `queueMicrotask`/`setImmediate` in library code; reserve `process.nextTick` for "run after this operation, before any I/O" (e.g. deferring an emit so listeners can attach).
- Names are historically swapped: `process.nextTick` fires *sooner* than `setImmediate`.

### setImmediate vs setTimeout(0)

- **Inside an I/O callback** (poll phase): `setImmediate` is **guaranteed** before `setTimeout(fn,0)` — check phase follows poll before the loop wraps to timers.
- **In the main module** (top level): order is **not guaranteed** — depends on process timing.
- **DO** use `setImmediate` to "run right after current I/O". **DON'T** use `setTimeout(fn,0)` for ordering — it also has a ~1ms floor.

### Don't block the loop + libuv threadpool

The loop is single-threaded: any long synchronous callback stalls *all* clients (DoS surface).
- **DON'T** call sync core APIs in a server: `fs.*Sync`, `crypto.pbkdf2Sync`, `zlib.*Sync`, `child_process.execSync`, huge `JSON.parse`.
- **DON'T** write catastrophic-backtracking regex (`(a+)*`) on user input (ReDoS). Bound input sizes.
- **DO** partition CPU loops with `setImmediate`, or offload (below).

**libuv threadpool** ("worker pool") — separate from the loop. Backs async APIs the OS can't do non-blocking:
- `fs.*` (all async, except `fs.watch`), `dns.lookup`/`dns.lookupService`, `crypto.pbkdf2`/`scrypt`/`randomBytes`/`randomFill`/`generateKeyPair`, all async `zlib`.
- **Not** the pool: network sockets (epoll/kqueue), and `dns.resolve*` (direct network).
- Default **`UV_THREADPOOL_SIZE=4`**, max **1024**. Set via env **before** process start: `UV_THREADPOOL_SIZE=8 node app.js`.
- **DO** raise it if you fan out many concurrent fs/crypto/zlib ops (a long task shrinks the pool by one). **DON'T** assume raising it helps network I/O — it doesn't.

### Scale out: worker_threads vs cluster vs child_process

- **CPU-bound JS** → `node:worker_threads`. Threads in one process; can share memory (`SharedArrayBuffer`) or move buffers zero-copy via `transferList`.
- **I/O-bound** → **don't** use workers; native async I/O is already efficient.
- **Scale across cores / isolate crashes** → `node:cluster` (fork loop-per-core sharing a listen socket) or `node:child_process`.

```js
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
if (isMainThread) {
  const w = new Worker(new URL(import.meta.url), { workerData: input });
  w.once('message', done); w.once('error', fail);
} else {
  parentPort.postMessage(heavyCompute(workerData));
}
```
- **DO** pool workers (creation is costly); one per task is wasteful. `worker.terminate()` returns a Promise; supports `await using`.
- **DON'T** expect class instances/prototypes across `postMessage` — structured clone yields plain objects; `Buffer` arrives as `Uint8Array`. `SharedArrayBuffer` is shared (never in `transferList`); a transferred `ArrayBuffer` is unusable on the sender.
- **DON'T** fork a child process per request (fork bomb). Bound the pool.

### Modules (ESM vs CJS)

- **DO** prefer ESM (`"type":"module"` or `.mjs`). `import`/`export`, top-level `await`.
- **ESM has no `__dirname`/`__filename`/`require`.** Use `import.meta.url`, or `import.meta.dirname`/`import.meta.filename` (Node 20.11+). Reconstruct `require` via `createRequire(import.meta.url)`.
- `require()` of a synchronous ES module works unflagged since **Node 22.12** (backported); still fails on ESM with top-level `await`.
- **DO** use `node:` prefix for builtins (`import fs from 'node:fs'`) — explicit, unspoofable.

### Runtime niceties (verify version before relying)

- **Built-in test runner** `node:test` — **stable since Node 20** (added 18). Run `node --test`; globs `**/*.test.js` etc. `--watch` still experimental. Older baselines: use vitest/jest.
- **Native TypeScript** — type-stripping (Amaro) runs `.ts` **flag-free since Node 22.18** (`--experimental-strip-types` before; `--no-strip-types` to disable). Strips erasable syntax only; **no type check**. `enum`/`namespace`/parameter-properties need `--experimental-transform-types`. Use TS 5.7+ and `erasableSyntaxOnly`; still run `tsc --noEmit` in CI.
- **`--env-file=.env`** — no longer experimental since Node 24.10 / 22.21. **`--watch`** restarts on change. **`--run <script>`** runs package.json scripts without npm overhead.
- Global `fetch` is built in (Node 18+). `AbortController`/`AbortSignal` are the cancellation primitive across timers, streams, `fetch`.
- **DON'T** swallow rejections: register `process.on('unhandledRejection')` and `'uncaughtException'` for logging + graceful exit (don't resume after uncaught).

### Streams

- **DO** stream large payloads (`fs.readFile` buffers the whole file into memory).
- **DO** use `pipeline` (from `node:stream/promises`) — propagates errors + cleans up; **DON'T** chain `.pipe()` (leaks on error).
- **DO** respect backpressure: `write()` returning `false` → await `'drain'`; `for await (const chunk of readable)` handles it automatically.

### Alternatives (brief)

- **Deno** — TS-native, permissioned, web-standard APIs, built-in `deno test`.
- **Bun** — fast all-in-one runtime/bundler/test; Node-compat imperfect. Don't assume libuv-phase/threadpool behavior carries over.

### Sources

- https://nodejs.org/en/learn/asynchronous-work/event-loop-timers-and-nexttick
- https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop
- https://nodejs.org/docs/latest/api/worker_threads.html
- https://nodejs.org/docs/latest/api/cluster.html
- https://nodejs.org/docs/latest/api/cli.html
- https://nodejs.org/docs/latest/api/test.html
- https://nodejs.org/en/learn/typescript/run-natively
- https://nodejs.org/docs/latest/api/esm.html
- https://nodejs.org/docs/latest/api/stream.html
- https://github.com/nodejs/release
- https://docs.libuv.org/en/v1.x/threadpool.html

## Modules & packaging <a id="modules-and-packaging"></a>

Node.js runtime (server-side). Assumes javascript/typescript lore. Version cues below are
verified against nodejs.org (checked 2026-07). Current lines: **v26 Current, v24 Active LTS
(Krypton), v22 Maintenance LTS (Jod)**; v20 and v18 are EOL. Target an Active/Maintenance LTS
for production.

### Module system — ESM vs CommonJS

DO
- Set `"type"` explicitly in every `package.json`. `"module"` → `.js` is ESM; `"commonjs"`
  (or omitted) → `.js` is CommonJS. Explicit avoids syntax-detection cost and future drift.
- Rely on extensions to override `"type"` when needed: `.mjs` is **always** ESM, `.cjs` is
  **always** CommonJS (`.cjs` added in Node 12). Extension always wins over `"type"`.
- Prefer ESM for new code. Use `import`/`export`; there is no `module.exports` in ESM.

DON'T
- Don't assume `require('./foo')` resolves `foo.cjs` — it won't. Write `require('./foo.cjs')`.
- Don't mix `require` and `import` in the same file. Don't expect `__dirname`/`__filename`,
  `require`, `module`, or `exports` to exist in ESM.

### `__dirname` / `__filename` in ESM

DO — use `import.meta` (added v20.11.0 / v21.2.0; unflagged/stable v22.16.0 / v24.0.0):
```js
const __dirname = import.meta.dirname;   // dir of current module (file: URLs only)
const __filename = import.meta.filename;  // absolute path, symlinks resolved
// always available:
import { readFileSync } from 'node:fs';
const buf = readFileSync(new URL('./data.bin', import.meta.url));
```
- On Node < 20.11: derive from `import.meta.url`:
  `fileURLToPath(import.meta.url)` (`node:url`) → then `path.dirname(...)`.
- Resolve a specifier: `import.meta.resolve('pkg/asset.css')` returns a string synchronously
  (sync since v20.0.0 / v18.19.0).

DON'T reference `import.meta.dirname` in code that must run on old LTS without a fallback.

### `node:` protocol imports

DO prefix builtins: `import { sep } from 'node:path'`; `require('node:fs')`. `node:` works in
`require()` since v16 / v14.18. It disambiguates builtins from userland packages and is immune
to specifier remapping. Prefer it everywhere.

DON'T rely on bare `'fs'` in new code — a malicious/shadowing package named `fs` can hijack it.

### package.json `"exports"` (the entry contract)

DO
- Use `"exports"` as the entry point (Node 12+; takes precedence over `"main"`). Defining it
  **encapsulates** the package: any subpath not listed throws `ERR_PACKAGE_PATH_NOT_EXPORTED`.
- Target paths must be relative and start with `./`. Export `package.json` if consumers need it.
```json
{
  "exports": {
    ".": "./index.js",
    "./feature": "./src/feature.js",
    "./package.json": "./package.json"
  }
}
```
- Conditional exports — key **order = priority**, `"default"` **last**. Core conditions:
  `node-addons`, `node`, `import`, `require`, `module-sync`, `default`. `"import"`/`"require"`
  are mutually exclusive. Community: `"types"` (list **first**), `"browser"`,
  `"development"`/`"production"`.
```json
{ "exports": { ".": {
  "types": "./index.d.ts",
  "import": "./index.mjs",
  "require": "./index.cjs",
  "default": "./index.mjs"
} } }
```
- Subpath patterns use `*` as pure string replacement (matches across `/`); block subtrees
  with `null`: `{ "./features/*.js": "./src/features/*.js", "./features/internal/*": null }`.

DON'T
- Don't treat `"import"`/`"require"` as "ESM vs CJS" — they mark the *loader used*, not the
  file format. `require` can load static ESM (see below); `import` can load CJS/JSON/WASM.
- Don't keep a bare `"main"` as your only entry if you want encapsulation — add `"exports"`
  (optionally keep `"main"` too for pre-12 tooling).

### package.json `"imports"` (internal aliases)

DO map private internals with a `#` prefix (resolves only inside the package). Unlike
`"exports"`, `"imports"` **can** target external packages — use it for env-specific swaps:
```json
{ "imports": { "#dep": { "node": "dep-native", "default": "./polyfill.js" } } }
```
DON'T use `#`-specifiers from outside the package; they're package-private.

### Dual packages & the dual-package hazard

DO prefer shipping **one** format. If ESM-only, CJS consumers can `require()` it on modern
Node (below). If you must ship both, use `"node"`/`"default"` conditions or `"module-sync"`
to serve **one** module instance to both loaders.

DON'T ship separate `"import"`→ESM and `"require"`→CJS builds of a **stateful** package: the
runtime loads two copies → duplicated state, `instanceof` returns `false`, singletons break.
That's the dual-package hazard.

### require(ESM) — loading ES modules from CommonJS

Version history (verified): added v22.0.0 / v20.17.0 (behind `--experimental-require-module`);
**unflagged v23.0.0 / v22.12.0 / v20.19.0**; **fully stable v25.4.0**.

DO
- On modern LTS, `require('./esm.mjs')` works and returns the module namespace (default under
  `.default`). Detect support at runtime: `process.features.require_module === true`.
- For dynamic/older paths, build a scoped require: `import { createRequire } from 'node:module';
  const require = createRequire(import.meta.url);`

DON'T `require()` an ESM graph that uses **top-level `await`** — throws
`ERR_REQUIRE_ASYNC_MODULE`. Load those with dynamic `import()` instead. (`--no-require-module`
disables the feature entirely.)

### Package managers & lockfiles

DO
- Commit the lockfile: `package-lock.json` (npm), `pnpm-lock.yaml` (pnpm), `yarn.lock` (yarn).
- Use deterministic installs in CI: `npm ci` (npm), `pnpm install --frozen-lockfile`,
  `yarn install --immutable`.
- Pin the manager with the `"packageManager"` field (`"pnpm@9.x.x"`, with hash recommended).
- Consider pnpm for monorepos: content-addressable store + hard links (disk-efficient) and a
  non-flat, symlinked `node_modules` that blocks **phantom dependencies** (undeclared deps
  npm/yarn-classic expose via hoisting).

DON'T
- Don't rely on Corepack being present: bundled with Node 14.19.0 up to (not incl.) **25.0.0**,
  then removed from the distribution. Install the manager explicitly on Node 25+.
- Don't mix managers in one repo, and don't `.gitignore` the lockfile.

### Semver ranges (exact bounds)

DO know what your ranges permit:
- `^1.2.3` → `>=1.2.3 <2.0.0-0` (locks left-most non-zero digit).
- `^0.2.3` → `>=0.2.3 <0.3.0-0`; `^0.0.3` → `>=0.0.3 <0.0.4-0` (0.x is stricter).
- `~1.2.3` → `>=1.2.3 <1.3.0-0`; `~1.2` → `>=1.2.0 <1.3.0-0`; `~1` → `>=1.0.0 <2.0.0-0`.
- `1.2.x`/`1.2` → `>=1.2.0 <1.3.0-0`; `1.2.3 - 2.3.4` → `>=1.2.3 <=2.3.4`.

DON'T use `*`/`latest`/unbounded ranges for dependencies. Declare a real `"engines"` field to
fail installs on unsupported Node versions.

### Runtime alternatives (brief)

Deno (native TS, web-standard APIs, `deno.json`, `npm:` specifiers) and Bun (runtime + bundler +
manager, `bun.lockb`, high Node-compat) both speak ESM natively. Facts above are authoritative
for Node; verify runtime-specific behavior against each project's docs.

### Sources

- https://nodejs.org/docs/latest/api/packages.html
- https://nodejs.org/docs/latest/api/esm.html
- https://nodejs.org/docs/latest/api/modules.html
- https://nodejs.org/en/learn/modules/publishing-a-package
- https://nodejs.org/en/about/previous-releases
- https://github.com/nodejs/corepack#readme
- https://github.com/npm/node-semver
- https://docs.npmjs.com/cli/v10/configuring-npm/package-json
- https://pnpm.io/motivation

## Async, streams & core APIs <a id="async-streams-and-apis"></a>

Node.js RUNTIME layer (server-side). Assumes javascript/typescript lore for language + event-loop mechanics. Version facts verified against nodejs.org docs + release schedule (2026-07).

**Release lines:** 24 "Krypton" = Active LTS, 22 "Jod" = Maintenance LTS, 20 = EOL (2026-04-30); 26 = Current. LTS = even majors. Target Node 22+ (20 is EOL); note 18 fallbacks only when a shop is stuck. Import core modules with the `node:` prefix — unambiguous, faster resolution.

### Never block the event loop
- **DON'T** use sync fs (`readFileSync`, `writeFileSync`), sync `zlib`, `child_process.execSync`, or sync crypto in a request path. One blocked call halts *all* concurrency. Sync fs is acceptable **only** at startup/config load.
- **DON'T** hand-roll callback APIs. Use `node:fs/promises` etc., or wrap legacy callbacks with `node:util`'s `promisify`.
- **DO** offload CPU-bound work (parsing megabytes, hashing, image work) to `worker_threads`; size pools with `os.availableParallelism()` (Node 19.4+/18.14+), not `os.cpus().length`.

### Streams: prefer them for large/unbounded data
Four types, all `EventEmitter`s: `Readable` (source), `Writable` (sink), `Duplex` (both, two buffers), `Transform` (Duplex that maps chunks). Byte mode by default; object mode (`{ objectMode: true }`) carries JS values.

- **DO** consume a Readable with exactly ONE style. Mixing `on('data')`, `on('readable')`, `pipe()`, and `for await` gives undefined behavior. Prefer `for await (const chunk of readable)`.
- **DO** create streams from data: `Readable.from(iterable | asyncIterable)` (generators, arrays).

### Backpressure — the #1 stream bug
`writable.write(chunk)` returns `false` when the internal buffer hits `highWaterMark` (default 16 KB byte mode / 16 objects). Ignoring it = unbounded memory growth, RSS blowup, DoS on sockets that never drain.

- **DON'T** loop `write()` ignoring the return value.
- **DO** let `pipeline()` handle it, or pause when `false` and resume on `'drain'`.

### pipeline() — always pipe with this
Wires stages, propagates errors, destroys/cleans up every stream on finish or failure. **`pipe()` does NOT forward errors or clean up — don't use it in production.**

```js
import { pipeline } from 'node:stream/promises';   // promise form: Node 15+
import { createReadStream, createWriteStream } from 'node:fs';
import { createGzip } from 'node:zlib';

await pipeline(
  createReadStream('in.tar'),
  createGzip(),
  createWriteStream('out.tar.gz'),
  { signal: AbortSignal.timeout(30_000) },          // abortable
);
```
- Async transform stages are plain generators that honor the passed `signal`: `async function* (source, { signal }) { for await (const c of source) yield f(c); }`.
- `finished(stream, { cleanup: true })` (`node:stream/promises`; `cleanup` = 19.1+/18.13+) awaits one stream's end without leaking listeners.

### Web Streams (WHATWG) — for cross-runtime / fetch interop
`ReadableStream`/`WritableStream`/`TransformStream` globals (added 18.0, **marked stable 22.15+/23.11+**). Use at boundaries with `fetch`, `Response.body`, Deno/Bun/browser — not as a wholesale replacement for node streams internally. Bridge with `Readable.toWeb/fromWeb` etc. (**still experimental**; keep at edges). `FileHandle.readableWebStream()` gives a byte `ReadableStream` from a file.

### Buffer vs Uint8Array
`Buffer` is a **subclass of `Uint8Array`** (since 3.0); Node APIs accept plain `Uint8Array` everywhere a Buffer works. Prefer `Uint8Array` for portable code; use `Buffer` for Node-only conveniences (encoding-aware `toString`, `concat`, `byteLength`).
- **DON'T** call `new Buffer(...)` (deprecated, unsafe) — use `Buffer.from(...)` / `Buffer.alloc(...)`.
- **DON'T** ship `Buffer.allocUnsafe(n)` unfilled — pooled, uninitialized memory can leak prior data. Use `Buffer.alloc(n)` (zero-filled) unless you overwrite every byte.
- Encodings: `utf8` (default), `base64`, `base64url`, `hex`, `latin1`, `utf16le`. `Buffer.byteLength(str)` ≠ `str.length`. `Buffer.concat([...])` joins chunks.

### Global fetch
`fetch`/`Request`/`Response`/`Headers`/`FormData` are globals (added 17.5+/16.15+, unflagged 18.0, **stable/no-longer-experimental 21.0**; undici-backed). On Node 18–20 it's usable but pre-stable — for hard reliability there, `undici` directly is an option.
```js
const res = await fetch(url, { signal: AbortSignal.timeout(5_000) });
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const data = await res.json();
```
- **DO** always set a timeout via `AbortSignal.timeout(ms)` — fetch has no default timeout; a hung server hangs you.
- **DO** stream large responses via `res.body` (a Web `ReadableStream`) instead of `.arrayBuffer()`.

### AbortSignal / AbortController — the cancellation currency
Wire it through fetch, streams, timers/promises, and fs.
- `AbortSignal.timeout(ms)` — auto-aborts after delay (17.3+/16.14+).
- `AbortSignal.any([...signals])` — aborts when any input aborts (20.3+/18.17+); combine a user cancel + a timeout.
- `signal.throwIfAborted()` (17.3+/16.17+) at the top of long loops.
- **DO** add `'abort'` listeners with `{ once: true }`; aborted ops reject with `AbortError` (`err.name === 'AbortError'`).

### timers/promises — no more callback timers
`node:timers/promises` (added 15.0, stable 16.0). Abortable, promise-based.
```js
import { setTimeout as sleep, setInterval } from 'node:timers/promises';
await sleep(1000, undefined, { signal });                          // cancellable delay
for await (const _ of setInterval(1000, null, { signal })) tick(); // async-iterator interval
```
- **DON'T** hold the process open with a stray interval — pass `{ ref: false }` or clear it.
- Ordering: `process.nextTick` → Promise microtasks → `setImmediate` (after I/O this tick) → `setTimeout` (≥ delay). `unref()` a timer so it doesn't keep the loop alive.

### node:fs/promises (server default)
`import { readFile, writeFile, readdir, mkdir, rm, open } from 'node:fs/promises';`
- `readFile(p)` → `Buffer`; `readFile(p, 'utf8')` → string.
- `readdir(dir, { withFileTypes: true })` → `Dirent[]` (`isFile()`/`isDirectory()`) — avoids extra `stat` calls.
- `mkdir(p, { recursive: true })`; `rm(p, { recursive: true, force: true })`.
- `open()` → `FileHandle`; **always** `await fh.close()` in `finally` (GC-close only warns). Use `fh.createReadStream()` for ranged/large reads.
- **DO** pass `{ signal }` to abort long reads/writes. **DON'T** fire many concurrent writes at one file — not threadsafe; use a single write stream.

### path & os
- `path.join()` (relative-safe, normalizes) vs `path.resolve()` (always absolute, cwd-anchored). `basename`/`dirname`/`extname`/`parse`. Use `path.posix` / `path.win32` when the style is fixed (e.g. building URLs → `path.posix`).
- **DON'T** concatenate paths with `/`. **DON'T** trust user input in paths — resolve then verify it stays under a root (path traversal).
- `os`: `tmpdir()`, `homedir()`, `platform()`, `availableParallelism()`, `totalmem()`.

### ESM vs CommonJS
- ESM (`"type":"module"` or `.mjs`) has **no `__dirname`/`__filename`/`require`**. Node 21.2+/20.11+: `import.meta.dirname`, `import.meta.filename`. Older: `fileURLToPath(import.meta.url)` + `path.dirname(...)`. Bridge CJS with `createRequire` from `node:module`.
- `structuredClone(value)` — global (17.0+); deep clone (Map/Set/Date/typed arrays; not functions) without `JSON.parse(JSON.stringify())`.

### Alternatives (brief)
Deno/Bun ship Web-standard APIs natively and support many `node:` modules via compat layers. Portable code favors Web Streams + `Uint8Array` + global `fetch` over Buffer/node-stream specifics.

### Sources
- https://nodejs.org/docs/latest/api/stream.html
- https://nodejs.org/docs/latest/api/globals.html
- https://nodejs.org/docs/latest/api/timers.html
- https://nodejs.org/docs/latest/api/fs.html
- https://nodejs.org/docs/latest/api/buffer.html
- https://nodejs.org/docs/latest/api/path.html
- https://nodejs.org/docs/latest/api/os.html
- https://nodejs.org/docs/latest/api/module.html
- https://nodejs.org/en/learn
- https://github.com/nodejs/release

## Errors, diagnostics & security <a id="errors-diagnostics-and-security"></a>

Server-side Node.js runtime layer. Assumes you also have javascript/typescript lore. Targets Node LTS lines **20 / 22 (Jod) / 24 (Krypton)**; 24 is Active LTS, 22 is Maintenance, 20 hit EOL 2026-04-30. Deno/Bun noted only as alternatives.

### Crash-on-fault: unhandledRejection / uncaughtException

DO
- Treat `uncaughtException` and unhandled rejection as **fatal**. Log, flush, exit non-zero, let a supervisor (systemd, k8s, pm2) restart. The process is in an undefined state — do not resume.
- Set a top-level handler for observability + synchronous cleanup only, then exit:
  ```js
  import process from 'node:process';
  process.on('uncaughtException', (err, origin) => {
    logger.fatal({ err, origin });      // sync-ish; don't await long
    process.exitCode = 1;
    // close server to stop new work, then let loop drain, or force-exit on timeout
  });
  process.on('unhandledRejection', (reason) => { throw reason; }); // route to uncaughtException
  ```
- Use `process.exitCode = N` + natural drain over `process.exit(N)`. `exit()` truncates pending stdout/stderr and kills the loop mid-write.
- Use `'uncaughtExceptionMonitor'` when you want to log *without* changing crash behavior (it never suppresses the crash).

DON'T
- Don't use `uncaughtException` as "on error resume next." Continuing after it leaks fds/handles and corrupts state. A `throw` inside the handler exits with the original fatal code (no loop).
- Don't rely on old warn-only rejection behavior. Since Node 15 default is `--unhandled-rejections=throw`: an unhandled rejection becomes an uncaught exception and crashes. Modes: `throw`(default), `strict`, `warn`, `none`.
- Don't `process.exit()` from a worker expecting the whole app to stop — it ends only that thread.

### Request context — AsyncLocalStorage

Stable since **Node 16.4**. The correct way to carry request id / user / tenant across `await` and callbacks without threading args.

DO
```js
import { AsyncLocalStorage } from 'node:async_hooks';
const als = new AsyncLocalStorage();               // {defaultValue, name} opts: Node 24+
app.use((req, _res, next) => als.run({ reqId: crypto.randomUUID() }, next));
function log(msg) { console.log(als.getStore()?.reqId ?? '-', msg); }
```
- Wrap each request in `als.run(store, cb)`. Read with `getStore()` anywhere downstream in that async tree.
- Lost context after a callback-style API? Re-bind with `AsyncResource.bind(fn)` (event listeners) or `AsyncLocalStorage.snapshot()` / `AsyncLocalStorage.bind(fn)` (stable Node 22.15 / 23.11). `util.promisify` callback APIs so native-promise context flows.

DON'T
- Don't prefer `enterWith()` — it persists for the whole sync execution and leaks the store into later, unrelated handlers. Use `run()`.
- Don't reach for raw `async_hooks` (`createHook`) unless building tracing infra — it's low-level and slows the runtime.

### Diagnostics

DO
- Debug: `node --inspect app.js` (attach anytime, binds `127.0.0.1:9229`), `--inspect-brk` (pause at line 1, startup bugs), `--inspect-wait` (block until client attaches). Open `chrome://inspect` or VS Code.
- CPU: `node --cpu-prof app.js` → `.cpuprofile` (load in DevTools ▸ Performance). Tick profiler: `node --prof` then `node --prof-process isolate-*.log`.
- Memory: `v8.writeHeapSnapshot('/tmp/x.heapsnapshot')` in-code; or `--heapsnapshot-signal=SIGUSR2` + `kill -USR2 <pid>`; sampling via `--heap-prof`. Diff two snapshots in DevTools ▸ Memory to find leaks.
- Crash forensics: `--report-uncaught-exception` (JSON diagnostic report with stacks, heap, libuv handles) or `process.report.writeReport()`.
- Dev loop: `node --watch app.js` / `--watch-path=./src` (stable Node 20+). Native `.env`: `node --env-file=.env` (Node 20+; `--env-file-if-exists` tolerates missing).
- Higher-level: `clinic doctor|flame|bubbleprof -- node app.js`.

DON'T
- Don't bind the inspector to `0.0.0.0` or a public IP — it's arbitrary RCE. Use `--inspect` (localhost default) + an SSH tunnel: `ssh -L 9221:localhost:9229 host`.
- Don't leave `--inspect` on in production; disable the `SIGUSR1` inspector trigger (`--disable-sigusr1`) to blunt DNS-rebinding.
- Don't block the event loop with sync I/O (`fs.readFileSync`, `crypto.*Sync`, heavy JSON) in request paths — it stalls every connection. Offload CPU work to `worker_threads`.

### Secrets & env

DO
- Read config from `process.env`; inject via orchestrator/secret manager. Use `node --env-file=.env` or `process.loadEnvFile(path)` for local dev only.
- Keep `.env` in `.gitignore` and `.npmignore`; use `package.json` `files` allowlist; `npm publish --dry-run` before publishing.
- Constant-time secret compare: `crypto.timingSafeEqual(a, b)`. Passwords: `crypto.scrypt`/argon2, never plain `===`.

DON'T
- Don't hardcode keys/tokens in source or commit `.env`. Don't log `process.env` wholesale. If a secret leaks to npm, unpublish + rotate.
- Don't put secrets or PII in URLs/query strings.

### Common vulns

DO
- **Command injection:** use `execFile`/`spawn` with an **args array** (no shell). Reserve `exec`/`execSync` for trusted static strings only.
  ```js
  import { execFile } from 'node:child_process';
  execFile('git', ['show', userInput], cb);   // safe: no shell interpolation
  ```
- **Path traversal:** resolve then confirm containment.
  ```js
  const base = path.resolve(UPLOAD_DIR);
  const p = path.resolve(base, userPath);
  if (p !== base && !p.startsWith(base + path.sep)) throw new Error('bad path');
  ```
- **Prototype pollution:** validate input against a schema (zod/ajv); use `Object.create(null)` maps, `Object.hasOwn(o,k)`, `Object.freeze(proto)`; reject `__proto__`/`constructor`/`prototype` keys; avoid unsafe recursive merge. `--disable-proto=delete` as defense-in-depth.

DON'T
- Don't pass user input into `exec`, `child_process.exec(\`cmd ${x}\`)`, or `shell:true`. Don't `eval`/`new Function` on input.
- Don't join user paths without a containment check; don't trust `..`-stripping regexes.
- Don't deep-merge untrusted JSON into config objects.

### Supply chain & hardening

DO
- Commit `package-lock.json`; CI uses `npm ci` (fails on lockfile drift), not `npm install`. Pin exact versions for apps.
- `npm audit` (and `--audit-level`) in CI; consider `--ignore-scripts` to block install-time code, dependency cooldown `--min-release-age` (npm 11.10+), Socket/Snyk for static analysis.
- **Permission Model** (stable Node 22.13 / 23.5; added 20, was `--experimental-permission`): least-privilege the process.
  ```bash
  node --permission --allow-fs-read=/app --allow-net app.js
  ```
  Flags: `--allow-fs-read`/`--allow-fs-write` (paths/globs/`*`), `--allow-child-process`, `--allow-worker`, `--allow-addons`, `--allow-net`. Check at runtime: `process.permission.has('fs.read', '/x')`; drop irreversibly: `process.permission.drop('child')`.
- HTTP DoS guards: set `server.headersTimeout`, `requestTimeout`, `keepAliveTimeout`; front with a reverse proxy. Never enable `insecureHTTPParser`.

DON'T
- Don't `npm install` in CI or ship without a committed lockfile. Don't run untrusted install scripts blindly.
- Don't treat `--permission` as a sandbox against malicious code — it's a seatbelt vs. accidental access, not a jail.

### Version cues
- ESM: no `__dirname`/`require` — use `import.meta.dirname`/`import.meta.filename` (Node 20.11+); `require(esm)` unflagged Node 22.12+.
- Built-in test runner `node:test` + `node --test`: stable Node 20+. Older lines: vitest/jest.
- `fetch`/`structuredClone` global: Node 18+ (WebSocket client stable 22+).
- TypeScript: run `.ts` directly — type-stripping on by default `node file.ts` (23.6+, backported 22.18+). Otherwise `tsx`/`ts-node` or precompile.

### Sources
- https://nodejs.org/docs/latest/api/process.html
- https://nodejs.org/docs/latest/api/async_context.html
- https://nodejs.org/docs/latest/api/permissions.html
- https://nodejs.org/en/learn/getting-started/security-best-practices
- https://nodejs.org/en/learn/getting-started/debugging
- https://nodejs.org/en/learn/command-line/how-to-read-environment-variables-from-nodejs
- https://github.com/nodejs/release

## Testing & tooling <a id="testing-and-tooling"></a>

Server-side runtime layer. Assumes javascript/typescript lore. Version facts verified against nodejs.org / eslint.org / typescript-eslint.io / vitest.dev (2026-07). LTS context: Node 24 Active LTS, 22 Maintenance, 20 EOL Apr 2026, 26 Current.

### Test runner: pick one

DO default to the **built-in `node:test`** on Node 20+ — zero deps, stable since **v20.0.0**. Reach for a framework only when you need its ecosystem.
DO use **Vitest** (v4; needs Vite ≥6, Node ≥20) for Vite/frontend-adjacent code, ESM/TS out of the box, Jest-compatible `expect`, watch UI, in-source tests.
DO keep **Jest** only on legacy suites; it needs `ts-jest`/`@swc/jest` for TS and its ESM support is still flagged/experimental. Don't start new projects on it.
DON'T mix two runners in one package.

### node:test — the checklist

DO import from the `node:` scheme only; write async or sync, not both.
```js
import { test, describe, it, before, beforeEach, mock } from 'node:test';
import assert from 'node:assert/strict';

describe('orders', () => {
  beforeEach(() => {/* fresh fixture */});
  it('places', async () => { assert.equal(await place(), 'ok'); });
});
```
DO `await` every subtest (`await t.test(...)`) — the parent does **not** wait for un-awaited subtests; they're cancelled and fail. Suites (`describe`) *do* await their `it`s.
DO pass options as the 2nd arg: `{ concurrency, only, skip, todo, timeout, signal }`. `concurrency` default is `false` (serial); set a number or `true` for parallel independent tests.
DO run with `node --test` (globs `**/*.test.{js,ts,…}`, `**/*-test.*`, `test/**`). Filter with `--test-name-pattern=<regex>`; watch with `--test --watch` (experimental).
DON'T rely on test order or shared mutable module state — each file runs in its own child process (`isolation:'process'`) by default.

#### Mocking (built in — no library)
DO use `mock.fn()` / `t.mock.method(obj,'m')`; assert via `fn.mock.callCount()` and `fn.mock.calls[i].arguments`. Per-test `t.mock.*` auto-restores; top-level `mock.*` needs `mock.reset()`/`restoreAll()`.
DO fake time with `mock.timers.enable({ apis:['setTimeout','Date'] })` then `mock.timers.tick(ms)` / `setTime(ts)`. Don't destructure `node:timers` imports — unsupported by the timer mock.

#### assert
DO use `node:assert/strict` (or `assert.strict`) so `equal`/`deepEqual` are `===`-based. Key API: `strictEqual`, `deepStrictEqual`, `throws(fn, expected)`, `await rejects(promise, expected)`, `match(str, re)`.
DON'T use loose `assert.equal` from plain `node:assert` — coercion hides bugs.

#### Snapshots & reporters
DO note snapshot testing is **stable since v23.4.0**; update with `--test-update-snapshots`.
DO pick a reporter with `--test-reporter` (`spec` is the default since v23, plus `tap`, `dot`, `junit`, `lcov`); import from `node:test/reporters`. Multiple reporters need paired `--test-reporter-destination`.

### Coverage

DO use the built-in collector: `node --test --experimental-test-coverage` — still **experimental (Stability 1)**; core + `node_modules/` excluded, scope with `--test-coverage-include/exclude`, emit lcov via `--test-reporter=lcov`.
DO reach for **c8** or Vitest's `@vitest/coverage-v8` when you need thresholds/HTML without the flag. Don't make a coverage % the goal — assert behavior.

### Running & bundling TS

DO run TS directly in dev with **Node's native type stripping** — flagged `--experimental-strip-types` in **v22.6**, unflagged by default since **v23.6 / v22.18**, **stable v24.12 / v25.2**. `tsconfig.json` is ignored; extensions are mandatory (`import './x.ts'`); `.tsx` unsupported.
DON'T use non-erasable syntax under native stripping — **enums, `namespace` with runtime values, parameter properties** need code generation. The transform flag (`--experimental-transform-types`) was **removed in v26**, so on modern Node those require a real transpiler (tsx/swc/tsc). Set `"erasableSyntaxOnly": true` (TS 5.8+) + `"verbatimModuleSyntax": true` to catch this at compile time.
DO use **tsx** when you need full TS features / path aliases / watch that native stripping lacks: `tsx script.ts`, `tsx watch`.
DON'T ship a bundle without a separate **`tsc --noEmit`** — every fast tool below **skips type checking**.

| Tool | Role | Type-check? | Use for |
|---|---|---|---|
| esbuild | bundler + transpiler (Go) | no | fast app/lib bundles, ESM/CJS/IIFE |
| swc | transpiler (Rust) | no | drop-in Babel replacement, `@swc/jest` |
| tsx | TS/ESM runner (esbuild) | no | dev/scripts |
| tsup | esbuild wrapper for **libraries** | emits `.d.ts` | dual ESM+CJS + declarations |
| tsc | official compiler | **yes** | type-check gate, exact `.d.ts` |

DO build publishable **libraries** with `tsup` (`format:['esm','cjs']`, `dts:true`, `sourcemap`, `target`, `minify`) — it wraps esbuild and generates declarations.

### Lint & format

DO use **ESLint flat config** (`eslint.config.{js,mjs,ts}`) — the default since **v9** (2024-04); v10 (current, 2026-02) **removed** the legacy `.eslintrc`. Export an array of config objects with `files`/`ignores`/`languageOptions`/`plugins`/`rules`; wrap in `defineConfig` from `eslint/config`.
```js
import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import tseslint from 'typescript-eslint';

export default defineConfig([
  js.configs.recommended,
  tseslint.configs.recommended,
]);
```
DON'T keep `.eslintrc*` on ESLint 10 — it no longer loads. Don't hand-roll TS parsing; use the **typescript-eslint** (v8) package.
DO enable **type-aware rules** when worth the cost: add `tseslint.configs.recommendedTypeChecked` + `languageOptions.parserOptions.projectService = true` and `tsconfigRootDir: import.meta.dirname`. It's slower (runs a TS build); disable on non-TS files via `disableTypeChecked`. Don't re-implement formatting rules in ESLint.

DO choose one formatter/toolchain:
- **Prettier** — the safe default formatter; pair with ESLint (`eslint-config-prettier` to drop conflicts).
- **Biome** (v2, Rust) — one binary that **lints + formats** JS/TS/JSX/JSON/CSS/GraphQL, near-Prettier compatible, far faster. Config `biome.json`; run `biome check --write` (format + lint + organize imports), `biome ci` in CI. Good for replacing ESLint+Prettier when its rule set covers you; it has fewer plugins/rules than the ESLint ecosystem.
DON'T run both Biome and ESLint+Prettier on the same files — pick one lane.

### Monorepo

DO use **pnpm workspaces** — declare packages in `pnpm-workspace.yaml`; link internals with the `workspace:*` protocol; run across all with `pnpm -r <script>`, target one with `pnpm --filter <pkg>...`. Its strict, content-addressed `node_modules` blocks phantom deps.
DO install reproducibly in CI: `pnpm i --frozen-lockfile`.
DO add **Turborepo** (v2.x) for task orchestration + caching over the workspace. `turbo.json` has a top-level **`tasks`** key (renamed from `pipeline` in **Turbo 2.0**); each task sets `dependsOn` (`"^build"` = build deps first, topological), `outputs` (globs to cache), `inputs`, `cache`, `persistent` (dev servers), `env`.
```json
{ "tasks": { "build": { "dependsOn": ["^build"], "outputs": ["dist/**"] },
             "dev":   { "cache": false, "persistent": true } } }
```
DON'T set `cache:true` on `dev`/watch tasks, and don't let a task `dependsOn` a `persistent` one. **Nx** suits larger/polyglot repos; npm/yarn workspaces are the leaner built-in alternative.

### Alt runtimes (brief)
**Deno** (`deno test`/fmt/lint, TS-native, permissions) and **Bun** (`bun test`, Jest-like, fast; built-in bundler) are all-in-one alternatives. They diverge from Node on some APIs — verify parity before porting.

### Sources
- https://nodejs.org/docs/latest/api/test.html
- https://nodejs.org/docs/latest/api/assert.html
- https://nodejs.org/api/typescript.html
- https://github.com/nodejs/release
- https://eslint.org/docs/latest/use/configure/configuration-files
- https://eslint.org/version-support
- https://typescript-eslint.io/getting-started/
- https://typescript-eslint.io/getting-started/typed-linting/
- https://biomejs.dev/guides/getting-started/
- https://vitest.dev/guide/
- https://esbuild.github.io/
- https://tsup.egoist.dev/
- https://pnpm.io/workspaces
- https://turborepo.dev/docs/reference/configuration
