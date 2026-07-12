# typescript — Type system essentials

Layers on the JavaScript lore (do not re-teach JS). Covers the type system + tsconfig only. Verified against the TS Handbook, release notes, and tsconfig reference (see Sources).

Version baseline: current stable is **TypeScript 7.0** (native Go port, codename Corsa); the JS-based line continues as **6.x**. TS 6 (JS) and TS 7 (native) are kept language-aligned — same type system, semantics, and syntax; only the compiler binary differs. All feature/version claims below refer to when a feature stabilized in the 4.x/5.x language line and carry forward unchanged.

## `type` vs `interface`
- DO use `interface` for object/class shapes by default. Handbook heuristic: "use `interface` until you need features from `type`." `extends` is often more compiler-performant than `&` intersections.
- DO use `type` for unions, tuples, mapped/conditional/template-literal types, primitives, and function-type aliases — things `interface` can't express.
- DON'T rely on `interface` **declaration merging** unless you mean it (augmenting library globals). Two `interface X` in scope silently merge; two `type X` error. That silent merge is a footgun, not a feature, for app code.
- DON'T reach for one over the other on style grounds mid-file — pick per shape, stay consistent.

## Unions & intersections
- DO model "one of" with unions (`A | B`). An operation is allowed only if valid for **every** member — narrow first.
- DO model "all of" with intersections (`A & B`). Conflicting primitive props in an intersection collapse to `never`.
- DO make unions **discriminated**: a shared literal field (`kind: "a" | "b"`) unlocks exhaustive `switch` narrowing.
- DON'T build unions of structurally-identical objects without a discriminant — narrowing degrades to `in`/property probing.

## Literal & template-literal types
- DO prefer literal unions over loose primitives: `type Align = "left" | "right" | "center"`.
- DO use template-literal types for string patterns: `type Ev = `on${Capitalize<string>}``, `type Route = `/api/${string}``.
- DON'T forget widening: `let x = "GET"` infers `string`. Use `const`, an explicit literal type, or `as const` to keep the literal.

## `as const`
- DO append `as const` to freeze literals and make arrays `readonly` tuples: `const M = ["GET","POST"] as const` → `readonly ["GET","POST"]`.
- DO derive union types from const objects: `type Dir = typeof ODir[keyof typeof ODir]`.
- DON'T mutate an `as const` value — it's deeply `readonly`.

## `satisfies` (TS 4.9)
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

## Generics + constraints
- DO constrain type params: `function first<T extends readonly unknown[]>(a: T)`. Unconstrained `<T>` where you index/call is a smell.
- DO use `const` type parameters (TS 5.0) to infer literals without caller-side `as const`: `function f<const T>(x: T): T`.
- DO use `NoInfer<T>` (TS 5.4) to stop a param from polluting inference: `f<C extends string>(colors: C[], dflt?: NoInfer<C>)`.
- DON'T add a type param that appears only once — if it's not relating two positions, it's just `any` in disguise; use `unknown`.

## Narrowing / control-flow analysis
- DO narrow with `typeof`, truthiness, `===`/`!==`, `in`, `instanceof`, and discriminant `switch`. CFA tracks reachability across branches.
- DO write user-defined guards as type predicates: `function isFish(x: Pet): x is Fish`. Assertion functions (`asserts x is T`) exist since TS 3.7.
- DO note inferred type predicates (TS 5.5): `arr.filter(x => x !== undefined)` now yields `T[]`, not `(T|undefined)[]`.
- DON'T write a guard body that doesn't actually prove the predicate — the compiler trusts the signature; a wrong guard is a silent hole.

## `unknown` over `any`
- DO type unvalidated/external input as `unknown` and narrow before use. `unknown` is the safe top type.
- DO leave catch vars as `unknown` (default under `strict` via `useUnknownInCatchVariables`) and check `err instanceof Error`.
- DON'T use `any` — it disables all checking and infects everything it touches. If forced, isolate it and re-narrow immediately.
- DON'T mask `any` with implicit inference — keep `noImplicitAny` on.

## `never`
- DO use `never` for impossible states and **exhaustiveness**: assign the discriminant to `never` in `default`; adding an unhandled union member becomes a compile error.
```ts
default: { const _c: never = shape; return _c; }
```
- DON'T use `never` as a return type unless the function truly never returns (throws/infinite loop).

## `readonly`
- DO mark props/params `readonly` and use `readonly T[]` / `ReadonlyArray<T>` / `ReadonlyMap` for inputs you won't mutate.
- DON'T assume `readonly` is runtime protection — it's compile-time only; use `Object.freeze`/`as const` for real immutability.

## enums vs union-of-literals
- DO prefer **union-of-literals** or a `const` object + derived type over `enum`. It stays aligned with plain JS and erases cleanly.
```ts
const Dir = { Up: 0, Down: 1 } as const;
type Dir = typeof Dir[keyof typeof Dir];
```
- DON'T use `const enum` in libraries — incompatible with `isolatedModules`; inlined values can desync across dependency versions ("wrong branch" bugs). Prefer string enums over numeric if you must use `enum` (readable, serialize well; no reverse map).
- DON'T use numeric enums for wire/serialized values — opaque and fragile.

## Non-null `!`
- DON'T use `!` to silence "possibly undefined." It removes `null`/`undefined` at compile time with **no runtime check** — it hides the bug, doesn't fix it.
- DO narrow (guard, early return, `??`, optional chaining) or fix the type. Reserve `!` for cases the compiler can't see but you've genuinely proven.

## tsconfig (verified defaults)
- DO set `"strict": true`. It enables: `alwaysStrict`, `strictNullChecks`, `strictBindCallApply`, `strictFunctionTypes`, `strictPropertyInitialization`, `strictBuiltinIteratorReturn` (TS 5.6), `noImplicitAny`, `noImplicitThis`, `useUnknownInCatchVariables`. Each defaults `true` under strict, else `false`.
- DO add non-strict-family safety flags explicitly: `noUncheckedIndexedAccess` (adds `undefined` to index reads), `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`.
- DO for modern Node: `"module": "nodenext"` (implies `target: esnext`) with `"moduleResolution": "nodenext"`; for bundlers use `"module": "preserve"`/`"esnext"` + `"moduleResolution": "bundler"` (no extension required on relative imports).
- DO enable `verbatimModuleSyntax` + `isolatedModules` for predictable ESM/CJS emit; use `import type`/`export type` for type-only imports.
- DON'T ship without `strict`; DON'T pin an ancient `target` if the runtime supports newer — it forces heavier downleveling.

## Type-checking commands
- Type-check only: `npx tsc --noEmit`. Watch: `npx tsc --noEmit --watch`.
- TS 7 native compiler ships as `tsgo` (drop-in, much faster); `tsc` remains the 6.x JS compiler during the overlap.

## Sources
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
