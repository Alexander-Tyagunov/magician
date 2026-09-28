# typescript — deep dive

> On-demand companion to `lore/typescript.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Type system essentials](#type-system) · [tsconfig & strictness](#tsconfig-and-strictness) · [Advanced types & inference](#advanced-types) · [Patterns & pitfalls](#patterns-and-pitfalls)

## Type system essentials <a id="type-system"></a>

Layers on the JavaScript lore (do not re-teach JS). Covers the type system + tsconfig only. Verified against the TS Handbook, release notes, and tsconfig reference (see Sources).

Version baseline: current stable is **TypeScript 7.0** (native Go port, codename Corsa); the JS-based line continues as **6.x**. TS 6 (JS) and TS 7 (native) are kept language-aligned — same type system, semantics, and syntax; only the compiler binary differs. All feature/version claims below refer to when a feature stabilized in the 4.x/5.x language line and carry forward unchanged.

### `type` vs `interface`
- DO use `interface` for object/class shapes by default. Handbook heuristic: "use `interface` until you need features from `type`." `extends` is often more compiler-performant than `&` intersections.
- DO use `type` for unions, tuples, mapped/conditional/template-literal types, primitives, and function-type aliases — things `interface` can't express.
- DON'T rely on `interface` **declaration merging** unless you mean it (augmenting library globals). Two `interface X` in scope silently merge; two `type X` error. That silent merge is a footgun, not a feature, for app code.
- DON'T reach for one over the other on style grounds mid-file — pick per shape, stay consistent.

### Unions & intersections
- DO model "one of" with unions (`A | B`). An operation is allowed only if valid for **every** member — narrow first.
- DO model "all of" with intersections (`A & B`). Conflicting primitive props in an intersection collapse to `never`.
- DO make unions **discriminated**: a shared literal field (`kind: "a" | "b"`) unlocks exhaustive `switch` narrowing.
- DON'T build unions of structurally-identical objects without a discriminant — narrowing degrades to `in`/property probing.

### Literal & template-literal types
- DO prefer literal unions over loose primitives: `type Align = "left" | "right" | "center"`.
- DO use template-literal types for string patterns: `type Ev = `on${Capitalize<string>}``, `type Route = `/api/${string}``.
- DON'T forget widening: `let x = "GET"` infers `string`. Use `const`, an explicit literal type, or `as const` to keep the literal.

### `as const`
- DO append `as const` to freeze literals and make arrays `readonly` tuples: `const M = ["GET","POST"] as const` → `readonly ["GET","POST"]`.
- DO derive union types from const objects: `type Dir = typeof ODir[keyof typeof ODir]`.
- DON'T mutate an `as const` value — it's deeply `readonly`.

### `satisfies` (TS 4.9)
- DO use `satisfies` to check a value against a type **without widening** its inferred type. You get both the shape check and the narrow inferred type.
```ts
const palette = {
  red: [255, 0, 0],
  green: "#00ff00",
} satisfies Record<string, string | number[]>;
palette.green.toUpperCase(); // OK: still known to be string
palette.red.at(0);           // OK: still known to be number[]
```
- DON'T use a plain annotation (`const p: Record<…> = …`) when you still need the specific literal/member types — that widens and loses them.
- DON'T use `as` (assertion) where `satisfies` fits: `as` can lie and silences errors; `satisfies` verifies.

### Generics + constraints
- DO constrain type params: `function first<T extends readonly unknown[]>(a: T)`. Unconstrained `<T>` where you index/call is a smell.
- DO use `const` type parameters (TS 5.0) to infer literals without caller-side `as const`: `function f<const T>(x: T): T`.
- DO use `NoInfer<T>` (TS 5.4) to stop a param from polluting inference: `f<C extends string>(colors: C[], dflt?: NoInfer<C>)`.
- DON'T add a type param that appears only once — if it's not relating two positions, it's just `any` in disguise; use `unknown`.

### Narrowing / control-flow analysis
- DO narrow with `typeof`, truthiness, `===`/`!==`, `in`, `instanceof`, and discriminant `switch`. CFA tracks reachability across branches.
- DO write user-defined guards as type predicates: `function isFish(x: Pet): x is Fish`. Assertion functions (`asserts x is T`) exist since TS 3.7.
- DO note inferred type predicates (TS 5.5): `arr.filter(x => x !== undefined)` now yields `T[]`, not `(T|undefined)[]`.
- DON'T write a guard body that doesn't actually prove the predicate — the compiler trusts the signature; a wrong guard is a silent hole.

### `unknown` over `any`
- DO type unvalidated/external input as `unknown` and narrow before use. `unknown` is the safe top type.
- DO leave catch vars as `unknown` (default under `strict` via `useUnknownInCatchVariables`) and check `err instanceof Error`.
- DON'T use `any` — it disables all checking and infects everything it touches. If forced, isolate it and re-narrow immediately.
- DON'T mask `any` with implicit inference — keep `noImplicitAny` on.

### `never`
- DO use `never` for impossible states and **exhaustiveness**: assign the discriminant to `never` in `default`; adding an unhandled union member becomes a compile error.
```ts
default: { const _c: never = shape; return _c; }
```
- DON'T use `never` as a return type unless the function truly never returns (throws/infinite loop).

### `readonly`
- DO mark props/params `readonly` and use `readonly T[]` / `ReadonlyArray<T>` / `ReadonlyMap` for inputs you won't mutate.
- DON'T assume `readonly` is runtime protection — it's compile-time only; use `Object.freeze`/`as const` for real immutability.

### enums vs union-of-literals
- DO prefer **union-of-literals** or a `const` object + derived type over `enum`. It stays aligned with plain JS and erases cleanly.
```ts
const Dir = { Up: 0, Down: 1 } as const;
type Dir = typeof Dir[keyof typeof Dir];
```
- DON'T use `const enum` in libraries — incompatible with `isolatedModules`; inlined values can desync across dependency versions ("wrong branch" bugs). Prefer string enums over numeric if you must use `enum` (readable, serialize well; no reverse map).
- DON'T use numeric enums for wire/serialized values — opaque and fragile.

### Non-null `!`
- DON'T use `!` to silence "possibly undefined." It removes `null`/`undefined` at compile time with **no runtime check** — it hides the bug, doesn't fix it.
- DO narrow (guard, early return, `??`, optional chaining) or fix the type. Reserve `!` for cases the compiler can't see but you've genuinely proven.

### tsconfig (verified defaults)
- DO set `"strict": true`. It enables: `alwaysStrict`, `strictNullChecks`, `strictBindCallApply`, `strictFunctionTypes`, `strictPropertyInitialization`, `strictBuiltinIteratorReturn` (TS 5.6), `noImplicitAny`, `noImplicitThis`, `useUnknownInCatchVariables`. Each defaults `true` under strict, else `false`.
- DO add non-strict-family safety flags explicitly: `noUncheckedIndexedAccess` (adds `undefined` to index reads), `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`.
- DO for modern Node: `"module": "nodenext"` (implies `target: esnext`) with `"moduleResolution": "nodenext"`; for bundlers use `"module": "preserve"`/`"esnext"` + `"moduleResolution": "bundler"` (no extension required on relative imports).
- DO enable `verbatimModuleSyntax` + `isolatedModules` for predictable ESM/CJS emit; use `import type`/`export type` for type-only imports.
- DON'T ship without `strict`; DON'T pin an ancient `target` if the runtime supports newer — it forces heavier downleveling.

### Type-checking commands
- Type-check only: `npx tsc --noEmit`. Watch: `npx tsc --noEmit --watch`.
- TS 7 native compiler ships as `tsgo` (drop-in, much faster); `tsc` remains the 6.x JS compiler during the overlap.

### Sources
- https://www.typescriptlang.org/docs/handbook/2/everyday-types.html
- https://www.typescriptlang.org/docs/handbook/2/narrowing.html
- https://www.typescriptlang.org/docs/handbook/enums.html
- https://www.typescriptlang.org/tsconfig/
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-0.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-4.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-5.html
- https://devblogs.microsoft.com/typescript/typescript-native-port/
- https://www.npmjs.com/package/typescript (latest: 7.0.2)

## tsconfig & strictness <a id="tsconfig-and-strictness"></a>

Layers on top of the JavaScript lore. This is the type system + `tsconfig.json`. Facts verified against the TS handbook/tsconfig reference (TS 5.8 era, current cutoff). Don't re-teach JS here.

### DO — strict family
- DO set `"strict": true`. It's the master switch and future TS majors add new checks under it. Turning it on enables the whole family; disable individual flags only with a comment justifying why.
- DO know what `strict` turns on: `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitThis`, `alwaysStrict`, `useUnknownInCatchVariables` (TS 4.4), `strictBuiltinIteratorReturn` (TS 5.6). All default to the value of `strict`.
- DO treat `strictNullChecks` as the load-bearing one: `null`/`undefined` become distinct types, so narrow before use.
- DO catch as `unknown` (from `useUnknownInCatchVariables`); narrow with `err instanceof Error` before touching `.message`.

```ts
try { risky(); }
catch (err) {                        // err: unknown
  if (err instanceof Error) log(err.message);
}
```

- DO use `!` (definite-assignment) or an initializer to satisfy `strictPropertyInitialization` — but prefer a real initializer.

### DON'T — strict family
- DON'T assume `strict` covers everything. Two high-value flags are NOT enabled by it: `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`. Add them explicitly.
- DON'T disable `noImplicitAny` to "move fast" — an implicit `any` silently disables checking for that whole value.

### DO — beyond strict (opt in explicitly)
- DO enable `noUncheckedIndexedAccess` (TS 4.1) for real correctness on arrays/records: index access adds `| undefined`.

```ts
// noUncheckedIndexedAccess
const xs: number[] = [1];
const first = xs[0];   // number | undefined — must check
const rec: Record<string, User> = {};
rec["nope"].name;      // Error: possibly undefined
```

- DO enable `exactOptionalPropertyTypes` (TS 4.4) so `foo?: string` means "absent or string" — NOT "settable to `undefined`". Write `foo?: string | undefined` if you truly allow explicit `undefined`.

```ts
interface Opts { debug?: boolean }
const o: Opts = { debug: undefined }; // Error under exactOptionalPropertyTypes
```

- DO consider `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noImplicitReturns`, `noUnusedLocals`/`noUnusedParameters` for app code.

### DO — module / moduleResolution
- DO pick the pair that matches how the code is CONSUMED, not habit. `module` controls emit; `moduleResolution` controls how imports resolve.
- DO use `"module": "nodenext"` (TS 4.7) for code run directly by modern Node (22+); it tracks latest Node semantics, implies floating `--target esnext`, and picks ESM vs CJS per file from `package.json` `"type"` + extension (`.mts`/`.cts`). `nodenext` allows `require()` of ESM (Node 22+) and requires import attributes (`with`), not the deprecated `assert`.
- DO use `"module": "node18"` (TS 5.8) as a STABLE pin for Node 18 libraries — locks behavior: disallows `require(ESM)`, still allows import assertions. `node16` (TS 4.7) is the older pin. `node20` adds `require(ESM)`.
- DO use `"moduleResolution": "bundler"` (TS 5.0) when a bundler/transpiler (Vite, esbuild, webpack, swc) owns resolution: honors `package.json` `exports`/`imports`, allows extensionless relative paths. Must pair with `"module": "esnext"` or `"preserve"`; implies `allowSyntheticDefaultImports`.
- DO use `"module": "preserve"` (TS 5.4) when a runtime/bundler operates on raw `.ts` (Bun, ts loaders): each import/export keeps its written form; implies `moduleResolution: bundler` + `esModuleInterop`.
- DO set `moduleResolution` `node16`/`nodenext` ONLY with `module` `node16`/`node18`/`node20`/`nodenext` — they must agree.

### DON'T — modules
- DON'T use `moduleResolution: "node"`/`node10` for new code — it predates `exports`/`imports` and CJS-only.
- DON'T use `"classic"` ever.
- DON'T omit `.js` extensions in relative imports under `node16`/`nodenext` ESM emit — extensions are required (you write `.js` even for a `.ts` source). `bundler` does not require them.
- DON'T ship `assert { type: "json" }` — use `with { type: "json" }` (import attributes).

### DO — target, syntax fidelity
- DO set `target` to the lowest ES edition you must support; it decides downleveling and the default `lib`. For modern Node LTS (20/22/24), `ES2022`+ is safe. `nodenext` floats `target` to `esnext`.
- DO enable `verbatimModuleSyntax` (TS 5.0): forbids imports that would be silently emitted as `require`, forcing written syntax to match emit. Use `import type` / `export type` for type-only. Replaces the older `importsNotUsedAsValues` + `isolatedModules` type-elision guessing.

```ts
import { type User, createUser } from "./user"; // type-only elided, value kept
```

- DO enable `isolatedModules` when a single-file transpiler (babel/esbuild/swc) compiles each file alone — it bans constructs needing cross-file type info (re-exporting a type without `export type`, `const enum`, non-erasable namespaces).

### DON'T — target/syntax
- DON'T set `target` higher than your runtime supports to "avoid transpiling" — you'll ship syntax that throws.
- DON'T rely on `const enum` under `isolatedModules`/`verbatimModuleSyntax`; prefer plain `enum` or a `const` object + union.

### DO — libraries: declaration / composite
- DO set `"declaration": true` to emit `.d.ts` for a published package. Add `"declarationMap": true` (TS 2.9) so consumers "Go to Definition" jumps to your `.ts` source.
- DO use `"composite": true` for project references / monorepos; it implies `declaration: true` and requires `rootDir`. Pair with `tsc --build`.
- DO consider `isolatedDeclarations` (TS 5.5) for large libs: forces explicit return/export types so `.d.ts` can be emitted without full type-checking (faster parallel builds).

### skipLibCheck — tradeoff
- DO turn `skipLibCheck: true` ON for app code / CI speed: skips type-checking all `.d.ts` (yours + `node_modules`). Standard in most setups; avoids errors from conflicting third-party types you can't fix.
- DON'T leave it on blind for a PUBLISHED library — it can hide genuine errors in YOUR emitted `.d.ts`. Run a periodic build with `skipLibCheck: false`, or use `isolatedDeclarations` to keep declarations honest.

### Quick baselines
- Modern Node app (Node 22+): `strict`, `noUncheckedIndexedAccess`, `module: nodenext`, `moduleResolution: nodenext`, `target: es2022`, `verbatimModuleSyntax`, `skipLibCheck`.
- Bundled web app: `strict`, `noUncheckedIndexedAccess`, `module: esnext`, `moduleResolution: bundler`, `target: es2022`, `verbatimModuleSyntax`, `noEmit` (bundler emits).
- Published library: add `declaration`, `declarationMap`, `composite` (if referenced), `isolatedDeclarations`; audit with `skipLibCheck: false`.

### Sources
- https://www.typescriptlang.org/tsconfig/
- https://www.typescriptlang.org/docs/handbook/modules/reference.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-8.html
- https://www.typescriptlang.org/docs/handbook/intro.html

## Advanced types & inference <a id="advanced-types"></a>

TYPE-SYSTEM layer. Sits on top of the JavaScript lore (runtime mechanics live there — don't re-teach). This is the compile-time type system: mapped/conditional/template-literal types, `infer`, utility types, discriminated unions, guards, and the strictness knobs. Latest stable: **TS 6.0** (shipped Mar 2026; 6.x is transitional with deprecations, and TS 7.x is the native Go `tsc` rewrite). Version tags below say when a feature *stabilized* — never claim earlier.

### DO — turn on strictness first

- DO set `"strict": true`. It enables the whole family: `noImplicitAny`, `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitThis`, `useUnknownInCatchVariables` (4.4), `alwaysStrict`, and `strictBuiltinIteratorReturn` (5.6). Each defaults `true` under `strict`.
- DO separately opt into `noUncheckedIndexedAccess` (index/record access → `T | undefined`) and `exactOptionalPropertyTypes` (4.4; `x?: T` stops silently accepting `undefined`). Neither is in `strict`.

### DO — mapped types (2.1)

- DO iterate keys with `[K in keyof T]`. Adjust modifiers with `+`/`-` (`+` is the default, so write only `-`):

```ts
type Mutable<T>  = { -readonly [K in keyof T]: T[K] };   // strip readonly
type Concrete<T> = { [K in keyof T]-?: T[K] };            // strip optional (?)
```

- DO remap/rename keys with `as` (4.1); emit `never` to DROP a key:

```ts
type Getters<T> = { [K in keyof T as `get${Capitalize<string & K>}`]: () => T[K] };
type NoKind<T>  = { [K in keyof T as Exclude<K, "kind">]: T[K] };   // filter out "kind"
```

- DON'T hand-roll what the built-ins already do (below). Reach for a custom mapped type only when no utility fits.

### DO — conditional types + `infer` (2.8)

- DO read `A extends B ? X : Y` as "if A is assignable to B". Use `infer` to capture a type in the true branch:

```ts
type ElementOf<T>  = T extends readonly (infer U)[] ? U : never;
type Return<T>     = T extends (...a: never[]) => infer R ? R : never;
```

- DO know conditionals are **distributive** over a *naked* type parameter — they apply per union member:

```ts
type Box<T> = T extends any ? T[] : never;
type R = Box<string | number>;   // string[] | number[]  (distributed)
```

- DO disable distribution by wrapping BOTH sides in a 1-tuple when you want the union treated whole:

```ts
type Box<T> = [T] extends [any] ? T[] : never;
type R = Box<string | number>;   // (string | number)[]
```

- DON'T forget: `infer` from an overloaded/multi-signature function resolves the LAST signature only.

### DO — use built-in utility types (don't reinvent)

| Utility | Since | Shape |
|---|---|---|
| `Partial<T>` / `Required<T>` | 2.1 / 2.8 | all props `?` / all props required |
| `Readonly<T>` | 2.1 | all props `readonly` |
| `Pick<T,K>` / `Omit<T,K>` | 2.1 / 3.5 | keep / drop keys `K` |
| `Record<K,T>` | 2.1 | `{ [P in K]: T }` |
| `Exclude<U,E>` / `Extract<U,E>` | 2.8 | union minus / intersect `E` |
| `NonNullable<T>` | 2.8 | strip `null`/`undefined` |
| `ReturnType<F>` / `Parameters<F>` | 2.8 / 3.1 | fn return / param tuple |
| `Awaited<T>` | **4.5** | recursively unwrap `Promise` (use this, not manual `infer`) |

- DO derive from the source of truth (`type User = typeof userSchema` → `Partial<User>`, `Pick<User,"id">`) so one change propagates. DON'T write `Pick<T, Exclude<keyof T, K>>` — that's `Omit<T,K>`.

### DO — template-literal types (4.1)

- DO build string-literal unions and use the intrinsic case types `Uppercase` / `Lowercase` / `Capitalize` / `Uncapitalize`:

```ts
type EventName<T extends string> = `on${Capitalize<T>}`;
type Clicks = EventName<"click" | "hover">;   // "onClick" | "onHover"
```

- DON'T explode combinatorial unions (`` `${A}-${B}-${C}` `` across large unions) — it blows up instantiation count and tanks compile time. Keep it bounded.

### DO — discriminated unions + exhaustiveness

- DO give each variant a shared literal discriminant with REQUIRED fields (not optional grab-bag props):

```ts
type Shape =
  | { kind: "circle"; r: number }
  | { kind: "square"; side: number };
