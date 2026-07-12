# node — Errors, diagnostics & security

Server-side Node.js runtime layer. Assumes you also have javascript/typescript lore. Targets Node LTS lines **20 / 22 (Jod) / 24 (Krypton)**; 24 is Active LTS, 22 is Maintenance, 20 hit EOL 2026-04-30. Deno/Bun noted only as alternatives.

## Crash-on-fault: unhandledRejection / uncaughtException

DO
- Treat `uncaughtException` and unhandled rejection as **fatal**. Log, flush, exit non-zero, let a supervisor (systemd, k8s, pm2) restart. The process is in an undefined state — do not resume.
- Set a top-level handler for observability + synchronous cleanup only, then exit:
  ```js
  import process from 'node:process';
  process.on('uncaughtException', (err, origin) => {
    logger.fatal({ err, origin });      // sync-ish; don't await long
    process.exitCode = 1;
    // close server to stop new work, then let loop drain, or force-exit on timeout
  });
  process.on('unhandledRejection', (reason) => { throw reason; }); // route to uncaughtException
  ```
- Use `process.exitCode = N` + natural drain over `process.exit(N)`. `exit()` truncates pending stdout/stderr and kills the loop mid-write.
- Use `'uncaughtExceptionMonitor'` when you want to log *without* changing crash behavior (it never suppresses the crash).

DON'T
- Don't use `uncaughtException` as "on error resume next." Continuing after it leaks fds/handles and corrupts state. A `throw` inside the handler exits with the original fatal code (no loop).
- Don't rely on old warn-only rejection behavior. Since Node 15 default is `--unhandled-rejections=throw`: an unhandled rejection becomes an uncaught exception and crashes. Modes: `throw`(default), `strict`, `warn`, `none`.
- Don't `process.exit()` from a worker expecting the whole app to stop — it ends only that thread.

## Request context — AsyncLocalStorage

Stable since **Node 16.4**. The correct way to carry request id / user / tenant across `await` and callbacks without threading args.

DO
```js
import { AsyncLocalStorage } from 'node:async_hooks';
const als = new AsyncLocalStorage();               // {defaultValue, name} opts: Node 24+
app.use((req, _res, next) => als.run({ reqId: crypto.randomUUID() }, next));
function log(msg) { console.log(als.getStore()?.reqId ?? '-', msg); }
```
- Wrap each request in `als.run(store, cb)`. Read with `getStore()` anywhere downstream in that async tree.
- Lost context after a callback-style API? Re-bind with `AsyncResource.bind(fn)` (event listeners) or `AsyncLocalStorage.snapshot()` / `AsyncLocalStorage.bind(fn)` (stable Node 22.15 / 23.11). `util.promisify` callback APIs so native-promise context flows.

DON'T
- Don't prefer `enterWith()` — it persists for the whole sync execution and leaks the store into later, unrelated handlers. Use `run()`.
- Don't reach for raw `async_hooks` (`createHook`) unless building tracing infra — it's low-level and slows the runtime.

## Diagnostics

DO
- Debug: `node --inspect app.js` (attach anytime, binds `127.0.0.1:9229`), `--inspect-brk` (pause at line 1, startup bugs), `--inspect-wait` (block until client attaches). Open `chrome://inspect` or VS Code.
- CPU: `node --cpu-prof app.js` → `.cpuprofile` (load in DevTools ▸ Performance). Tick profiler: `node --prof` then `node --prof-process isolate-*.log`.
- Memory: `v8.writeHeapSnapshot('/tmp/x.heapsnapshot')` in-code; or `--heapsnapshot-signal=SIGUSR2` + `kill -USR2 <pid>`; sampling via `--heap-prof`. Diff two snapshots in DevTools ▸ Memory to find leaks.
- Crash forensics: `--report-uncaught-exception` (JSON diagnostic report with stacks, heap, libuv handles) or `process.report.writeReport()`.
- Dev loop: `node --watch app.js` / `--watch-path=./src` (stable Node 20+). Native `.env`: `node --env-file=.env` (Node 20+; `--env-file-if-exists` tolerates missing).
- Higher-level: `clinic doctor|flame|bubbleprof -- node app.js`.

