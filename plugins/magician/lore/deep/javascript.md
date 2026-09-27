# javascript — deep dive

> On-demand companion to `lore/javascript.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Language & idioms](#language-and-idioms) · [Async & the event loop](#async) · [Types, coercion & pitfalls](#types-and-coercion) · [Errors & resource handling](#errors-and-resources)

## Language & idioms <a id="language-and-idioms"></a>

Language layer only. TypeScript typing and Node runtime APIs live in their own lore.
Baseline: **ES2015+**. Gate newer syntax by target/runtime — years below are when each
feature landed in the ECMAScript standard (MDN's spec links say "ES2027" only because
they point at the living draft; ignore that number).

### Declarations

DO use `const` by default; `let` only when reassigned.
DON'T use `var` — it is function-scoped and hoisted, causing leaks and TDZ-free bugs.
DON'T rely on `const` for deep immutability — it only fixes the binding, not the value.

```js
const list = [1];
list.push(2); // allowed — binding is const, contents are not
```

### Equality & comparison

DO use `===` / `!==` always.
DON'T use `==` — its coercions are surprising (`0 == ""`, `null == undefined`, `[] == false`).
DO use one intentional exception: `x == null` to test "null or undefined" in one check.
DO use `Object.is` for `NaN` / `±0` edge cases (`Object.is(NaN, NaN) === true`).

### Nullish handling (ES2020 / ES2021)

DO use optional chaining `?.` to short-circuit on `null`/`undefined`: `user?.profile?.name`,
`obj?.method?.()`, `arr?.[i]`.
DO use nullish coalescing `??` for defaults — unlike `||`, it keeps `0`, `''`, `false`.
DON'T mix `??` with `||`/`&&` without parens — it's a syntax error by design.
DO use logical assignment (ES2021): `opts.timeout ??= 100`, `flag ||= true`, `x &&= f(x)`.

```js
const port = cfg.port ?? 8080;   // 0 would survive; `|| 8080` would not
(a ?? b) || c;                   // parens required
```

### Destructuring, spread, rest

DO destructure with defaults + rename: `const { id, name: label = "?" } = obj;`.
DO use rest to collect: `const [first, ...tail] = arr;`, `const { a, ...others } = obj;`.
DO copy/merge shallowly with spread: `{ ...base, ...overrides }`, `[...a, ...b]`.
DON'T assume spread is deep — nested objects are shared references.
DO deep-clone with `structuredClone(value)` (global in modern browsers and Node 17+),
not `JSON.parse(JSON.stringify(...))` (drops `undefined`, `Date`, `Map`, functions).

### Template literals

DO use backticks for interpolation and multiline: `` `Hi ${name}` ``.
DON'T build HTML/SQL/shell strings by interpolation — use a proper builder/escaper.

### Functions, `this`, arrows

DO use arrow functions for callbacks — they capture lexical `this`, no `.bind(this)`.
DON'T use arrows for object methods needing dynamic `this`, or as constructors, or where
`arguments`/`new.target` are needed.
DO know method `this` is set by the call site: `obj.fn()` → `obj`; a detached `const f =
obj.fn; f()` → `undefined` (strict) — re-bind or wrap in an arrow.

```js
btn.addEventListener("click", () => this.handle()); // lexical this ✅
const m = { n: 1, get() { return this.n; } };
const g = m.get; g();                                // undefined — detached
```

### Closures

DO use closures for private state and factories. Each call frame captures its own bindings.
DO use `let`/`const` in loops so each iteration closes over a fresh binding (a classic `var`
bug — all callbacks share one variable).

### Prototypes vs classes

DO use `class` syntax for constructors, inheritance (`extends`/`super`), and clarity.
DO use public/private class fields (**ES2022**): `#secret` is truly private; accessing an
uninitialized `#field` throws.
DON'T mutate `Object.prototype` or built-in prototypes (monkey-patching breaks everyone).

