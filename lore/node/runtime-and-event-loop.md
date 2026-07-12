# node — Runtime & event loop

Server-side Node.js runtime: event loop, libuv, modules, streams, scaling. Assumes javascript/typescript lore for language + microtask mechanics. Version facts verified against nodejs.org docs + release schedule (2026-07). Deno/Bun noted only as alternatives.

## Version baseline (LTS lines)

Verify with `node -v` and `process.versions`. As of 2026-07:
- **24 (Krypton)** — **Active LTS** (since 2025-10-28), EOL 2028-04-30. Default target for new work.
- **22 (Jod)** — **Maintenance LTS**, EOL 2027-04-30.
- **20 (Iron)** — **EOL 2026-04-30** (past). **18 (Hydrogen)** — EOL 2025-04-30.
- **DON'T** ship on 18/20 — unsupported, no security patches. **DO** run CI on both 22 and 24.

## Event loop phases (know cold)

One loop thread. Each iteration runs these phases in fixed order, each with a FIFO queue:
1. **timers** — `setTimeout` / `setInterval` callbacks whose threshold elapsed.
2. **pending callbacks** — deferred system I/O callbacks (e.g. TCP `ECONNREFUSED`).
3. **idle, prepare** — internal only.
4. **poll** — retrieve I/O events; run I/O callbacks; block here waiting for I/O if nothing else pending. Most application callbacks fire here.
5. **check** — `setImmediate` callbacks.
6. **close callbacks** — `'close'` events (`socket.on('close')`).

## nextTick vs Promise microtasks (Node-specific)

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

## setImmediate vs setTimeout(0)

- **Inside an I/O callback** (poll phase): `setImmediate` is **guaranteed** before `setTimeout(fn,0)` — check phase follows poll before the loop wraps to timers.
- **In the main module** (top level): order is **not guaranteed** — depends on process timing.
- **DO** use `setImmediate` to "run right after current I/O". **DON'T** use `setTimeout(fn,0)` for ordering — it also has a ~1ms floor.

## Don't block the loop + libuv threadpool

The loop is single-threaded: any long synchronous callback stalls *all* clients (DoS surface).
- **DON'T** call sync core APIs in a server: `fs.*Sync`, `crypto.pbkdf2Sync`, `zlib.*Sync`, `child_process.execSync`, huge `JSON.parse`.
- **DON'T** write catastrophic-backtracking regex (`(a+)*`) on user input (ReDoS). Bound input sizes.
- **DO** partition CPU loops with `setImmediate`, or offload (below).

**libuv threadpool** ("worker pool") — separate from the loop. Backs async APIs the OS can't do non-blocking:
- `fs.*` (all async, except `fs.watch`), `dns.lookup`/`dns.lookupService`, `crypto.pbkdf2`/`scrypt`/`randomBytes`/`randomFill`/`generateKeyPair`, all async `zlib`.
- **Not** the pool: network sockets (epoll/kqueue), and `dns.resolve*` (direct network).
- Default **`UV_THREADPOOL_SIZE=4`**, max **1024**. Set via env **before** process start: `UV_THREADPOOL_SIZE=8 node app.js`.
- **DO** raise it if you fan out many concurrent fs/crypto/zlib ops (a long task shrinks the pool by one). **DON'T** assume raising it helps network I/O — it doesn't.

## Scale out: worker_threads vs cluster vs child_process

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

## Modules (ESM vs CJS)

- **DO** prefer ESM (`"type":"module"` or `.mjs`). `import`/`export`, top-level `await`.
- **ESM has no `__dirname`/`__filename`/`require`.** Use `import.meta.url`, or `import.meta.dirname`/`import.meta.filename` (Node 20.11+). Reconstruct `require` via `createRequire(import.meta.url)`.
- `require()` of a synchronous ES module works unflagged since **Node 22.12** (backported); still fails on ESM with top-level `await`.
- **DO** use `node:` prefix for builtins (`import fs from 'node:fs'`) — explicit, unspoofable.

## Runtime niceties (verify version before relying)

- **Built-in test runner** `node:test` — **stable since Node 20** (added 18). Run `node --test`; globs `**/*.test.js` etc. `--watch` still experimental. Older baselines: use vitest/jest.
- **Native TypeScript** — type-stripping (Amaro) runs `.ts` **flag-free since Node 22.18** (`--experimental-strip-types` before; `--no-strip-types` to disable). Strips erasable syntax only; **no type check**. `enum`/`namespace`/parameter-properties need `--experimental-transform-types`. Use TS 5.7+ and `erasableSyntaxOnly`; still run `tsc --noEmit` in CI.
- **`--env-file=.env`** — no longer experimental since Node 24.10 / 22.21. **`--watch`** restarts on change. **`--run <script>`** runs package.json scripts without npm overhead.
- Global `fetch` is built in (Node 18+). `AbortController`/`AbortSignal` are the cancellation primitive across timers, streams, `fetch`.
- **DON'T** swallow rejections: register `process.on('unhandledRejection')` and `'uncaughtException'` for logging + graceful exit (don't resume after uncaught).

## Streams

- **DO** stream large payloads (`fs.readFile` buffers the whole file into memory).
- **DO** use `pipeline` (from `node:stream/promises`) — propagates errors + cleans up; **DON'T** chain `.pipe()` (leaks on error).
- **DO** respect backpressure: `write()` returning `false` → await `'drain'`; `for await (const chunk of readable)` handles it automatically.

## Alternatives (brief)

- **Deno** — TS-native, permissioned, web-standard APIs, built-in `deno test`.
- **Bun** — fast all-in-one runtime/bundler/test; Node-compat imperfect. Don't assume libuv-phase/threadpool behavior carries over.

## Sources

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