```

- DO force exhaustiveness with a `never` sink — adding a variant becomes a compile error:

```ts
function area(s: Shape): number {
  switch (s.kind) {
    case "circle": return Math.PI * s.r ** 2;
    case "square": return s.side ** 2;
    default: { const _x: never = s; return _x; }   // errors if a case is missing
  }
}
```

- DON'T model variants as one type with optional fields (`radius?`, `side?`) — TS can't correlate them and narrowing fails.

### DO — narrowing: guards & assertions

- DO write user-defined type guards returning `x is T`; they narrow in BOTH branches and compose with `.filter`:

```ts
const isStr = (x: unknown): x is string => typeof x === "string";
const strs = mixed.filter(isStr);   // string[]
```

- DO use assertion functions (3.7) when you narrow-and-continue rather than branch. `asserts x is T` narrows a value; `asserts x` narrows on truthiness. Must return `void`:

```ts
function assert(c: unknown, m?: string): asserts c { if (!c) throw new Error(m); }
assert(typeof v === "string"); v.toUpperCase();   // v: string after the call
```

- DON'T lie inside a guard/assertion — the compiler trusts the signature; a wrong `x is T` is an unsound hole worse than `any`. Prefer a real guard over an `as` cast (a cast asserts without proof).

### DO — inference control (5.x)

- DO use `satisfies` (4.9) to validate a value against a type WITHOUT widening it — you keep the specific inferred type and still catch typos/missing keys:

```ts
const routes = { home: "/", user: "/u/:id" } satisfies Record<string, string>;
routes.home.startsWith("/");   // home is string, not string|... — still narrow
```

- DO add `const` type parameters (5.0) when a generic should infer literals/tuples without callers writing `as const`. Pair with a `readonly` constraint:

```ts
function tuple<const T extends readonly unknown[]>(t: T): T { return t; }
const t = tuple(["a", "b"]);   // readonly ["a", "b"]
```

- DO wrap a param in `NoInfer<T>` (5.4) to exclude it as an inference source, so `T` is fixed by the other args:

```ts
function pick<C extends string>(all: C[], def?: NoInfer<C>): void {}
pick(["red", "green"], "blue");   // error: "blue" not in inferred C
```

### DON'T — over-engineer the types

- DON'T build deep recursive conditional/template gymnastics for a shape a plain `interface` + a utility type expresses. Type cleverness has a real compile-time and readability cost.
- DON'T use `any` — it disables checking and spreads. Use `unknown` for untrusted input and narrow before use.
- DON'T annotate what TS already infers correctly (locals, return types of obvious functions). Annotate exported/public API boundaries; let inference handle the interior.
- DON'T model with `enum` when a string-literal union suffices — unions are erasable, tree-shakeable, and narrow cleanly.

### Checklist before shipping

- `strict` on; consider `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`.
- Every `switch` over a discriminated union has a `never` exhaustiveness default.
- No `as`/`any` used to silence an error — replaced by a guard, `satisfies`, or a correct type.
- Every `x is T` guard body actually proves `T` (no lying signatures).
- Derived types (`Pick`/`Omit`/`ReturnType`/`Awaited`) instead of re-declared parallel shapes.
- No unbounded template-literal cross-products or gratuitous recursive types.

### Sources

- https://www.typescriptlang.org/docs/handbook/2/mapped-types.html
- https://www.typescriptlang.org/docs/handbook/2/conditional-types.html
- https://www.typescriptlang.org/docs/handbook/2/narrowing.html
- https://www.typescriptlang.org/docs/handbook/utility-types.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-0.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-4.html
- https://www.typescriptlang.org/tsconfig/

## Patterns & pitfalls <a id="patterns-and-pitfalls"></a>

Type-system layer, on top of the JavaScript lore (JS runtime mechanics — coercion, `??`, `===`,
closures — live there). Baseline **TS 5.x** (5.9 current line; native Go port ships as TS 7.0).
Types are **erased** at runtime: they guide the compiler, they do not validate data. Trust the
compiler for internal shapes; validate at every boundary. Enable `strict` — everything assumes it.

### DO — tsconfig baseline

- DO set `"strict": true`. Turns on `noImplicitAny`, `strictNullChecks`, `strictFunctionTypes`,
  `strictPropertyInitialization`, `useUnknownInCatchVariables`, `strictBindCallApply`, etc.
- DO add the two `strict` does **not** include:
  - `noUncheckedIndexedAccess` (TS 4.1): `arr[i]` / `rec[k]` become `T | undefined`. Catches the
    #1 off-by-one/absent-key bug.
  - `exactOptionalPropertyTypes` (TS 4.4): `{ x?: number }` no longer silently accepts `x: undefined`.
- DO set `"verbatimModuleSyntax": true` (TS 5.0) — forces `import type` for type-only imports,
  no import elision surprises, correct ESM/CJS emit.
- DO pick module settings by target: **Node** → `"module": "nodenext"` (resolution follows);
  **bundler** → `"module": "preserve"` + `"moduleResolution": "bundler"`. DON'T use `node10`/`classic`.
- DO set `"isolatedModules": true` (and `"erasableSyntaxOnly"`, TS 5.8, if you use Node's
  `--experimental-strip-types` / any single-file transpiler) — bans `const enum`, runtime
  `namespace`, param properties, which a per-file transpiler can't erase.

### DON'T — `any` and `as`

- DON'T use `any`. It disables checking transitively and infects everything it touches.
  Use `unknown` for "I don't know the type yet", then narrow.
- DON'T cast with `as` to silence errors — a cast is a *lie to the compiler*, checked by nobody.
  `data as User` does zero runtime work. Narrow or parse instead.
- DON'T use non-null `!` to paper over `strictNullChecks`. It hides the real absent-value bug.
  Guard (`if (x == null) return`) or model the absence.
- DO allow `as` only where un-expressible: `as const`, narrowing `unknown` *after* a runtime check,
  or the double-cast escape hatch `x as unknown as T` (flag it in review).
- DO enable `@typescript-eslint` `no-explicit-any`, `no-unsafe-*`, `no-non-null-assertion`.

```ts
const raw: unknown = JSON.parse(body);
// DON'T: const user = raw as User;          // compiles, lies
const user = UserSchema.parse(raw);           // DO: validated → typed
```

### DO — discriminated unions for domain modeling

- DO model "one of N shapes" as a union with a shared literal **discriminant**. Make illegal
  states unrepresentable instead of a bag of optionals.
- DO `switch` on the tag; add a `default` with an `assertNever` to get compile-time exhaustiveness.

```ts
type Result<T> =
  | { status: "ok"; data: T }
  | { status: "error"; error: Error };

