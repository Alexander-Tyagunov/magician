# node — Testing & tooling

Server-side runtime layer. Assumes javascript/typescript lore. Version facts verified against nodejs.org / eslint.org / typescript-eslint.io / vitest.dev (2026-07). LTS context: Node 24 Active LTS, 22 Maintenance, 20 EOL Apr 2026, 26 Current.

## Test runner: pick one

DO default to the **built-in `node:test`** on Node 20+ — zero deps, stable since **v20.0.0**. Reach for a framework only when you need its ecosystem.
DO use **Vitest** (v4; needs Vite ≥6, Node ≥20) for Vite/frontend-adjacent code, ESM/TS out of the box, Jest-compatible `expect`, watch UI, in-source tests.
DO keep **Jest** only on legacy suites; it needs `ts-jest`/`@swc/jest` for TS and its ESM support is still flagged/experimental. Don't start new projects on it.
DON'T mix two runners in one package.

## node:test — the checklist

DO import from the `node:` scheme only; write async or sync, not both.
```js
import { test, describe, it, before, beforeEach, mock } from 'node:test';
import assert from 'node:assert/strict';

describe('orders', () => {
  beforeEach(() => {/* fresh fixture */});
  it('places', async () => { assert.equal(await place(), 'ok'); });
});
```
DO `await` every subtest (`await t.test(...)`) — the parent does **not** wait for un-awaited subtests; they're cancelled and fail. Suites (`describe`) *do* await their `it`s.
DO pass options as the 2nd arg: `{ concurrency, only, skip, todo, timeout, signal }`. `concurrency` default is `false` (serial); set a number or `true` for parallel independent tests.
DO run with `node --test` (globs `**/*.test.{js,ts,…}`, `**/*-test.*`, `test/**`). Filter with `--test-name-pattern=<regex>`; watch with `--test --watch` (experimental).
DON'T rely on test order or shared mutable module state — each file runs in its own child process (`isolation:'process'`) by default.

### Mocking (built in — no library)
DO use `mock.fn()` / `t.mock.method(obj,'m')`; assert via `fn.mock.callCount()` and `fn.mock.calls[i].arguments`. Per-test `t.mock.*` auto-restores; top-level `mock.*` needs `mock.reset()`/`restoreAll()`.
DO fake time with `mock.timers.enable({ apis:['setTimeout','Date'] })` then `mock.timers.tick(ms)` / `setTime(ts)`. Don't destructure `node:timers` imports — unsupported by the timer mock.

### assert
DO use `node:assert/strict` (or `assert.strict`) so `equal`/`deepEqual` are `===`-based. Key API: `strictEqual`, `deepStrictEqual`, `throws(fn, expected)`, `await rejects(promise, expected)`, `match(str, re)`.
DON'T use loose `assert.equal` from plain `node:assert` — coercion hides bugs.

### Snapshots & reporters
DO note snapshot testing is **stable since v23.4.0**; update with `--test-update-snapshots`.
DO pick a reporter with `--test-reporter` (`spec` is the default since v23, plus `tap`, `dot`, `junit`, `lcov`); import from `node:test/reporters`. Multiple reporters need paired `--test-reporter-destination`.

## Coverage

DO use the built-in collector: `node --test --experimental-test-coverage` — still **experimental (Stability 1)**; core + `node_modules/` excluded, scope with `--test-coverage-include/exclude`, emit lcov via `--test-reporter=lcov`.
DO reach for **c8** or Vitest's `@vitest/coverage-v8` when you need thresholds/HTML without the flag. Don't make a coverage % the goal — assert behavior.

## Running & bundling TS

DO run TS directly in dev with **Node's native type stripping** — flagged `--experimental-strip-types` in **v22.6**, unflagged by default since **v23.6 / v22.18**, **stable v24.12 / v25.2**. `tsconfig.json` is ignored; extensions are mandatory (`import './x.ts'`); `.tsx` unsupported.
DON'T use non-erasable syntax under native stripping — **enums, `namespace` with runtime values, parameter properties** need code generation. The transform flag (`--experimental-transform-types`) was **removed in v26**, so on modern Node those require a real transpiler (tsx/swc/tsc). Set `"erasableSyntaxOnly": true` (TS 5.8+) + `"verbatimModuleSyntax": true` to catch this at compile time.
DO use **tsx** when you need full TS features / path aliases / watch that native stripping lacks: `tsx script.ts`, `tsx watch`.
DON'T ship a bundle without a separate **`tsc --noEmit`** — every fast tool below **skips type checking**.

