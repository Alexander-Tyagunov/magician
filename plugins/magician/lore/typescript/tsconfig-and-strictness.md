# typescript — tsconfig & strictness

Layers on top of the JavaScript lore. This is the type system + `tsconfig.json`. Facts verified against the TS handbook/tsconfig reference (TS 5.8 era, current cutoff). Don't re-teach JS here.

## DO — strict family
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

## DON'T — strict family
- DON'T assume `strict` covers everything. Two high-value flags are NOT enabled by it: `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`. Add them explicitly.
- DON'T disable `noImplicitAny` to "move fast" — an implicit `any` silently disables checking for that whole value.

## DO — beyond strict (opt in explicitly)
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

## DO — module / moduleResolution
- DO pick the pair that matches how the code is CONSUMED, not habit. `module` controls emit; `moduleResolution` controls how imports resolve.
- DO use `"module": "nodenext"` (TS 4.7) for code run directly by modern Node (22+); it tracks latest Node semantics, implies floating `--target esnext`, and picks ESM vs CJS per file from `package.json` `"type"` + extension (`.mts`/`.cts`). `nodenext` allows `require()` of ESM (Node 22+) and requires import attributes (`with`), not the deprecated `assert`.
- DO use `"module": "node18"` (TS 5.8) as a STABLE pin for Node 18 libraries — locks behavior: disallows `require(ESM)`, still allows import assertions. `node16` (TS 4.7) is the older pin. `node20` adds `require(ESM)`.
- DO use `"moduleResolution": "bundler"` (TS 5.0) when a bundler/transpiler (Vite, esbuild, webpack, swc) owns resolution: honors `package.json` `exports`/`imports`, allows extensionless relative paths. Must pair with `"module": "esnext"` or `"preserve"`; implies `allowSyntheticDefaultImports`.
- DO use `"module": "preserve"` (TS 5.4) when a runtime/bundler operates on raw `.ts` (Bun, ts loaders): each import/export keeps its written form; implies `moduleResolution: bundler` + `esModuleInterop`.
- DO set `moduleResolution` `node16`/`nodenext` ONLY with `module` `node16`/`node18`/`node20`/`nodenext` — they must agree.

## DON'T — modules
- DON'T use `moduleResolution: "node"`/`node10` for new code — it predates `exports`/`imports` and CJS-only.
- DON'T use `"classic"` ever.
- DON'T omit `.js` extensions in relative imports under `node16`/`nodenext` ESM emit — extensions are required (you write `.js` even for a `.ts` source). `bundler` does not require them.
- DON'T ship `assert { type: "json" }` — use `with { type: "json" }` (import attributes).

## DO — target, syntax fidelity
- DO set `target` to the lowest ES edition you must support; it decides downleveling and the default `lib`. For modern Node LTS (20/22/24), `ES2022`+ is safe. `nodenext` floats `target` to `esnext`.
- DO enable `verbatimModuleSyntax` (TS 5.0): forbids imports that would be silently emitted as `require`, forcing written syntax to match emit. Use `import type` / `export type` for type-only. Replaces the older `importsNotUsedAsValues` + `isolatedModules` type-elision guessing.

```ts
import { type User, createUser } from "./user"; // type-only elided, value kept
```

- DO enable `isolatedModules` when a single-file transpiler (babel/esbuild/swc) compiles each file alone — it bans constructs needing cross-file type info (re-exporting a type without `export type`, `const enum`, non-erasable namespaces).

## DON'T — target/syntax
- DON'T set `target` higher than your runtime supports to "avoid transpiling" — you'll ship syntax that throws.
- DON'T rely on `const enum` under `isolatedModules`/`verbatimModuleSyntax`; prefer plain `enum` or a `const` object + union.

## DO — libraries: declaration / composite
- DO set `"declaration": true` to emit `.d.ts` for a published package. Add `"declarationMap": true` (TS 2.9) so consumers "Go to Definition" jumps to your `.ts` source.
- DO use `"composite": true` for project references / monorepos; it implies `declaration: true` and requires `rootDir`. Pair with `tsc --build`.
- DO consider `isolatedDeclarations` (TS 5.5) for large libs: forces explicit return/export types so `.d.ts` can be emitted without full type-checking (faster parallel builds).

## skipLibCheck — tradeoff
- DO turn `skipLibCheck: true` ON for app code / CI speed: skips type-checking all `.d.ts` (yours + `node_modules`). Standard in most setups; avoids errors from conflicting third-party types you can't fix.
- DON'T leave it on blind for a PUBLISHED library — it can hide genuine errors in YOUR emitted `.d.ts`. Run a periodic build with `skipLibCheck: false`, or use `isolatedDeclarations` to keep declarations honest.

## Quick baselines
- Modern Node app (Node 22+): `strict`, `noUncheckedIndexedAccess`, `module: nodenext`, `moduleResolution: nodenext`, `target: es2022`, `verbatimModuleSyntax`, `skipLibCheck`.
- Bundled web app: `strict`, `noUncheckedIndexedAccess`, `module: esnext`, `moduleResolution: bundler`, `target: es2022`, `verbatimModuleSyntax`, `noEmit` (bundler emits).
- Published library: add `declaration`, `declarationMap`, `composite` (if referenced), `isolatedDeclarations`; audit with `skipLibCheck: false`.

## Sources
- https://www.typescriptlang.org/tsconfig/
- https://www.typescriptlang.org/docs/handbook/modules/reference.html
- https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-8.html
- https://www.typescriptlang.org/docs/handbook/intro.html