function h<T>(r: Result<T>) {
  switch (r.status) {
    case "ok": return r.data;        // narrowed, .error not accessible
    case "error": throw r.error;
    default: return assertNever(r);  // errors if a case is added later
  }
}
const assertNever = (x: never): never => { throw new Error(`unreachable: ${x}`); };
```

- DON'T use `{ ok: boolean; data?: T; error?: E }` — every consumer must null-check both fields.

### DO — branded / nominal types

TS is **structurally** typed: same shape = assignable. `UserId` and `OrderId` (both `string`)
are interchangeable — a real bug source. Add a brand to get nominal safety.

```ts
type UserId = string & { readonly __brand: "UserId" };
const asUserId = (s: string): UserId => s as UserId; // brand cast only at the validated boundary
declare function load(id: UserId): void;
load("123");            // ✗ plain string not assignable
load(asUserId("123"));  // ✓
```

- DO brand IDs, currency/units, and already-validated strings (`Email`, `SafeHtml`).
- DON'T scatter the `as` brand cast — confine it to one constructor/parser per brand.

### DO — structural typing gotchas

- DO know **excess property checks** fire only on *fresh* object literals; assign the literal to a
  variable first and extra props pass silently — a common "why didn't it catch my typo" moment.
- DO prefer `readonly` inputs — array/object types are covariant and method params bivariant
  (historical), both sources of unsound reads.
- DON'T rely on `private`/`#` for structural distinction alone; use a brand for true nominal intent.

