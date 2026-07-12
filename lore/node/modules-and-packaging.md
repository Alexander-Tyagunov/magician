# node — Modules & packaging

Node.js runtime (server-side). Assumes javascript/typescript lore. Version cues below are
verified against nodejs.org (checked 2026-07). Current lines: **v26 Current, v24 Active LTS
(Krypton), v22 Maintenance LTS (Jod)**; v20 and v18 are EOL. Target an Active/Maintenance LTS
for production.

## Module system — ESM vs CommonJS

DO
- Set `"type"` explicitly in every `package.json`. `"module"` → `.js` is ESM; `"commonjs"`
  (or omitted) → `.js` is CommonJS. Explicit avoids syntax-detection cost and future drift.
- Rely on extensions to override `"type"` when needed: `.mjs` is **always** ESM, `.cjs` is
  **always** CommonJS (`.cjs` added in Node 12). Extension always wins over `"type"`.
- Prefer ESM for new code. Use `import`/`export`; there is no `module.exports` in ESM.

DON'T
- Don't assume `require('./foo')` resolves `foo.cjs` — it won't. Write `require('./foo.cjs')`.
- Don't mix `require` and `import` in the same file. Don't expect `__dirname`/`__filename`,
  `require`, `module`, or `exports` to exist in ESM.

## `__dirname` / `__filename` in ESM

DO — use `import.meta` (added v20.11.0 / v21.2.0; unflagged/stable v22.16.0 / v24.0.0):
```js
const __dirname = import.meta.dirname;   // dir of current module (file: URLs only)
const __filename = import.meta.filename;  // absolute path, symlinks resolved
// always available:
import { readFileSync } from 'node:fs';
const buf = readFileSync(new URL('./data.bin', import.meta.url));
```
- On Node < 20.11: derive from `import.meta.url`:
  `fileURLToPath(import.meta.url)` (`node:url`) → then `path.dirname(...)`.
- Resolve a specifier: `import.meta.resolve('pkg/asset.css')` returns a string synchronously
  (sync since v20.0.0 / v18.19.0).

DON'T reference `import.meta.dirname` in code that must run on old LTS without a fallback.

## `node:` protocol imports

DO prefix builtins: `import { sep } from 'node:path'`; `require('node:fs')`. `node:` works in
`require()` since v16 / v14.18. It disambiguates builtins from userland packages and is immune
to specifier remapping. Prefer it everywhere.

DON'T rely on bare `'fs'` in new code — a malicious/shadowing package named `fs` can hijack it.

## package.json `"exports"` (the entry contract)

DO
- Use `"exports"` as the entry point (Node 12+; takes precedence over `"main"`). Defining it
  **encapsulates** the package: any subpath not listed throws `ERR_PACKAGE_PATH_NOT_EXPORTED`.
- Target paths must be relative and start with `./`. Export `package.json` if consumers need it.
```json
{
  "exports": {
    ".": "./index.js",
    "./feature": "./src/feature.js",
    "./package.json": "./package.json"
  }
}
```
- Conditional exports — key **order = priority**, `"default"` **last**. Core conditions:
  `node-addons`, `node`, `import`, `require`, `module-sync`, `default`. `"import"`/`"require"`
  are mutually exclusive. Community: `"types"` (list **first**), `"browser"`,
  `"development"`/`"production"`.
```json
{ "exports": { ".": {
  "types": "./index.d.ts",
  "import": "./index.mjs",
  "require": "./index.cjs",
  "default": "./index.mjs"
} } }
```
- Subpath patterns use `*` as pure string replacement (matches across `/`); block subtrees
  with `null`: `{ "./features/*.js": "./src/features/*.js", "./features/internal/*": null }`.

DON'T
- Don't treat `"import"`/`"require"` as "ESM vs CJS" — they mark the *loader used*, not the
  file format. `require` can load static ESM (see below); `import` can load CJS/JSON/WASM.
- Don't keep a bare `"main"` as your only entry if you want encapsulation — add `"exports"`
  (optionally keep `"main"` too for pre-12 tooling).

## package.json `"imports"` (internal aliases)

