# javascript — Async & the event loop

Language-layer mechanics only. TS-specific typing and Node runtime APIs (timers, streams, `worker_threads`) live in the typescript / node lore. Version facts below verified against MDN + TC39 (2026-07).

## The event loop (know this cold)

Single agent = one call stack + one FIFO task (macrotask) queue + one microtask queue. **Run-to-completion**: a job runs fully; nothing preempts it.

Ordering per turn:
1. Current sync code runs; stack empties.
2. **Entire microtask queue drains** — including microtasks queued *by* microtasks.
3. Exactly **one** macrotask is pulled; then microtasks drain again.

Microtasks: Promise reactions (`.then/.catch/.finally`), `await` continuations, `queueMicrotask()`, `MutationObserver`. Macrotasks: `setTimeout/setInterval`, I/O, UI events.

```js
console.log(1);
setTimeout(() => console.log(4));        // macrotask
Promise.resolve().then(() => console.log(3));
console.log(2);
// 1, 2, 3, 4
```

### DO / DON'T
- **DON'T block the loop.** No long sync loops, huge JSON parse, or sync crypto on the main thread — everything else starves. Chunk work, offload to a Worker, or yield.
- **DON'T starve macrotasks** by recursively queuing microtasks — a microtask that always queues another microtask never lets timers/rendering run.
- **DO** rely on run-to-completion for deterministic ordering; **DON'T** rely on `setTimeout(…, 0)` for ordering vs promises — promises (microtasks) always win.

## Callbacks → Promises → async/await

- **DON'T** write new callback-based async APIs. Return a Promise (or use `node:util.promisify` to wrap legacy callbacks).
- `async` fn **always returns a Promise**; `return x` fulfills, `throw` rejects. A non-promise `return` is wrapped (not identical to `Promise.resolve` — different reference).
- Code up to the first `await` runs **synchronously**; each `await` suspends and resumes as a microtask.

```js
async function load(id) {
  const res = await fetch(`/api/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
```

## Sequential vs parallel await

- **DON'T `await` inside a loop when iterations are independent** — that serializes them.

```js
// DON'T — serial, N × latency
for (const id of ids) results.push(await fetch(id));

// DO — concurrent
const results = await Promise.all(ids.map((id) => fetch(id)));
```

- **DO** kick off independent work first, await later, when you need distinct results:
```js
const a = fetchA();          // start now
const b = fetchB();          // start now
const [x, y] = [await a, await b];
```
- **DO** bound concurrency for large N (chunk, or a pool) — unbounded `Promise.all` over thousands of tasks exhausts sockets/memory.

## Promise combinators (pick the right one)

| Method | Fulfills | Rejects | ES |
|---|---|---|---|
| `Promise.all(it)` | all fulfill → values[] | **first** rejection (fail-fast) | ES2015 |
| `Promise.allSettled(it)` | all settle → `{status,value|reason}[]` | never | ES2020 |
| `Promise.any(it)` | first fulfillment | all reject → `AggregateError` | ES2021 |
| `Promise.race(it)` | first to **settle** (fulfill *or* reject) | first settle is a rejection | ES2015 |

- **DO** use `allSettled` when you want every outcome (don't let one failure discard successful results).
- **DO** use `any` for "first success wins"; `race` for timeouts/first-settled.
- `Promise.withResolvers()` (ES2024) returns `{promise, resolve, reject}` — cleaner than the deferred-in-executor pattern.

## Error handling

- **DO** wrap `await` in `try/catch`; on `.then` chains use `.catch`. `.finally(fn)` runs on both paths (no arg, passes value through).
- **DON'T** build result arrays with separate awaits that can reject out of order — a rejection not yet chained becomes **unhandled**:
```js
// DON'T — if p2 rejects before p1 resolves, .catch won't catch it
const out = [await p1, await p2];
// DO
const out = await Promise.all([p1, p2]);
```
- **DON'T swallow** errors with empty `.catch(() => {})` unless intentional.

## Floating / unhandled promises

- **DON'T** call an async fn and ignore the promise ("floating"). Either `await` it, chain `.catch`, or explicitly `void`+handle.
- A rejected promise with no handler → `unhandledrejection` (browser) / `'unhandledRejection'` (Node, may crash the process). Attach handlers; in Node prefer failing fast over silencing.

## Cancellation — AbortController / AbortSignal

Standard cancellation. `new AbortController()` → pass `.signal` to `fetch`/APIs → `.abort(reason?)`. Aborted fetch rejects with `AbortError`.

```js
const ac = new AbortController();
const p = fetch(url, { signal: ac.signal });
ac.abort();                               // p rejects: err.name === "AbortError"
```

- `AbortSignal.timeout(ms)` — auto-aborting signal (browsers ~2022, Node 17.3+).
- `AbortSignal.any([...signals])` — aborts when any input aborts; combine user-cancel + timeout (browsers 2024, Node 20.3+ / 18.17+).
- `signal.throwIfAborted()` — bail early inside loops. `signal.reason` — why it aborted.
- **DO** thread `signal` through every layer of long-running async work; **DON'T** invent ad-hoc `cancelled` booleans.

## structuredClone

Global (browsers Baseline 2022; Node 17+). Deep clone via structured-clone algorithm; **handles circular refs**, Maps, Sets, typed arrays, `ArrayBuffer`.

```js
const copy = structuredClone(obj);
structuredClone(buf, { transfer: [buf] }); // move, don't copy (detaches original)
```
- **DON'T** clone functions, DOM nodes, or class instances expecting the prototype — throws `DataCloneError` or drops metadata. **DON'T** use `JSON.parse(JSON.stringify(x))` when the data has Dates/Maps/undefined/cycles.

## Version cues (verify against target baseline)

- **Top-level `await`** — ES2022; only in **modules** (`"type":"module"` / `.mjs` / ESM bundles). Sibling modules that import it wait on it.
- **`Array.fromAsync(asyncIterable, mapFn?)`** — ES2024 / Baseline 2024; returns `Promise<Array>`. Iterates **sequentially & lazily** (like `for await…of`) — *not* concurrent. Use `Promise.all` when you want concurrency.
- **`queueMicrotask(cb)`** — schedule a microtask directly; prefer over `Promise.resolve().then` for clarity.
- Older baselines (pre-ES2020 targets, e.g. transpiling to ES2017): `allSettled/any/withResolvers` need polyfills; `structuredClone`/`AbortSignal.timeout` absent on old Node (<17) — feature-detect or polyfill.

## Sources
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Execution_model
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/async_function
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/await
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/fromAsync
- https://developer.mozilla.org/en-US/docs/Web/API/AbortController
- https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal
- https://developer.mozilla.org/en-US/docs/Web/API/Window/structuredClone
- https://developer.mozilla.org/en-US/docs/Web/API/HTML_DOM_API/Microtask_guide
- https://tc39.es/ecma262/