### DO — the DTO / validation boundary (parse, don't cast)

Anything crossing the wire — `JSON.parse`, `fetch` bodies, `req.body`, env vars, query params,
`localStorage`, DB rows from untyped drivers — is `unknown`. A type annotation there is a claim,
not a check.

- DO parse with a schema validator (zod, valibot, arktype) and derive the type from the schema —
  one source of truth, runtime + compile-time agree.
- DON'T annotate `const body: CreateUser = await res.json()` — `json()` returns `any`/`unknown`;
  you've asserted a shape you never verified.

```ts
import { z } from "zod";
const CreateUser = z.object({ email: z.string().email(), age: z.number().int() });
type CreateUser = z.infer<typeof CreateUser>;   // derive type from schema

const parsed = CreateUser.safeParse(await res.json());
if (!parsed.success) return badRequest(parsed.error);
use(parsed.data);                                // typed AND validated
```

### DO — typing async

- DO type the resolved value: `async` fn returning `T` is `Promise<T>`; `await` unwraps it.
- DO type `catch` as `unknown` (default under `strict`) and narrow: `e instanceof Error`.
  Rejections can be *anything*, not just `Error`.
- DON'T mark a function `async` if it never `await`s just to "return a Promise" — wrap only what's needed.
- DON'T leave floating promises — always `await` or `void` them; enable `no-floating-promises`.
- DO note `Promise.all` infers a tuple; `allSettled` yields `PromiseSettledResult<T>[]` (narrow on `.status`).

