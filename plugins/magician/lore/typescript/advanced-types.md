# typescript — Advanced types & inference

TYPE-SYSTEM layer. Sits on top of the JavaScript lore (runtime mechanics live there — don't re-teach). This is the compile-time type system: mapped/conditional/template-literal types, `infer`, utility types, discriminated unions, guards, and the strictness knobs. Latest stable: **TS 6.0** (shipped Mar 2026; 6.x is transitional with deprecations, and TS 7.x is the native Go `tsc` rewrite). Version tags below say when a feature *stabilized* — never claim earlier.

## DO — turn on strictness first

- DO set `"strict": true`. It enables the whole family: `noImplicitAny`, `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitThis`, `useUnknownInCatchVariables` (4.4), `alwaysStrict`, and `strictBuiltinIteratorReturn` (5.6). Each defaults `true` under `strict`.
- DO separately opt into `noUncheckedIndexedAccess` (index/record access → `T | undefined`) and `exactOptionalPropertyTypes` (4.4; `x?: T` stops silently accepting `undefined`). Neither is in `strict`.

## DO — mapped types (2.1)

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

## DO — conditional types + `infer` (2.8)

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

## DO — use built-in utility types (don't reinvent)

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

## DO — template-literal types (4.1)

- DO build string-literal unions and use the intrinsic case types `Uppercase` / `Lowercase` / `Capitalize` / `Uncapitalize`:

```ts
type EventName<T extends string> = `on${Capitalize<T>}`;
type Clicks = EventName<"click" | "hover">;   // "onClick" | "onHover"
```

- DON'T explode combinatorial unions (`` `${A}-${B}-${C}` `` across large unions) — it blows up instantiation count and tanks compile time. Keep it bounded.

## DO — discriminated unions + exhaustiveness

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

## DO — narrowing: guards & assertions

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

## DO — inference control (5.x)

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

## DON'T — over-engineer the types

- DON'T build deep recursive conditional/template gymnastics for a shape a plain `interface` + a utility type expresses. Type cleverness has a real compile-time and readability cost.
- DON'T use `any` — it disables checking and spreads. Use `unknown` for untrusted input and narrow before use.
- DON'T annotate what TS already infers correctly (locals, return types of obvious functions). Annotate exported/public API boundaries; let inference handle the interior.
- DON'T model with `enum` when a string-literal union suffices — unions are erasable, tree-shakeable, and narrow cleanly.

## Checklist before shipping

- `strict` on; consider `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`.
- Every `switch` over a discriminated union has a `never` exhaustiveness default.
- No `as`/`any` used to silence an error — replaced by a guard, `satisfies`, or a correct type.
- Every `x is T` guard body actually proves `T` (no lying signatures).
- Derived types (`Pick`/`Omit`/`ReturnType`/`Awaited`) instead of re-declared parallel shapes.
- No unbounded template-literal cross-products or gratuitous recursive types.

## Sources

- https://www.typescriptlang.org/docs/handbook/2/mapped-types.html
- https://www.typescriptlang.org/docs/handbook/2/conditional-types.html
- https://www.typescriptlang.org/docs/handbook/2/narrowing.html
- https://www.typescriptlang.org/docs/handbook/utility-types.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-0.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-4.html
- https://www.typescriptlang.org/tsconfig/