DO map private internals with a `#` prefix (resolves only inside the package). Unlike
`"exports"`, `"imports"` **can** target external packages — use it for env-specific swaps:
```json
{ "imports": { "#dep": { "node": "dep-native", "default": "./polyfill.js" } } }
```
DON'T use `#`-specifiers from outside the package; they're package-private.

## Dual packages & the dual-package hazard

DO prefer shipping **one** format. If ESM-only, CJS consumers can `require()` it on modern
Node (below). If you must ship both, use `"node"`/`"default"` conditions or `"module-sync"`
to serve **one** module instance to both loaders.

DON'T ship separate `"import"`→ESM and `"require"`→CJS builds of a **stateful** package: the
runtime loads two copies → duplicated state, `instanceof` returns `false`, singletons break.
That's the dual-package hazard.

## require(ESM) — loading ES modules from CommonJS

Version history (verified): added v22.0.0 / v20.17.0 (behind `--experimental-require-module`);
**unflagged v23.0.0 / v22.12.0 / v20.19.0**; **fully stable v25.4.0**.

DO
- On modern LTS, `require('./esm.mjs')` works and returns the module namespace (default under
  `.default`). Detect support at runtime: `process.features.require_module === true`.
- For dynamic/older paths, build a scoped require: `import { createRequire } from 'node:module';
  const require = createRequire(import.meta.url);`

DON'T `require()` an ESM graph that uses **top-level `await`** — throws
`ERR_REQUIRE_ASYNC_MODULE`. Load those with dynamic `import()` instead. (`--no-require-module`
disables the feature entirely.)

## Package managers & lockfiles

DO
- Commit the lockfile: `package-lock.json` (npm), `pnpm-lock.yaml` (pnpm), `yarn.lock` (yarn).
- Use deterministic installs in CI: `npm ci` (npm), `pnpm install --frozen-lockfile`,
  `yarn install --immutable`.
- Pin the manager with the `"packageManager"` field (`"pnpm@9.x.x"`, with hash recommended).
- Consider pnpm for monorepos: content-addressable store + hard links (disk-efficient) and a
  non-flat, symlinked `node_modules` that blocks **phantom dependencies** (undeclared deps
  npm/yarn-classic expose via hoisting).

DON'T
- Don't rely on Corepack being present: bundled with Node 14.19.0 up to (not incl.) **25.0.0**,
  then removed from the distribution. Install the manager explicitly on Node 25+.
- Don't mix managers in one repo, and don't `.gitignore` the lockfile.

## Semver ranges (exact bounds)

DO know what your ranges permit:
- `^1.2.3` → `>=1.2.3 <2.0.0-0` (locks left-most non-zero digit).
- `^0.2.3` → `>=0.2.3 <0.3.0-0`; `^0.0.3` → `>=0.0.3 <0.0.4-0` (0.x is stricter).
- `~1.2.3` → `>=1.2.3 <1.3.0-0`; `~1.2` → `>=1.2.0 <1.3.0-0`; `~1` → `>=1.0.0 <2.0.0-0`.
- `1.2.x`/`1.2` → `>=1.2.0 <1.3.0-0`; `1.2.3 - 2.3.4` → `>=1.2.3 <=2.3.4`.

DON'T use `*`/`latest`/unbounded ranges for dependencies. Declare a real `"engines"` field to
fail installs on unsupported Node versions.

## Runtime alternatives (brief)

Deno (native TS, web-standard APIs, `deno.json`, `npm:` specifiers) and Bun (runtime + bundler +
manager, `bun.lockb`, high Node-compat) both speak ESM natively. Facts above are authoritative
for Node; verify runtime-specific behavior against each project's docs.

## Sources

- https://nodejs.org/docs/latest/api/packages.html
- https://nodejs.org/docs/latest/api/esm.html
- https://nodejs.org/docs/latest/api/modules.html
- https://nodejs.org/en/learn/modules/publishing-a-package
- https://nodejs.org/en/about/previous-releases
- https://github.com/nodejs/corepack#readme
- https://github.com/npm/node-semver
- https://docs.npmjs.com/cli/v10/configuring-npm/package-json
- https://pnpm.io/motivation