```ts
try { await work(); }
catch (e: unknown) { if (e instanceof Error) log(e.message); else log(String(e)); }
```

### DO — generics vs overloads

- DO prefer **generics** when input and output types are *linked* (`<T>(x: T) => T[]`).
  One signature, relationship preserved, composes.
- DO use **overloads** only for genuinely different, unrelated input→output shapes that a single
  signature can't express. The implementation signature is not callable — keep overloads narrow.
- DON'T reach for overloads where a union return or a conditional/generic type would do — they don't
  narrow on the argument and multiply maintenance.
- DO use `NoInfer<T>` (TS 5.4) to stop a param from polluting inference of a type parameter.
- DO use `satisfies` (TS 4.9) to check a value against a type **without widening** — keeps the
  narrow/literal inference a `: T` annotation would discard:
  `const cfg = {port: 8080} satisfies Record<string, unknown>;` → `cfg.port` stays `number`.

### DO — declaration files & module augmentation

- DO write `.d.ts` for untyped JS deps; ship `types`/`exports` in `package.json` for libraries.
- DO augment third-party or global types with `declare module "x" { ... }` / `declare global`,
  inside a module (has an `import`/`export`) so it merges rather than shadows.
- DON'T redeclare a global as a plain script-file `var` — it replaces instead of extending.
- DO use interface **declaration merging** deliberately (e.g. Express `Request`); know that
  `interface` merges across declarations but `type` aliases do not.