DON'T
- Don't bind the inspector to `0.0.0.0` or a public IP — it's arbitrary RCE. Use `--inspect` (localhost default) + an SSH tunnel: `ssh -L 9221:localhost:9229 host`.
- Don't leave `--inspect` on in production; disable the `SIGUSR1` inspector trigger (`--disable-sigusr1`) to blunt DNS-rebinding.
- Don't block the event loop with sync I/O (`fs.readFileSync`, `crypto.*Sync`, heavy JSON) in request paths — it stalls every connection. Offload CPU work to `worker_threads`.

## Secrets & env

DO
- Read config from `process.env`; inject via orchestrator/secret manager. Use `node --env-file=.env` or `process.loadEnvFile(path)` for local dev only.
- Keep `.env` in `.gitignore` and `.npmignore`; use `package.json` `files` allowlist; `npm publish --dry-run` before publishing.
- Constant-time secret compare: `crypto.timingSafeEqual(a, b)`. Passwords: `crypto.scrypt`/argon2, never plain `===`.

DON'T
- Don't hardcode keys/tokens in source or commit `.env`. Don't log `process.env` wholesale. If a secret leaks to npm, unpublish + rotate.
- Don't put secrets or PII in URLs/query strings.

## Common vulns

DO
- **Command injection:** use `execFile`/`spawn` with an **args array** (no shell). Reserve `exec`/`execSync` for trusted static strings only.
  ```js
  import { execFile } from 'node:child_process';
  execFile('git', ['show', userInput], cb);   // safe: no shell interpolation
  ```
- **Path traversal:** resolve then confirm containment.
  ```js
  const base = path.resolve(UPLOAD_DIR);
  const p = path.resolve(base, userPath);
  if (p !== base && !p.startsWith(base + path.sep)) throw new Error('bad path');
  ```
- **Prototype pollution:** validate input against a schema (zod/ajv); use `Object.create(null)` maps, `Object.hasOwn(o,k)`, `Object.freeze(proto)`; reject `__proto__`/`constructor`/`prototype` keys; avoid unsafe recursive merge. `--disable-proto=delete` as defense-in-depth.

DON'T
- Don't pass user input into `exec`, `child_process.exec(\`cmd ${x}\`)`, or `shell:true`. Don't `eval`/`new Function` on input.
- Don't join user paths without a containment check; don't trust `..`-stripping regexes.
- Don't deep-merge untrusted JSON into config objects.

## Supply chain & hardening

DO
- Commit `package-lock.json`; CI uses `npm ci` (fails on lockfile drift), not `npm install`. Pin exact versions for apps.
- `npm audit` (and `--audit-level`) in CI; consider `--ignore-scripts` to block install-time code, dependency cooldown `--min-release-age` (npm 11.10+), Socket/Snyk for static analysis.
- **Permission Model** (stable Node 22.13 / 23.5; added 20, was `--experimental-permission`): least-privilege the process.
  ```bash
  node --permission --allow-fs-read=/app --allow-net app.js
  ```
  Flags: `--allow-fs-read`/`--allow-fs-write` (paths/globs/`*`), `--allow-child-process`, `--allow-worker`, `--allow-addons`, `--allow-net`. Check at runtime: `process.permission.has('fs.read', '/x')`; drop irreversibly: `process.permission.drop('child')`.
- HTTP DoS guards: set `server.headersTimeout`, `requestTimeout`, `keepAliveTimeout`; front with a reverse proxy. Never enable `insecureHTTPParser`.

DON'T
- Don't `npm install` in CI or ship without a committed lockfile. Don't run untrusted install scripts blindly.
- Don't treat `--permission` as a sandbox against malicious code — it's a seatbelt vs. accidental access, not a jail.

## Version cues
- ESM: no `__dirname`/`require` — use `import.meta.dirname`/`import.meta.filename` (Node 20.11+); `require(esm)` unflagged Node 22.12+.
- Built-in test runner `node:test` + `node --test`: stable Node 20+. Older lines: vitest/jest.
- `fetch`/`structuredClone` global: Node 18+ (WebSocket client stable 22+).
- TypeScript: run `.ts` directly — type-stripping on by default `node file.ts` (23.6+, backported 22.18+). Otherwise `tsx`/`ts-node` or precompile.

## Sources
- https://nodejs.org/docs/latest/api/process.html
- https://nodejs.org/docs/latest/api/async_context.html
- https://nodejs.org/docs/latest/api/permissions.html
- https://nodejs.org/en/learn/getting-started/security-best-practices
- https://nodejs.org/en/learn/getting-started/debugging
- https://nodejs.org/en/learn/command-line/how-to-read-environment-variables-from-nodejs
- https://github.com/nodejs/release
