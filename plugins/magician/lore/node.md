DON'T block the event loop: no `*Sync` fs/crypto or long CPU loops on request paths — offload to `worker_threads`. Keep handlers async and non-blocking.
DON'T drop rejections: `await` every promise, never mix callbacks with async/await, register `process.on('unhandledRejection')`. Add `'error'` handlers on `EventEmitter`/streams.
DO stream large data via `stream/promises` `pipeline()` — never `fs.readFile` a big file into memory; respect backpressure.
DON'T use `__dirname`/`require` in ESM — use `import.meta.dirname` (Node 20.11+) or `import.meta.url`. Import builtins with the `node:` prefix.
DO set `"type"` + `"engines"` in package.json; put `AbortSignal`/timeouts on `fetch` and I/O; validate `child_process` input and avoid `shell:true`.

Version: Node 24 Active LTS / 22 Maintenance (20 EOL Apr 2026, 18 EOL). Native `fetch` stable v21; `node:test` stable v20; `require(ESM)` unflagged v22.12/20.19; `node --run` + `--watch` v22; `--env-file` v20.6.

Commands: install `npm ci` | `pnpm i --frozen-lockfile`; run `node --run start` (Node 22+) | `npm start`; test `node --test` (Node 20+) | `vitest run`; lint `npm run lint` | `pnpm lint`.

Deep dive when writing non-trivial node — read lore/node/{runtime-and-event-loop,modules-and-packaging,async-streams-and-apis,errors-diagnostics-and-security,testing-and-tooling}.md

Sources: nodejs.org/docs/latest/api (modules, test, stream, process), nodejs.org/en/learn, github.com/nodejs/release
