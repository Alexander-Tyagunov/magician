# sveltekit — Routing & load

Scope: filesystem routing, `load` data flow, server vs universal boundary, streaming, `+server.js`, redirect/error helpers. Current line is **SvelteKit 2.x** (Svelte 5 runes). Notes flag v1→v2 and Svelte 4 fallbacks. Verify version-gated APIs against `svelte.dev/docs/kit`.

## Route files (the `+` files)

`src/routes` maps dirs → URLs. Only `+`-prefixed files are special; colocate anything else, share via `$lib`.

- `+page.svelte` — page component. Gets `data` prop from `load`; `params` prop added **2.24**.
- `+page.js` — **universal** `load` (`PageLoad`) + page options (`prerender`/`ssr`/`csr`). Runs server (SSR) AND client.
- `+page.server.js` — **server-only** `load` (`PageServerLoad`) + form `actions`. DB, secrets.
- `+layout.svelte` — shared wrapper; MUST render children (`{@render children()}` Svelte 5 / `<slot/>` Svelte 4). Nests down the tree.
- `+layout.js` / `+layout.server.js` — layout `load` (`LayoutLoad`/`LayoutServerLoad`); data flows to all children.
- `+server.js` — endpoints; server-only, no CSR.
- `+error.svelte` — nearest error boundary when `load` throws; walks up the tree. NOT triggered by errors in `+server.js` or `handle` hooks.

DO annotate with generated `$types`: `PageProps`/`LayoutProps` (added **2.16.0**; earlier: `PageData`/`LayoutData`). DON'T use a link component — plain `<a>`; SvelteKit intercepts.

## Server vs universal load — the boundary

