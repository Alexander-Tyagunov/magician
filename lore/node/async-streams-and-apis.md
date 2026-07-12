# node — Async, streams & core APIs

Node.js RUNTIME layer (server-side). Assumes javascript/typescript lore for language + event-loop mechanics. Version facts verified against nodejs.org docs + release schedule (2026-07).

**Release lines:** 24 "Krypton" = Active LTS, 22 "Jod" = Maintenance LTS, 20 = EOL (2026-04-30); 26 = Current. LTS = even majors. Target Node 22+ (20 is EOL); note 18 fallbacks only when a shop is stuck. Import core modules with the `node:` prefix — unambiguous, faster resolution.

## Never block the event loop
- **DON'T** use sync fs (`readFileSync`, `writeFileSync`), sync `zlib`, `child_process.execSync`, or sync crypto in a request path. One blocked call halts *all* concurrency. Sync fs is acceptable **only** at startup/config load.
- **DON'T** hand-roll callback APIs. Use `node:fs/promises` etc., or wrap legacy callbacks with `node:util`'s `promisify`.
- **DO** offload CPU-bound work (parsing megabytes, hashing, image work) to `worker_threads`; size pools with `os.availableParallelism()` (Node 19.4+/18.14+), not `os.cpus().length`.

## Streams: prefer them for large/unbounded data
Four types, all `EventEmitter`s: `Readable` (source), `Writable` (sink), `Duplex` (both, two buffers), `Transform` (Duplex that maps chunks). Byte mode by default; object mode (`{ objectMode: true }`) carries JS values.

- **DO** consume a Readable with exactly ONE style. Mixing `on('data')`, `on('readable')`, `pipe()`, and `for await` gives undefined behavior. Prefer `for await (const chunk of readable)`.
- **DO** create streams from data: `Readable.from(iterable | asyncIterable)` (generators, arrays).

## Backpressure — the #1 stream bug
`writable.write(chunk)` returns `false` when the internal buffer hits `highWaterMark` (default 16 KB byte mode / 16 objects). Ignoring it = unbounded memory growth, RSS blowup, DoS on sockets that never drain.

- **DON'T** loop `write()` ignoring the return value.
- **DO** let `pipeline()` handle it, or pause when `false` and resume on `'drain'`.

## pipeline() — always pipe with this
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

## Web Streams (WHATWG) — for cross-runtime / fetch interop
`ReadableStream`/`WritableStream`/`TransformStream` globals (added 18.0, **marked stable 22.15+/23.11+**). Use at boundaries with `fetch`, `Response.body`, Deno/Bun/browser — not as a wholesale replacement for node streams internally. Bridge with `Readable.toWeb/fromWeb` etc. (**still experimental**; keep at edges). `FileHandle.readableWebStream()` gives a byte `ReadableStream` from a file.

## Buffer vs Uint8Array
`Buffer` is a **subclass of `Uint8Array`** (since 3.0); Node APIs accept plain `Uint8Array` everywhere a Buffer works. Prefer `Uint8Array` for portable code; use `Buffer` for Node-only conveniences (encoding-aware `toString`, `concat`, `byteLength`).
- **DON'T** call `new Buffer(...)` (deprecated, unsafe) — use `Buffer.from(...)` / `Buffer.alloc(...)`.
- **DON'T** ship `Buffer.allocUnsafe(n)` unfilled — pooled, uninitialized memory can leak prior data. Use `Buffer.alloc(n)` (zero-filled) unless you overwrite every byte.
- Encodings: `utf8` (default), `base64`, `base64url`, `hex`, `latin1`, `utf16le`. `Buffer.byteLength(str)` ≠ `str.length`. `Buffer.concat([...])` joins chunks.

## Global fetch
`fetch`/`Request`/`Response`/`Headers`/`FormData` are globals (added 17.5+/16.15+, unflagged 18.0, **stable/no-longer-experimental 21.0**; undici-backed). On Node 18–20 it's usable but pre-stable — for hard reliability there, `undici` directly is an option.
```js
const res = await fetch(url, { signal: AbortSignal.timeout(5_000) });
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const data = await res.json();
```
- **DO** always set a timeout via `AbortSignal.timeout(ms)` — fetch has no default timeout; a hung server hangs you.
- **DO** stream large responses via `res.body` (a Web `ReadableStream`) instead of `.arrayBuffer()`.

## AbortSignal / AbortController — the cancellation currency
Wire it through fetch, streams, timers/promises, and fs.
- `AbortSignal.timeout(ms)` — auto-aborts after delay (17.3+/16.14+).
- `AbortSignal.any([...signals])` — aborts when any input aborts (20.3+/18.17+); combine a user cancel + a timeout.
- `signal.throwIfAborted()` (17.3+/16.17+) at the top of long loops.
- **DO** add `'abort'` listeners with `{ once: true }`; aborted ops reject with `AbortError` (`err.name === 'AbortError'`).

## timers/promises — no more callback timers
`node:timers/promises` (added 15.0, stable 16.0). Abortable, promise-based.
```js
import { setTimeout as sleep, setInterval } from 'node:timers/promises';
await sleep(1000, undefined, { signal });                          // cancellable delay
for await (const _ of setInterval(1000, null, { signal })) tick(); // async-iterator interval
```
- **DON'T** hold the process open with a stray interval — pass `{ ref: false }` or clear it.
- Ordering: `process.nextTick` → Promise microtasks → `setImmediate` (after I/O this tick) → `setTimeout` (≥ delay). `unref()` a timer so it doesn't keep the loop alive.

## node:fs/promises (server default)
`import { readFile, writeFile, readdir, mkdir, rm, open } from 'node:fs/promises';`
- `readFile(p)` → `Buffer`; `readFile(p, 'utf8')` → string.
- `readdir(dir, { withFileTypes: true })` → `Dirent[]` (`isFile()`/`isDirectory()`) — avoids extra `stat` calls.
- `mkdir(p, { recursive: true })`; `rm(p, { recursive: true, force: true })`.
- `open()` → `FileHandle`; **always** `await fh.close()` in `finally` (GC-close only warns). Use `fh.createReadStream()` for ranged/large reads.
- **DO** pass `{ signal }` to abort long reads/writes. **DON'T** fire many concurrent writes at one file — not threadsafe; use a single write stream.

## path & os
- `path.join()` (relative-safe, normalizes) vs `path.resolve()` (always absolute, cwd-anchored). `basename`/`dirname`/`extname`/`parse`. Use `path.posix` / `path.win32` when the style is fixed (e.g. building URLs → `path.posix`).
- **DON'T** concatenate paths with `/`. **DON'T** trust user input in paths — resolve then verify it stays under a root (path traversal).
- `os`: `tmpdir()`, `homedir()`, `platform()`, `availableParallelism()`, `totalmem()`.

## ESM vs CommonJS
- ESM (`"type":"module"` or `.mjs`) has **no `__dirname`/`__filename`/`require`**. Node 21.2+/20.11+: `import.meta.dirname`, `import.meta.filename`. Older: `fileURLToPath(import.meta.url)` + `path.dirname(...)`. Bridge CJS with `createRequire` from `node:module`.
- `structuredClone(value)` — global (17.0+); deep clone (Map/Set/Date/typed arrays; not functions) without `JSON.parse(JSON.stringify())`.

## Alternatives (brief)
Deno/Bun ship Web-standard APIs natively and support many `node:` modules via compat layers. Portable code favors Web Streams + `Uint8Array` + global `fetch` over Buffer/node-stream specifics.

## Sources
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
