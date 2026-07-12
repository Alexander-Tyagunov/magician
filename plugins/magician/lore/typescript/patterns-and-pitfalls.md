# typescript — Patterns & pitfalls

Type-system layer, on top of the JavaScript lore (JS runtime mechanics — coercion, `??`, `===`,
closures — live there). Baseline **TS 5.x** (5.9 current line; native Go port ships as TS 7.0).
Types are **erased** at runtime: they guide the compiler, they do not validate data. Trust the
compiler for internal shapes; validate at every boundary. Enable `strict` — everything assumes it.

## DO — tsconfig baseline

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

## DON'T — `any` and `as`

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

## DO — discriminated unions for domain modeling

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

## DO — branded / nominal types

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

## DO — structural typing gotchas

- DO know **excess property checks** fire only on *fresh* object literals; assign the literal to a
  variable first and extra props pass silently — a common "why didn't it catch my typo" moment.
- DO prefer `readonly` inputs — array/object types are covariant and method params bivariant
  (historical), both sources of unsound reads.
- DON'T rely on `private`/`#` for structural distinction alone; use a brand for true nominal intent.

## DO — the DTO / validation boundary (parse, don't cast)

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

## DO — typing async

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

## DO — generics vs overloads

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

## DO — declaration files & module augmentation

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

## Checklist before shipping

- `strict` on; add `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`.
- Grep for `any`, ` as `, `!` — each is a checked lie unless justified (`as const`, post-guard `unknown`).
- Every external input (`res.json`, `req.body`, env, `JSON.parse`) → schema `.parse`, never annotate-and-trust.
- Union domain models have a discriminant + exhaustive `switch` with `assertNever`.
- Same-primitive IDs/units → branded types; brand cast confined to one constructor.
- `catch (e: unknown)` and narrow; no floating promises.
- Run `npx tsc --noEmit` + `eslint` in CI; treat type errors as build failures.

## Sources

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
