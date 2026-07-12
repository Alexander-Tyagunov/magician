# javascript — Errors & resource handling

Language-layer mechanics only. TypeScript config (`lib`, `target`) lives in typescript lore; Node process tuning lives in node lore.

## Throwing

DO throw `Error` or an `Error` subclass — always. Catchers rely on `.message`, `.stack`, `.name`, `instanceof`.
DON'T throw strings, numbers, plain objects, or `undefined`. `throw "boom"` gives no stack and breaks `err.message`.

```js
// DON'T
throw "user not found";
// DO
throw new TypeError("id must be a number");
```

DO use the right built-in subclass: `TypeError` (wrong type/shape), `RangeError` (out of bounds), `SyntaxError`, `ReferenceError`. Reach for these before inventing one.
DON'T put a line break after `throw` — ASI turns `throw\n new Error()` into invalid `throw;`.

## Custom errors + cause (ES2022)

DO subclass `Error` and set `name`. Message stays human; attach machine-readable fields as own properties.

```js
class HttpError extends Error {
  constructor(message, { status, cause } = {}) {
    super(message, { cause });   // cause forwarded to Error()
    this.name = "HttpError";
    this.status = status;
  }
}
```

DO chain with `cause` (2nd arg options bag) when wrapping a lower-level failure — preserves the original stack for debugging.

```js
try { await db.query(sql); }
catch (err) { throw new HttpError("load failed", { status: 500, cause: err }); }
```

- `new Error(msg, { cause })` — ES2022. Baseline since Sep 2021 (Chrome/Edge 93, Firefox 91, Safari 15); Node 16.9+.
- `cause` may be any value; access via `err.cause`. It's non-enumerable.

DON'T lose the cause by rethrowing a bare `new Error(err.message)` — you drop the original stack.
DON'T rely on `Error.captureStackTrace` (V8-only) for portable code.
DON'T `instanceof` a subclass across realms (iframe/worker/vm) — check a `code` property instead.

## try / catch / finally

DO scope `try` tightly — wrap only the throwing call, not unrelated logic.
DO use `catch {}` (optional binding, ES2019) when you don't need the error.
DON'T swallow silently. If you catch, either handle, rethrow, or wrap with `cause`.
DON'T return from `finally` — it overrides a `return`/`throw` from `try`/`catch` and hides errors.

```js
// DON'T — finally's return masks the throw
try { throw new Error("x"); } finally { return 1; } // returns 1, error gone
```

DO narrow before acting on a caught value (it's `unknown`-shaped — could be anything thrown):

```js
catch (err) {
  if (err instanceof HttpError && err.status === 404) return null;
  throw err;
}
```

## Async propagation

DO `await` inside `try` to catch rejection; a returned-but-unawaited promise escapes the `try`.

```js
// DON'T — rejection escapes; catch never fires
try { return fetchUser(id); } catch { /* dead */ }
// DO
try { return await fetchUser(id); } catch (e) { /* handled */ }
```

DON'T mix `.then().catch()` chains with `try/catch` on the same call — pick one.
DO use `Promise.allSettled` when partial failure is acceptable; `Promise.all` rejects on first failure and abandons the rest.
DO reject with an `Error`, never a string: `reject(new Error(...))`.
DON'T create floating promises — an unhandled rejection can crash Node (see below).

## Process/global last-resort handlers

Browser:
```js
window.addEventListener("error", (e) => report(e.error));           // sync + resource errors
window.addEventListener("unhandledrejection", (e) => report(e.reason)); // e.preventDefault() to silence
```

Node:
```js
process.on("uncaughtException", (err, origin) => { logSync(err); process.exit(1); });
process.on("unhandledRejection", (reason) => { logSync(reason); process.exit(1); });
```

- `uncaughtException` handler args: `(err, origin)`. Default (no handler): print stack, exit 1.
- `unhandledRejection` args: `(reason, promise)`. Node 15+ default (`--unhandled-rejections=throw`): promoted to an uncaught exception → process terminates non-zero.
- `uncaughtExceptionMonitor` (Node 13.7/12.17+): observe without suppressing the crash — use for logging.

DO treat these as crash-logging + graceful-shutdown only. Flush logs, close handles, then exit.
DON'T resume normal operation after `uncaughtException` — state may be corrupt. It is not "on error resume next".

## Cleanup patterns

DO release resources in `finally` so they run on both success and throw.

```js
const conn = await pool.acquire();
try { return await conn.run(q); }
finally { await conn.release(); }
```

DO pass an `AbortSignal` to cancel async work; listen and clean up on `abort`.
DON'T rely on GC/`finalizers` for deterministic cleanup — `FinalizationRegistry` timing is unspecified.

## Explicit resource management: `using` / `await using`

Stage 4 (finished, TC39) — expected ES2027, **not** ES2026. Runtime support: Node 24+ (V8 13.6, no flag); TypeScript 5.2+ emits the syntax (needs `lib: esnext.disposable`). Older targets: polyfill `Symbol.dispose`/`Symbol.asyncDispose` or stay on `try/finally`.

DO give a resource a `[Symbol.dispose]()` (sync) or `[Symbol.asyncDispose]()` (async) method; the disposer runs automatically when the binding leaves scope.

```js
function openFile(path) {
  const fd = fs.openSync(path, "r");
  return { fd, [Symbol.dispose]() { fs.closeSync(fd); } };
}
{
  using f = openFile("./a.txt");   // f[Symbol.dispose]() runs at block end
  read(f.fd);
}                                  // ...even if read() throws

async function q() {
  await using conn = await pool.acquire(); // awaits [Symbol.asyncDispose]()
  return conn.run(sql);
}
```

- Disposers run in **reverse** declaration order (stack/LIFO).
- `using` bindings are block-scoped, const-like (no reassign), must init to `null`/`undefined`/an object with the disposer method.
- If both the body and a disposer throw, you get a `SuppressedError` (`.error` = disposer's, `.suppressed` = original).
- `await using` is only valid in async contexts (module top level, async function, `for await`).

DO use `DisposableStack` / `AsyncDisposableStack` (`.use()`, `.defer()`, `.adopt()`) for dynamic/conditional cleanup instead of nested `try/finally`.
DON'T use `using` at the top level of a **script** (only modules) or in a `for...in` head.

## Sources

- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/throw
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Error/cause
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/using
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/try...catch
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Symbol/dispose
- https://nodejs.org/api/process.html#event-unhandledrejection
- https://nodejs.org/en/blog/release/v24.0.0
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html
- https://github.com/tc39/proposal-explicit-resource-management
- https://github.com/tc39/proposals/blob/main/finished-proposals.md