```ts
// express.d.ts
import "express";
declare global {
  namespace Express { interface Request { userId?: UserId } }
}
```

### Checklist before shipping

- `strict` on; add `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`.
- Grep for `any`, ` as `, `!` — each is a checked lie unless justified (`as const`, post-guard `unknown`).
- Every external input (`res.json`, `req.body`, env, `JSON.parse`) → schema `.parse`, never annotate-and-trust.
- Union domain models have a discriminant + exhaustive `switch` with `assertNever`.
- Same-primitive IDs/units → branded types; brand cast confined to one constructor.
- `catch (e: unknown)` and narrow; no floating promises.
- Run `npx tsc --noEmit` + `eslint` in CI; treat type errors as build failures.

### Sources

- https://www.typescriptlang.org/docs/handbook/intro.html
- https://www.typescriptlang.org/tsconfig/
- https://www.typescriptlang.org/docs/handbook/release-notes/overview.html
- https://www.typescriptlang.org/docs/handbook/2/narrowing.html
- https://www.typescriptlang.org/docs/handbook/2/objects.html
- https://www.typescriptlang.org/docs/handbook/declaration-merging.html
- https://www.typescriptlang.org/docs/handbook/utility-types.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html (satisfies)
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-0.html (const params, verbatimModuleSyntax)
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-4.html (NoInfer)
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-8.html (erasableSyntaxOnly)
- https://zod.dev/
