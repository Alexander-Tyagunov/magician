# javascript — Types, coercion & pitfalls

JS LANGUAGE layer. Dynamic typing: values have types, bindings don't. 7 primitives (`undefined`, `null`, `boolean`, `number`, `string`, `bigint`, `symbol`) + `object`. Coercion is the #1 source of silent bugs. TS types and Node APIs live in their own lore — this is runtime language mechanics. Mostly version-stable.

## DO — equality & identity

- DO use `===` / `!==` everywhere. It never coerces; compares type then value.
- DO know the ONLY safe `==` idiom: `x == null` matches both `null` and `undefined` (nothing else). Use it as a nullish guard if you like it — otherwise `x === null || x === undefined` or `x ?? …`.
- DO use `Object.is(a, b)` (ES2015) when `NaN` must equal `NaN` and `+0`/`-0` must differ. `===` says `NaN !== NaN` (true) and `+0 === -0` (true).
- DO recall SameValueZero (used by `Array.prototype.includes`, `Map`/`Set` keys): like `===` but `NaN` equals `NaN`, and `+0`/`-0` are equal. That's why `[NaN].includes(NaN)` is `true` but `[NaN].indexOf(NaN)` is `-1` (`indexOf` uses `===`).

## DON'T — `==` coercion

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

## DO — truthy / falsy

- DO memorize the 8 falsy values: `false`, `0`, `-0`, `0n`, `""`, `null`, `undefined`, `NaN`. Everything else is truthy — including `"0"`, `"false"`, `[]`, `{}`, and any function.
- DO guard explicitly when `0` / `""` are valid inputs. `if (count)` skips `0`; `if (name)` skips `""`. Use `if (x != null)` or `x === undefined` checks instead.
- DON'T use `||` for defaults when `0`/`""`/`false` are legal — it eats them. Use `??` (nullish coalescing, ES2020): falls back only on `null`/`undefined`.

```js
const port = cfg.port ?? 8080;   // 0 would be kept by ??, dropped by ||
const label = input || "N/A";    // "" becomes "N/A" — usually a bug
```

## DO — NaN & number checks

- DO use `Number.isNaN(x)` (ES2015), never the global `isNaN(x)`. Global `isNaN` coerces first: `isNaN("foo") === true`, `isNaN(undefined) === true`. `Number.isNaN` returns `true` only for actual `NaN`.
- DO use `Number.isFinite(x)` / `Number.isInteger(x)` (ES2015, no coercion) over the coercing globals.
- DO detect parse failure via `Number.isNaN(Number(s))`; `Number("")` is `0`, `Number(" ")` is `0`, `Number("12px")` is `NaN`. `parseInt("12px")` is `12` (stops at non-digit) — different tool, different behavior. Always pass a radix: `parseInt(s, 10)`.

## DON'T — floating point

- DON'T assume decimal exactness. IEEE-754 doubles: `0.1 + 0.2 === 0.3` is `false` (`0.30000000000000004`).
- DO compare floats with an epsilon, or work in integers (cents, not dollars):

```js
Math.abs(a - b) < Number.EPSILON        // ok for values near 1
Math.abs(a - b) < 1e-9                   // pick tolerance for your scale
```

- DO round for display with `toFixed`/`Intl.NumberFormat`; never for money math.

## DO — type checks

- DO use `typeof` for primitives. Returns: `"undefined"`, `"boolean"`, `"number"`, `"string"`, `"bigint"` (ES2020), `"symbol"` (ES2015), `"function"`, `"object"`.
- DON'T trust `typeof x === "object"` to mean "object": `typeof null === "object"` (historical bug, permanent). Test `x !== null && typeof x === "object"`.
- DO use `Array.isArray(x)` (ES5) for arrays — `typeof [] === "object"`, and it works across realms/iframes where `instanceof Array` fails.
- DON'T rely on `instanceof` across realms (iframe/worker/vm) — each has its own constructors. Prefer `Array.isArray`, or `Object.prototype.toString.call(x)` (`"[object Date]"` etc.) for built-in tags.
- DO note `typeof (()=>{}) === "function"` and `typeof class C{} === "function"`; `NaN` is `"number"`.

## DO — null vs undefined

- DO treat `undefined` = "never assigned / absent" (missing params, missing props, array holes) and `null` = "intentionally empty". Pick one for your own absent-value sentinel; don't mix.
- DO use optional chaining `?.` (ES2020) to short-circuit on `null`/`undefined`: `obj?.a?.b`, `fn?.()`, `arr?.[i]`. Returns `undefined` instead of throwing.
- DON'T `JSON.stringify` and expect `undefined` to survive — object props with `undefined` are dropped; in arrays `undefined` becomes `null`. `null` is preserved.

## DO — BigInt (ES2020)

- DO use `BigInt` for exact integers beyond `Number.MAX_SAFE_INTEGER` (`2**53 - 1` = `9007199254740991`). Past that, `Number` silently collides: `9007199254740992 + 1 === 9007199254740992`. Validate with `Number.isSafeInteger(x)`.
- DON'T mix `BigInt` and `Number` in arithmetic — `1n + 1` throws `TypeError`. Convert explicitly: `Number(1n)` or `BigInt(1)`.
- DO know `==` bridges them (`0n == 0` true) but `===` does not (`0n === 0` false; different types). `typeof 1n === "bigint"`.
- DON'T `JSON.stringify` a BigInt — it throws. Serialize as string manually.
- DON'T use `Math.*` on BigInt; BigInt division truncates toward zero (`7n / 2n === 3n`).

## DO — Symbol (ES2015)

- DO use `Symbol()` for unique, non-colliding property keys and well-known protocol hooks (`Symbol.iterator`, `Symbol.asyncIterator`). Every `Symbol()` is unique: `Symbol("x") !== Symbol("x")`.
- DO use `Symbol.for(key)` for a cross-realm global registry (interned); `Symbol.for("x") === Symbol.for("x")`.
- DON'T expect symbol keys in `for...in`, `Object.keys`, or `JSON.stringify` — they're skipped. Use `Object.getOwnPropertySymbols`.
- DON'T coerce a symbol to string implicitly (`` `${sym}` `` throws `TypeError`); call `String(sym)` or `sym.description`.

## Checklist before shipping

- Grep for `==` / `!=` — replace with `===` / `!==` unless it's the deliberate `== null` idiom.
- Any `||` default over a value that could be `0`/`""`/`false` → switch to `??`.
- Any `isNaN(` / bare `parseInt(` → `Number.isNaN(` / add radix.
- Money or large-int math → integers or `BigInt`, never raw float `===`.
- `typeof x === "object"` → add the `x !== null` guard; arrays → `Array.isArray`.
- Guard external inputs (`JSON.parse`, query params, form data) before trusting their type.

## Sources

- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Equality_comparisons_and_sameness
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/typeof
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/isNaN
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/BigInt
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Symbol
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Nullish_coalescing
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/isArray
- https://tc39.es/ecma262/