| | Server (`*.server.js`) | Universal (`+page.js`/`+layout.js`) |
|---|---|---|
| Runs | server only | SSR + browser |
| Return | must be **devalue**-serializable | anything (classes, components) |
| Extra input | `cookies`, `locals`, `request`, `clientAddress`, `platform` | `data` (= server load's return, if both exist) |

DON'T read `env/private`, DB clients, or secrets in universal `load` — it ships to the browser. Put those in `+page.server.js`.
DO: when both exist, server runs **first**; its return becomes the universal load's `event.data`, and the universal return reaches the page. Missing `+layout.js` acts as `({ data }) => data`.

## load input & data flow

Both types receive: `params`, `route.id`, `url` (URL; `url.hash` unavailable), `fetch`, `setHeaders`, `parent`, `depends`, `untrack`.

DO use event `fetch` (not global) — inherits `cookie`/`authorization`, resolves relative paths, routes internal `+server.js` calls directly, inlines SSR responses for hydration reuse.
DO merge via `await parent()`; last key wins on collision. Fire independent fetches BEFORE `await parent()` to avoid waterfalls.
DO expose page data to ancestors via `page.data` (`$app/state`, added **2.12**; `$page` from `$app/stores` in Svelte 4 / earlier).

```js
// +page.server.js
import { error } from '@sveltejs/kit';
export async function load({ params, locals, cookies }) {
  const post = await db.get(params.slug);        // secret client stays server-side
  if (!post) error(404, 'Not found');            // v2: no `throw`
  return { post };                                // devalue-serializable
}
```

## Streaming (server load only)

DO return unresolved promises to stream; render with `{#await}`. v2 streams **top-level** promises; v1 auto-awaited top-level and only streamed nested ones.

```js
export function load() {
  return { one: await critical(), slow: slowQuery() }; // slow streams in
}
```
DON'T stream from universal `load` on an SSR page (needs JS). DON'T `setHeaders`/`redirect` inside a streamed promise. DO attach a `.catch()` (even noop) to streamed promises or an unhandled rejection can crash. Some platforms (AWS Lambda, Firebase) buffer instead of stream.

## Rerunning load / invalidation

- Auto-tracked: `params`, `url` searchParams (per-key), `fetch` URLs (**universal only** — server loads never auto-depend on fetches, to avoid leaking).
- `depends('app:foo' | url)` declares a custom/URL dep; `invalidate('app:foo')` / `invalidate(url)` reruns matching loads; `invalidateAll()` reruns everything.
- `untrack(fn)` opts sync code out. Tracking stops once `load` returns — read `params`/`url` in the main body, not inside async callbacks.
- `await parent()` reruns this load when the parent reruns.

## Cookies & headers

DO `cookies.get/set/delete` in **server** load only. `setHeaders` (both) affects SSR response only; setting the same header twice is an error; can't set `set-cookie` via it. Forwarded cookies go only to same host / more-specific subdomain.

## +server.js endpoints

Export `GET POST PUT PATCH DELETE OPTIONS HEAD` + `fallback` (catches other/custom methods). Each `(RequestEvent) => Response`.

```js
import { json, error } from '@sveltejs/kit';
export async function GET({ url }) {
  const q = url.searchParams.get('q');
  if (!q) error(400, 'q required');
  return json({ q });                 // sets Content-Type + Content-Length
}
```
DO know content negotiation when a route has both `+page` and `+server`: `PUT/PATCH/DELETE/OPTIONS` → always endpoint; `GET/POST/HEAD` → page only if `accept` prioritizes `text/html`. Layouts/hooks-boundaries don't wrap endpoints — use the `handle` hook.

## Redirect / error helpers (`@sveltejs/kit`)

- `error(status, body)` — status **400–599**; renders nearest `+error.svelte`; skips `handleError`.
- `redirect(status, location)` — status **300–308** (303 GET, 307 keep-method, 308 permanent).
- `fail(status, data?)` — **400–599**, action validation failure (not a throw).
- `json(data, init?)`, `text(body, init?)` — build `Response`.
- Guards: `isRedirect(e)`, `isHttpError(e, status?)`.

DON'T wrap `error`/`redirect` in `try/catch` — in v2 they signal control flow by throwing internally; catching swallows them. v1 required you to `throw redirect(...)` / `throw error(...)`.

## Advanced routing

- `[param]` dynamic · `[...rest]` catch-all · `[[opt]]` optional (can't follow a rest param).
- Matchers: `src/params/foo.js` → `[slug=foo]`; run on server + client; `*.test/spec.js` excluded.
- `(group)` dirs group layouts without affecting URL. `@` breaks out: `+page@.svelte` → root layout; `+page@(app).svelte` → `(app)` layout; `+layout@.svelte` resets for children.
- Sort/specificity: more specific wins; matched `[x=type]` beats `[x]`; `[[opt]]`/`[...rest]` lowest; ties alphabetical.
- 404: nested `+error.svelte` won't catch unmatched routes — add a `[...path]` route that throws `error(404)`.
- Encode illegal chars `[x+nn]` / unicode `[u+nnnn]` (e.g. `.well-known` → `[x+2e]well-known`).

## Page options (cascade: child overrides parent; set app-wide on root layout)

- `prerender`: `true | false | 'auto'` (`'auto'` = prerender but keep in dynamic manifest). No form actions / no `url.searchParams` on prerendered pages. `entries()` lists dynamic instances to crawl.
- `ssr`: default `true`; `false` = empty shell (SPA when on root layout).
- `csr`: default `true`; `false` = no JS shipped (no enhance/HMR, full-page nav).
- `trailingSlash`: `'never'` (default) `| 'always' | 'ignore'`.
- `config`: adapter-specific (merged top level only). `prerender/trailingSlash/config/entries` also valid in `+server.js`.

DON'T run browser-only code at module top level of `+page.js`/`+layout.js` — non-literal page options force a server import.

## Sources
- https://svelte.dev/docs/kit/routing
- https://svelte.dev/docs/kit/load
- https://svelte.dev/docs/kit/advanced-routing
- https://svelte.dev/docs/kit/page-options
- https://svelte.dev/docs/kit/@sveltejs-kit