| Tool | Role | Type-check? | Use for |
|---|---|---|---|
| esbuild | bundler + transpiler (Go) | no | fast app/lib bundles, ESM/CJS/IIFE |
| swc | transpiler (Rust) | no | drop-in Babel replacement, `@swc/jest` |
| tsx | TS/ESM runner (esbuild) | no | dev/scripts |
| tsup | esbuild wrapper for **libraries** | emits `.d.ts` | dual ESM+CJS + declarations |
| tsc | official compiler | **yes** | type-check gate, exact `.d.ts` |

DO build publishable **libraries** with `tsup` (`format:['esm','cjs']`, `dts:true`, `sourcemap`, `target`, `minify`) — it wraps esbuild and generates declarations.

## Lint & format

DO use **ESLint flat config** (`eslint.config.{js,mjs,ts}`) — the default since **v9** (2024-04); v10 (current, 2026-02) **removed** the legacy `.eslintrc`. Export an array of config objects with `files`/`ignores`/`languageOptions`/`plugins`/`rules`; wrap in `defineConfig` from `eslint/config`.
```js
import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import tseslint from 'typescript-eslint';

export default defineConfig([
  js.configs.recommended,
  tseslint.configs.recommended,
]);
```
DON'T keep `.eslintrc*` on ESLint 10 — it no longer loads. Don't hand-roll TS parsing; use the **typescript-eslint** (v8) package.
DO enable **type-aware rules** when worth the cost: add `tseslint.configs.recommendedTypeChecked` + `languageOptions.parserOptions.projectService = true` and `tsconfigRootDir: import.meta.dirname`. It's slower (runs a TS build); disable on non-TS files via `disableTypeChecked`. Don't re-implement formatting rules in ESLint.

DO choose one formatter/toolchain:
- **Prettier** — the safe default formatter; pair with ESLint (`eslint-config-prettier` to drop conflicts).
- **Biome** (v2, Rust) — one binary that **lints + formats** JS/TS/JSX/JSON/CSS/GraphQL, near-Prettier compatible, far faster. Config `biome.json`; run `biome check --write` (format + lint + organize imports), `biome ci` in CI. Good for replacing ESLint+Prettier when its rule set covers you; it has fewer plugins/rules than the ESLint ecosystem.
DON'T run both Biome and ESLint+Prettier on the same files — pick one lane.

## Monorepo

DO use **pnpm workspaces** — declare packages in `pnpm-workspace.yaml`; link internals with the `workspace:*` protocol; run across all with `pnpm -r <script>`, target one with `pnpm --filter <pkg>...`. Its strict, content-addressed `node_modules` blocks phantom deps.
DO install reproducibly in CI: `pnpm i --frozen-lockfile`.
DO add **Turborepo** (v2.x) for task orchestration + caching over the workspace. `turbo.json` has a top-level **`tasks`** key (renamed from `pipeline` in **Turbo 2.0**); each task sets `dependsOn` (`"^build"` = build deps first, topological), `outputs` (globs to cache), `inputs`, `cache`, `persistent` (dev servers), `env`.
```json
{ "tasks": { "build": { "dependsOn": ["^build"], "outputs": ["dist/**"] },
             "dev":   { "cache": false, "persistent": true } } }
```
DON'T set `cache:true` on `dev`/watch tasks, and don't let a task `dependsOn` a `persistent` one. **Nx** suits larger/polyglot repos; npm/yarn workspaces are the leaner built-in alternative.

## Alt runtimes (brief)
**Deno** (`deno test`/fmt/lint, TS-native, permissions) and **Bun** (`bun test`, Jest-like, fast; built-in bundler) are all-in-one alternatives. They diverge from Node on some APIs — verify parity before porting.

## Sources
- https://nodejs.org/docs/latest/api/test.html
- https://nodejs.org/docs/latest/api/assert.html
- https://nodejs.org/api/typescript.html
- https://github.com/nodejs/release
- https://eslint.org/docs/latest/use/configure/configuration-files
- https://eslint.org/version-support
- https://typescript-eslint.io/getting-started/
- https://typescript-eslint.io/getting-started/typed-linting/
- https://biomejs.dev/guides/getting-started/
- https://vitest.dev/guide/
- https://esbuild.github.io/
- https://tsup.egoist.dev/
- https://pnpm.io/workspaces
- https://turborepo.dev/docs/reference/configuration