```js
class Counter {
  #n = 0;                 // private, ES2022
  static make() { return new Counter(); }
  inc() { this.#n++; return this; }
}
```

### Modules (ESM)

DO use `import`/`export`; prefer named exports for discoverability, default sparingly.
DO note imports are hoisted, live read-only bindings — you can't reassign an import.
DO use dynamic `import()` (returns a Promise) for lazy/conditional loading.
DO use top-level `await` (**ES2022**) — only inside ES modules, not CommonJS/scripts.
DON'T mix CommonJS `require`/`module.exports` with ESM in the same file.

### Immutability habits

DO treat data as immutable: build new values with spread / `map` / `filter` / `reduce`.
DO use copy-array methods (**ES2023**) instead of mutating: `toSorted`, `toReversed`,
`toSpliced`, `with(i, v)` — the mutating `sort`/`reverse`/`splice` change in place.
DO `Object.freeze` for shallow runtime lock (dev/config); it's not deep.

```js
const sorted = nums.toSorted((a, b) => a - b); // original untouched (ES2023)
const next = arr.with(0, "x");                 // copy with index 0 replaced
```

### Map/Set vs object

DO use `Map` for keyed collections: any key type, real `.size`, ordered iteration, no
prototype-pollution keys. Use `Set` for uniqueness / membership.
DON'T use a plain object as a hash map for arbitrary/user keys (proto keys, string-only,
inherited props). If you must, use `Object.create(null)` or `Object.hasOwn` (**ES2022**).
DO prefer `Object.hasOwn(obj, k)` over `obj.hasOwnProperty(k)` — safe on null-proto objects
and immune to overrides. `key in obj` also walks the prototype chain.

```js
const seen = new Set(ids);
const byId = new Map(rows.map((r) => [r.id, r]));
Object.hasOwn(cfg, "port"); // ✅ ES2022
```

### Array / object method idioms

DO reach for declarative iteration: `map`, `filter`, `reduce`, `find`, `some`, `every`,
`flatMap`. Use `for...of` for side effects / early `break`; `Object.entries/keys/values`
to iterate objects.
DON'T use `for...in` on arrays (walks proto chain, string keys, unordered).
DO use `arr.at(-1)` for last element (**ES2022**), `findLast`/`findLastIndex` (**ES2023**).
DO use `Object.groupBy(items, fn)` / `Map.groupBy` (**ES2024**) — gate by runtime support.
DON'T call `Array.prototype.forEach` when you need the result — it returns `undefined`.

### Async (language level)

DO use `async`/`await` with `try/catch`; run independent work concurrently with
`Promise.all` (or `allSettled` when partial failure is tolerable).
DON'T `await` inside a `for` loop when calls are independent — batch with `Promise.all`.
DON'T forget to `return`/`await` a promise inside a function, or errors go unhandled.

### Sources

- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Optional_chaining
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Nullish_coalescing_assignment
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/hasOwn
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/toSorted
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/groupBy
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Classes/Public_class_fields
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/structuredClone
- https://tc39.es/ecma262/

## Async & the event loop <a id="async"></a>

Language-layer mechanics only. TS-specific typing and Node runtime APIs (timers, streams, `worker_threads`) live in the typescript / node lore. Version facts below verified against MDN + TC39 (2026-07).

### The event loop (know this cold)

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

#### DO / DON'T
- **DON'T block the loop.** No long sync loops, huge JSON parse, or sync crypto on the main thread — everything else starves. Chunk work, offload to a Worker, or yield.
- **DON'T starve macrotasks** by recursively queuing microtasks — a microtask that always queues another microtask never lets timers/rendering run.
- **DO** rely on run-to-completion for deterministic ordering; **DON'T** rely on `setTimeout(…, 0)` for ordering vs promises — promises (microtasks) always win.

### Callbacks → Promises → async/await

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

### Sequential vs parallel await

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

