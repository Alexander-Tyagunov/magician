# sveltekit — deep dive

> On-demand companion to `lore/sveltekit.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Routing & load](#routing-and-load) · [Forms, actions & server](#forms-and-server)

## Routing & load <a id="routing-and-load"></a>

Scope: filesystem routing, `load` data flow, server vs universal boundary, streaming, `+server.js`, redirect/error helpers. Current line is **SvelteKit 2.x** (Svelte 5 runes). Notes flag v1→v2 and Svelte 4 fallbacks. Verify version-gated APIs against `svelte.dev/docs/kit`.

### Route files (the `+` files)

`src/routes` maps dirs → URLs. Only `+`-prefixed files are special; colocate anything else, share via `$lib`.

- `+page.svelte` — page component. Gets `data` prop from `load`; `params` prop added **2.24**.
- `+page.js` — **universal** `load` (`PageLoad`) + page options (`prerender`/`ssr`/`csr`). Runs server (SSR) AND client.
- `+page.server.js` — **server-only** `load` (`PageServerLoad`) + form `actions`. DB, secrets.
- `+layout.svelte` — shared wrapper; MUST render children (`{@render children()}` Svelte 5 / `<slot/>` Svelte 4). Nests down the tree.
- `+layout.js` / `+layout.server.js` — layout `load` (`LayoutLoad`/`LayoutServerLoad`); data flows to all children.
- `+server.js` — endpoints; server-only, no CSR.
- `+error.svelte` — nearest error boundary when `load` throws; walks up the tree. NOT triggered by errors in `+server.js` or `handle` hooks.

DO annotate with generated `$types`: `PageProps`/`LayoutProps` (added **2.16.0**; earlier: `PageData`/`LayoutData`). DON'T use a link component — plain `<a>`; SvelteKit intercepts.

### Server vs universal load — the boundary

| | Server (`*.server.js`) | Universal (`+page.js`/`+layout.js`) |
|---|---|---|
| Runs | server only | SSR + browser |
| Return | must be **devalue**-serializable | anything (classes, components) |
| Extra input | `cookies`, `locals`, `request`, `clientAddress`, `platform` | `data` (= server load's return, if both exist) |

DON'T read `env/private`, DB clients, or secrets in universal `load` — it ships to the browser. Put those in `+page.server.js`.
DO: when both exist, server runs **first**; its return becomes the universal load's `event.data`, and the universal return reaches the page. Missing `+layout.js` acts as `({ data }) => data`.

### load input & data flow

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

### Streaming (server load only)

DO return unresolved promises to stream; render with `{#await}`. v2 streams **top-level** promises; v1 auto-awaited top-level and only streamed nested ones.

```js
export function load() {
  return { one: await critical(), slow: slowQuery() }; // slow streams in
}
```
DON'T stream from universal `load` on an SSR page (needs JS). DON'T `setHeaders`/`redirect` inside a streamed promise. DO attach a `.catch()` (even noop) to streamed promises or an unhandled rejection can crash. Some platforms (AWS Lambda, Firebase) buffer instead of stream.

### Rerunning load / invalidation

- Auto-tracked: `params`, `url` searchParams (per-key), `fetch` URLs (**universal only** — server loads never auto-depend on fetches, to avoid leaking).
- `depends('app:foo' | url)` declares a custom/URL dep; `invalidate('app:foo')` / `invalidate(url)` reruns matching loads; `invalidateAll()` reruns everything.
- `untrack(fn)` opts sync code out. Tracking stops once `load` returns — read `params`/`url` in the main body, not inside async callbacks.
- `await parent()` reruns this load when the parent reruns.

### Cookies & headers

DO `cookies.get/set/delete` in **server** load only. `setHeaders` (both) affects SSR response only; setting the same header twice is an error; can't set `set-cookie` via it. Forwarded cookies go only to same host / more-specific subdomain.

### +server.js endpoints

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

### Redirect / error helpers (`@sveltejs/kit`)

- `error(status, body)` — status **400–599**; renders nearest `+error.svelte`; skips `handleError`.
- `redirect(status, location)` — status **300–308** (303 GET, 307 keep-method, 308 permanent).
- `fail(status, data?)` — **400–599**, action validation failure (not a throw).
- `json(data, init?)`, `text(body, init?)` — build `Response`.
- Guards: `isRedirect(e)`, `isHttpError(e, status?)`.

DON'T wrap `error`/`redirect` in `try/catch` — in v2 they signal control flow by throwing internally; catching swallows them. v1 required you to `throw redirect(...)` / `throw error(...)`.

### Advanced routing

- `[param]` dynamic · `[...rest]` catch-all · `[[opt]]` optional (can't follow a rest param).
- Matchers: `src/params/foo.js` → `[slug=foo]`; run on server + client; `*.test/spec.js` excluded.
- `(group)` dirs group layouts without affecting URL. `@` breaks out: `+page@.svelte` → root layout; `+page@(app).svelte` → `(app)` layout; `+layout@.svelte` resets for children.
- Sort/specificity: more specific wins; matched `[x=type]` beats `[x]`; `[[opt]]`/`[...rest]` lowest; ties alphabetical.
- 404: nested `+error.svelte` won't catch unmatched routes — add a `[...path]` route that throws `error(404)`.
- Encode illegal chars `[x+nn]` / unicode `[u+nnnn]` (e.g. `.well-known` → `[x+2e]well-known`).

### Page options (cascade: child overrides parent; set app-wide on root layout)

- `prerender`: `true | false | 'auto'` (`'auto'` = prerender but keep in dynamic manifest). No form actions / no `url.searchParams` on prerendered pages. `entries()` lists dynamic instances to crawl.
- `ssr`: default `true`; `false` = empty shell (SPA when on root layout).
- `csr`: default `true`; `false` = no JS shipped (no enhance/HMR, full-page nav).
- `trailingSlash`: `'never'` (default) `| 'always' | 'ignore'`.
- `config`: adapter-specific (merged top level only). `prerender/trailingSlash/config/entries` also valid in `+server.js`.

DON'T run browser-only code at module top level of `+page.js`/`+layout.js` — non-literal page options force a server import.

### Sources
- https://svelte.dev/docs/kit/routing
- https://svelte.dev/docs/kit/load
- https://svelte.dev/docs/kit/advanced-routing
- https://svelte.dev/docs/kit/page-options
- https://svelte.dev/docs/kit/@sveltejs-kit

## Forms, actions & server <a id="forms-and-server"></a>

Scope: form actions, progressive enhancement, hooks, env, adapters. Current: **SvelteKit 2 + Svelte 5** (runes). Assumes Svelte-5 syntax; Svelte-4 fallbacks noted. Assumes generic JS/TS lore exists elsewhere.

### Form actions (`+page.server.js`)

DO
- Define actions in `+page.server.js` under `export const actions`. Type with `Actions` from `./$types`.
- Use ONE default action OR named actions — never both (named actions leave a `?/name` query param that collides with default).
- Read body with `await request.formData()`; return JSON-serializable data (plus `Date`/`BigInt`).
- Return validation errors with `fail(status, data)` from `@sveltejs/kit` (400/422). Echo back user input (e.g. `email`), never secrets.
- Read result in the page via the `form` prop; app-wide via `page.form`, status via `page.status`.

```js
// +page.server.js
import { fail, redirect } from '@sveltejs/kit';
/** @satisfies {import('./$types').Actions} */
export const actions = {
  login: async ({ cookies, request, url }) => {
    const data = await request.formData();
    const email = data.get('email');
    if (!email) return fail(400, { email, missing: true });
    const user = await db.getUser(email);
    if (!user) return fail(400, { email, incorrect: true });
    cookies.set('sessionid', await db.createSession(user), { path: '/' });
    if (url.searchParams.has('redirectTo')) redirect(303, url.searchParams.get('redirectTo'));
    return { success: true };
  }
};
```
```svelte
<!-- +page.svelte (Svelte 5) -->
<script> let { form } = $props(); </script>
<form method="POST" action="?/login">
  <input name="email" value={form?.email ?? ''} />
  {#if form?.missing}<p>Email required</p>{/if}
</form>
```

DON'T
- DON'T give actions side effects on GET — actions are POST-only.
- DON'T `throw fail(...)` — `fail` is returned; `redirect`/`error` are thrown-by-call (`redirect(303, ...)` in v2; no `throw` needed).
- DON'T assume `event.locals` refreshes after an action. `handle` runs BEFORE the action and does NOT rerun before `load`. When you set/clear a cookie in an action, mutate `event.locals` directly too:

```js
logout: async (event) => {
  event.cookies.delete('sessionid', { path: '/' });
  event.locals.user = null; // else load() still sees stale user
}
```

Form targeting: `action="?/register"` (named), `action="/login?/register"` (cross-page), or per-button `formaction="?/register"`. Non-mutating search? Use `<form action="/search">` (GET) — routes client-side, runs `load`, no action.

Props typing: `PageProps` from `./$types` (since **2.16.0**): `let { data, form }: PageProps = $props();`. Older: `let { data, form }: { data: PageData; form: ActionData } = $props();`. Svelte 4: `export let data; export let form;`.

### Progressive enhancement (`use:enhance`)

DO
- Import `enhance` from `$app/forms`; add `use:enhance` to a `method="POST"` form. Bare `use:enhance` emulates native behavior sans reload: updates `form`/`page.form`/`page.status` (same-page only), resets the form, `invalidateAll()` on success, `goto()` on redirect, renders nearest `+error` on error, resets focus.
- Customize with a `SubmitFunction`: receives `{ formElement, formData, action, cancel, submitter }`; return `async ({ result, update }) => {}`. Call `update()` (opts `{ reset, invalidateAll }`) to restore default logic, or `applyAction(result)`.

```svelte
<script> import { enhance, applyAction } from '$app/forms'; import { goto } from '$app/navigation'; </script>
<form method="POST" use:enhance={() => async ({ result }) =>
  result.type === 'redirect' ? goto(result.location) : applyAction(result)}>
```

DON'T
- DON'T `use:enhance` on `method="GET"` forms or on `+server.js` endpoints — it throws.
- DON'T `JSON.parse` an action response in a hand-rolled handler — use `deserialize` from `$app/forms` (actions can return `Date`/`BigInt`).
- DON'T forget: when a `+server.js` sits beside the page, a manual `fetch` to the action needs header `'x-sveltekit-action': 'true'`.

`applyAction(result)` by type: `success`/`failure` → set status + `form`/`page.form` (regardless of origin, unlike `update`); `redirect` → `goto(location, { invalidateAll: true })`; `error` → nearest `+error`.

### Hooks

Files: `src/hooks.server.js` (server), `src/hooks.client.js` (client), `src/hooks.js` (universal). Types from `@sveltejs/kit`.

`handle` (server) — runs on every request; owns the response.
DO
- Populate `event.locals` for downstream `load`/`+server.js`. Compose multiple handles with `sequence` from `@sveltejs/kit/hooks`.
- Short-circuit by returning a `Response` before `resolve(event)`.
- Use `resolve(event, opts)`: `transformPageChunk({ html, done })`, `filterSerializedResponseHeaders(name, value)` (default: none forwarded), `preload({ type, path })` (default: js+css).

```js
import { redirect, type Handle } from '@sveltejs/kit';
export const handle: Handle = async ({ event, resolve }) => {
  event.locals.user = await getUser(event.cookies.get('sessionid'));
  if (event.url.pathname.startsWith('/admin') && !event.locals.user) redirect(303, '/login');
  return resolve(event, { transformPageChunk: ({ html }) => html.replace('%THEME%', 'dark') });
};
```
DON'T
- DON'T mutate immutable response headers (e.g. from `Response.redirect()`) — throws `TypeError`.
- DON'T trust `route`/`params`/`url` for authz on remote-function requests — they reflect the calling page and are manipulable.

`handleFetch` (server) — rewrite/redirect server-side `event.fetch`. Same-origin forwards `cookie`/`authorization`; cross-origin drops `cookie` unless subdomain. Sibling subdomains (api.x.com vs www.x.com): set `cookie` manually.

`handleError` (server + client) — last-resort logging; return value becomes `page.error` (shape = `App.Error`, must include `message`). Not called for expected `error()`. Must never throw. Client type is `HandleClientError` (event is `NavigationEvent`).

`init` (`ServerInit`, since **2.10.0**) — one-time async startup (DB connect). `reroute` (universal, since **2.3.0**; async since **2.18**) — remap URL→route; pure/idempotent, cached per URL; does NOT change address bar. `transport` (since **2.11.0**) — `encode`/`decode` custom classes across the SSR boundary. `handleValidationError` — remote-function Standard-Schema failures → `App.Error` (400).

### Env (`$env/*`)

Two axes: static (build-time, inlined, dead-code-elim) vs dynamic (runtime); private (server-only) vs public (`PUBLIC_` prefix, client-safe).

| Module | Client? | Resolved |
|---|---|---|
| `$env/static/private` | no | build |
| `$env/static/public` | yes | build |
| `$env/dynamic/private` | no | runtime |
| `$env/dynamic/public` | yes | runtime |

DO
- Default private for secrets: `import { API_KEY } from '$env/static/private'`.
- Use `$env/dynamic/*` when the value differs per-deploy/runtime (containers, serverless). Prefer static for perf (inlined, tree-shakeable).
- Prefix client-exposed vars `PUBLIC_`; customize via `config.kit.env.publicPrefix`/`privatePrefix`.

DON'T
- DON'T import private modules into client code — build error.
- DON'T expect `$env/static/*` to reflect runtime env — values are frozen at build. Use dynamic if you need runtime.

### Adapters & deploy (`svelte.config.js`)

Adapters convert the build for a target; set `kit.adapter`. Packages: `@sveltejs/adapter-auto` (zero-config, detects platform), `-node`, `-static` (SSG), `-vercel`, `-cloudflare`, `-netlify`.

```js
import adapter from '@sveltejs/adapter-node';
export default { kit: { adapter: adapter() } };
```

DO
- Swap `adapter-auto` for the concrete adapter once you know the target (auto pulls it at build).
- Access platform extras (Cloudflare `env`/KV, etc.) via `event.platform` in hooks/`+server.js`/`load`.
- SSG: `adapter-static` + `export const prerender = true` per route (or in root layout).

DON'T
- DON'T rely on `platform` shape being portable — it's adapter-specific; guard usage.

### Remote functions (experimental, since 2.27)

Type-safe client↔server calls in `*.remote.js`/`*.remote.ts` (anywhere in `src` except `src/lib/server`). Opt in: `kit.experimental.remoteFunctions: true` AND `compilerOptions.experimental.async: true`. Flavours from `$app/server`: `query` (read; `.refresh()`, `loading`, `error`; `.batch`, `.live`), `form` (write; spread onto `<form>`, built-in enhance/validation, auto-invalidates on success), `command` (write from anywhere; NOT during render), `prerender` (static reads). Validate args with any Standard Schema. Experimental — keep behind a flag.

### Sources
- https://svelte.dev/docs/kit/form-actions
- https://svelte.dev/docs/kit/hooks
- https://svelte.dev/docs/kit/$env-static-private
- https://svelte.dev/docs/kit/adapters
- https://svelte.dev/docs/kit/@sveltejs-kit
- https://svelte.dev/docs/kit/remote-functions
