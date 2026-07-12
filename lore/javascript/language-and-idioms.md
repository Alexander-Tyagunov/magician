# javascript — Language & idioms

Language layer only. TypeScript typing and Node runtime APIs live in their own lore.
Baseline: **ES2015+**. Gate newer syntax by target/runtime — years below are when each
feature landed in the ECMAScript standard (MDN's spec links say "ES2027" only because
they point at the living draft; ignore that number).

## Declarations

DO use `const` by default; `let` only when reassigned.
DON'T use `var` — it is function-scoped and hoisted, causing leaks and TDZ-free bugs.
DON'T rely on `const` for deep immutability — it only fixes the binding, not the value.

```js
const list = [1];
list.push(2); // allowed — binding is const, contents are not
```

## Equality & comparison

DO use `===` / `!==` always.
DON'T use `==` — its coercions are surprising (`0 == ""`, `null == undefined`, `[] == false`).
DO use one intentional exception: `x == null` to test "null or undefined" in one check.
DO use `Object.is` for `NaN` / `±0` edge cases (`Object.is(NaN, NaN) === true`).

## Nullish handling (ES2020 / ES2021)

DO use optional chaining `?.` to short-circuit on `null`/`undefined`: `user?.profile?.name`,
`obj?.method?.()`, `arr?.[i]`.
DO use nullish coalescing `??` for defaults — unlike `||`, it keeps `0`, `''`, `false`.
DON'T mix `??` with `||`/`&&` without parens — it's a syntax error by design.
DO use logical assignment (ES2021): `opts.timeout ??= 100`, `flag ||= true`, `x &&= f(x)`.

```js
const port = cfg.port ?? 8080;   // 0 would survive; `|| 8080` would not
(a ?? b) || c;                   // parens required
```

## Destructuring, spread, rest

DO destructure with defaults + rename: `const { id, name: label = "?" } = obj;`.
DO use rest to collect: `const [first, ...tail] = arr;`, `const { a, ...others } = obj;`.
DO copy/merge shallowly with spread: `{ ...base, ...overrides }`, `[...a, ...b]`.
DON'T assume spread is deep — nested objects are shared references.
DO deep-clone with `structuredClone(value)` (global in modern browsers and Node 17+),
not `JSON.parse(JSON.stringify(...))` (drops `undefined`, `Date`, `Map`, functions).

## Template literals

DO use backticks for interpolation and multiline: `` `Hi ${name}` ``.
DON'T build HTML/SQL/shell strings by interpolation — use a proper builder/escaper.

## Functions, `this`, arrows

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

## Closures

DO use closures for private state and factories. Each call frame captures its own bindings.
DO use `let`/`const` in loops so each iteration closes over a fresh binding (a classic `var`
bug — all callbacks share one variable).

## Prototypes vs classes

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

## Modules (ESM)

DO use `import`/`export`; prefer named exports for discoverability, default sparingly.
DO note imports are hoisted, live read-only bindings — you can't reassign an import.
DO use dynamic `import()` (returns a Promise) for lazy/conditional loading.
DO use top-level `await` (**ES2022**) — only inside ES modules, not CommonJS/scripts.
DON'T mix CommonJS `require`/`module.exports` with ESM in the same file.

## Immutability habits

DO treat data as immutable: build new values with spread / `map` / `filter` / `reduce`.
DO use copy-array methods (**ES2023**) instead of mutating: `toSorted`, `toReversed`,
`toSpliced`, `with(i, v)` — the mutating `sort`/`reverse`/`splice` change in place.
DO `Object.freeze` for shallow runtime lock (dev/config); it's not deep.

```js
const sorted = nums.toSorted((a, b) => a - b); // original untouched (ES2023)
const next = arr.with(0, "x");                 // copy with index 0 replaced
```

## Map/Set vs object

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

## Array / object method idioms

DO reach for declarative iteration: `map`, `filter`, `reduce`, `find`, `some`, `every`,
`flatMap`. Use `for...of` for side effects / early `break`; `Object.entries/keys/values`
to iterate objects.
DON'T use `for...in` on arrays (walks proto chain, string keys, unordered).
DO use `arr.at(-1)` for last element (**ES2022**), `findLast`/`findLastIndex` (**ES2023**).
DO use `Object.groupBy(items, fn)` / `Map.groupBy` (**ES2024**) — gate by runtime support.
DON'T call `Array.prototype.forEach` when you need the result — it returns `undefined`.

## Async (language level)

DO use `async`/`await` with `try/catch`; run independent work concurrently with
`Promise.all` (or `allSettled` when partial failure is tolerable).
DON'T `await` inside a `for` loop when calls are independent — batch with `Promise.all`.
DON'T forget to `return`/`await` a promise inside a function, or errors go unhandled.

## Sources

- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Optional_chaining
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Nullish_coalescing_assignment
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/hasOwn
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/toSorted
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/groupBy
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Classes/Public_class_fields
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/structuredClone
- https://tc39.es/ecma262/