### Promise combinators (pick the right one)

| Method | Fulfills | Rejects | ES |
|---|---|---|---|
| `Promise.all(it)` | all fulfill → values[] | **first** rejection (fail-fast) | ES2015 |
| `Promise.allSettled(it)` | all settle → `{status,value|reason}[]` | never | ES2020 |
| `Promise.any(it)` | first fulfillment | all reject → `AggregateError` | ES2021 |
| `Promise.race(it)` | first to **settle** (fulfill *or* reject) | first settle is a rejection | ES2015 |

- **DO** use `allSettled` when you want every outcome (don't let one failure discard successful results).
- **DO** use `any` for "first success wins"; `race` for timeouts/first-settled.
- `Promise.withResolvers()` (ES2024) returns `{promise, resolve, reject}` — cleaner than the deferred-in-executor pattern.

### Error handling

- **DO** wrap `await` in `try/catch`; on `.then` chains use `.catch`. `.finally(fn)` runs on both paths (no arg, passes value through).
- **DON'T** build result arrays with separate awaits that can reject out of order — a rejection not yet chained becomes **unhandled**:
```js
// DON'T — if p2 rejects before p1 resolves, .catch won't catch it
const out = [await p1, await p2];
// DO
const out = await Promise.all([p1, p2]);
```
- **DON'T swallow** errors with empty `.catch(() => {})` unless intentional.

### Floating / unhandled promises

- **DON'T** call an async fn and ignore the promise ("floating"). Either `await` it, chain `.catch`, or explicitly `void`+handle.
- A rejected promise with no handler → `unhandledrejection` (browser) / `'unhandledRejection'` (Node, may crash the process). Attach handlers; in Node prefer failing fast over silencing.

### Cancellation — AbortController / AbortSignal

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

### structuredClone

Global (browsers Baseline 2022; Node 17+). Deep clone via structured-clone algorithm; **handles circular refs**, Maps, Sets, typed arrays, `ArrayBuffer`.

```js
const copy = structuredClone(obj);
structuredClone(buf, { transfer: [buf] }); // move, don't copy (detaches original)
```
- **DON'T** clone functions, DOM nodes, or class instances expecting the prototype — throws `DataCloneError` or drops metadata. **DON'T** use `JSON.parse(JSON.stringify(x))` when the data has Dates/Maps/undefined/cycles.

### Version cues (verify against target baseline)

- **Top-level `await`** — ES2022; only in **modules** (`"type":"module"` / `.mjs` / ESM bundles). Sibling modules that import it wait on it.
- **`Array.fromAsync(asyncIterable, mapFn?)`** — ES2024 / Baseline 2024; returns `Promise<Array>`. Iterates **sequentially & lazily** (like `for await…of`) — *not* concurrent. Use `Promise.all` when you want concurrency.
- **`queueMicrotask(cb)`** — schedule a microtask directly; prefer over `Promise.resolve().then` for clarity.
- Older baselines (pre-ES2020 targets, e.g. transpiling to ES2017): `allSettled/any/withResolvers` need polyfills; `structuredClone`/`AbortSignal.timeout` absent on old Node (<17) — feature-detect or polyfill.

### Sources
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

## Types, coercion & pitfalls <a id="types-and-coercion"></a>

JS LANGUAGE layer. Dynamic typing: values have types, bindings don't. 7 primitives (`undefined`, `null`, `boolean`, `number`, `string`, `bigint`, `symbol`) + `object`. Coercion is the #1 source of silent bugs. TS types and Node APIs live in their own lore — this is runtime language mechanics. Mostly version-stable.

### DO — equality & identity

- DO use `===` / `!==` everywhere. It never coerces; compares type then value.
- DO know the ONLY safe `==` idiom: `x == null` matches both `null` and `undefined` (nothing else). Use it as a nullish guard if you like it — otherwise `x === null || x === undefined` or `x ?? …`.
- DO use `Object.is(a, b)` (ES2015) when `NaN` must equal `NaN` and `+0`/`-0` must differ. `===` says `NaN !== NaN` (true) and `+0 === -0` (true).
- DO recall SameValueZero (used by `Array.prototype.includes`, `Map`/`Set` keys): like `===` but `NaN` equals `NaN`, and `+0`/`-0` are equal. That's why `[NaN].includes(NaN)` is `true` but `[NaN].indexOf(NaN)` is `-1` (`indexOf` uses `===`).

### DON'T — `==` coercion

- DON'T use `==` for general comparison. Its coercion table is a minefield:

```js
0 == ""          // true
0 == "0"         // true
"" == "0"        // false   ← not transitive
0 == false       // true
null == undefined// true
null == 0        // false   ← null only loose-equals undefined
NaN == NaN       // false
[] == ![]        // true    (![] → false → 0; [] → "" → 0)
[] == 0          // true    ([] → "" → 0)
"\t\n" == 0      // true    (whitespace string → 0)
0n == 0          // true    (bigint↔number)
```

- DON'T compare objects with `==`/`===` for structure — both check reference identity. `{a:1} === {a:1}` is `false`. Use a deep-equal util or compare serialized/known fields.

### DO — truthy / falsy

- DO memorize the 8 falsy values: `false`, `0`, `-0`, `0n`, `""`, `null`, `undefined`, `NaN`. Everything else is truthy — including `"0"`, `"false"`, `[]`, `{}`, and any function.
- DO guard explicitly when `0` / `""` are valid inputs. `if (count)` skips `0`; `if (name)` skips `""`. Use `if (x != null)` or `x === undefined` checks instead.
- DON'T use `||` for defaults when `0`/`""`/`false` are legal — it eats them. Use `??` (nullish coalescing, ES2020): falls back only on `null`/`undefined`.

```js
const port = cfg.port ?? 8080;   // 0 would be kept by ??, dropped by ||
const label = input || "N/A";    // "" becomes "N/A" — usually a bug
```

### DO — NaN & number checks

- DO use `Number.isNaN(x)` (ES2015), never the global `isNaN(x)`. Global `isNaN` coerces first: `isNaN("foo") === true`, `isNaN(undefined) === true`. `Number.isNaN` returns `true` only for actual `NaN`.
- DO use `Number.isFinite(x)` / `Number.isInteger(x)` (ES2015, no coercion) over the coercing globals.
- DO detect parse failure via `Number.isNaN(Number(s))`; `Number("")` is `0`, `Number(" ")` is `0`, `Number("12px")` is `NaN`. `parseInt("12px")` is `12` (stops at non-digit) — different tool, different behavior. Always pass a radix: `parseInt(s, 10)`.

### DON'T — floating point

- DON'T assume decimal exactness. IEEE-754 doubles: `0.1 + 0.2 === 0.3` is `false` (`0.30000000000000004`).
- DO compare floats with an epsilon, or work in integers (cents, not dollars):

```js
Math.abs(a - b) < Number.EPSILON        // ok for values near 1
Math.abs(a - b) < 1e-9                   // pick tolerance for your scale
```

- DO round for display with `toFixed`/`Intl.NumberFormat`; never for money math.

### DO — type checks

- DO use `typeof` for primitives. Returns: `"undefined"`, `"boolean"`, `"number"`, `"string"`, `"bigint"` (ES2020), `"symbol"` (ES2015), `"function"`, `"object"`.
- DON'T trust `typeof x === "object"` to mean "object": `typeof null === "object"` (historical bug, permanent). Test `x !== null && typeof x === "object"`.
- DO use `Array.isArray(x)` (ES5) for arrays — `typeof [] === "object"`, and it works across realms/iframes where `instanceof Array` fails.
- DON'T rely on `instanceof` across realms (iframe/worker/vm) — each has its own constructors. Prefer `Array.isArray`, or `Object.prototype.toString.call(x)` (`"[object Date]"` etc.) for built-in tags.
- DO note `typeof (()=>{}) === "function"` and `typeof class C{} === "function"`; `NaN` is `"number"`.

### DO — null vs undefined

- DO treat `undefined` = "never assigned / absent" (missing params, missing props, array holes) and `null` = "intentionally empty". Pick one for your own absent-value sentinel; don't mix.
- DO use optional chaining `?.` (ES2020) to short-circuit on `null`/`undefined`: `obj?.a?.b`, `fn?.()`, `arr?.[i]`. Returns `undefined` instead of throwing.
- DON'T `JSON.stringify` and expect `undefined` to survive — object props with `undefined` are dropped; in arrays `undefined` becomes `null`. `null` is preserved.

### DO — BigInt (ES2020)

- DO use `BigInt` for exact integers beyond `Number.MAX_SAFE_INTEGER` (`2**53 - 1` = `9007199254740991`). Past that, `Number` silently collides: `9007199254740992 + 1 === 9007199254740992`. Validate with `Number.isSafeInteger(x)`.
- DON'T mix `BigInt` and `Number` in arithmetic — `1n + 1` throws `TypeError`. Convert explicitly: `Number(1n)` or `BigInt(1)`.
- DO know `==` bridges them (`0n == 0` true) but `===` does not (`0n === 0` false; different types). `typeof 1n === "bigint"`.
- DON'T `JSON.stringify` a BigInt — it throws. Serialize as string manually.
- DON'T use `Math.*` on BigInt; BigInt division truncates toward zero (`7n / 2n === 3n`).

### DO — Symbol (ES2015)

- DO use `Symbol()` for unique, non-colliding property keys and well-known protocol hooks (`Symbol.iterator`, `Symbol.asyncIterator`). Every `Symbol()` is unique: `Symbol("x") !== Symbol("x")`.
- DO use `Symbol.for(key)` for a cross-realm global registry (interned); `Symbol.for("x") === Symbol.for("x")`.
- DON'T expect symbol keys in `for...in`, `Object.keys`, or `JSON.stringify` — they're skipped. Use `Object.getOwnPropertySymbols`.
- DON'T coerce a symbol to string implicitly (`` `${sym}` `` throws `TypeError`); call `String(sym)` or `sym.description`.

### Checklist before shipping

- Grep for `==` / `!=` — replace with `===` / `!==` unless it's the deliberate `== null` idiom.
- Any `||` default over a value that could be `0`/`""`/`false` → switch to `??`.
- Any `isNaN(` / bare `parseInt(` → `Number.isNaN(` / add radix.
- Money or large-int math → integers or `BigInt`, never raw float `===`.
- `typeof x === "object"` → add the `x !== null` guard; arrays → `Array.isArray`.
- Guard external inputs (`JSON.parse`, query params, form data) before trusting their type.

### Sources

- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Equality_comparisons_and_sameness
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/typeof
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/isNaN
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/BigInt
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Symbol
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Nullish_coalescing
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/isArray
- https://tc39.es/ecma262/

## Errors & resource handling <a id="errors-and-resources"></a>

Language-layer mechanics only. TypeScript config (`lib`, `target`) lives in typescript lore; Node process tuning lives in node lore.

### Throwing

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

### Custom errors + cause (ES2022)

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

### try / catch / finally

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

### Async propagation

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

### Process/global last-resort handlers

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

### Cleanup patterns

DO release resources in `finally` so they run on both success and throw.

```js
const conn = await pool.acquire();
try { return await conn.run(q); }
finally { await conn.release(); }
```

DO pass an `AbortSignal` to cancel async work; listen and clean up on `abort`.
DON'T rely on GC/`finalizers` for deterministic cleanup — `FinalizationRegistry` timing is unspecified.

### Explicit resource management: `using` / `await using`

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

### Sources

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
