# sveltekit — Forms, actions & server

Scope: form actions, progressive enhancement, hooks, env, adapters. Current: **SvelteKit 2 + Svelte 5** (runes). Assumes Svelte-5 syntax; Svelte-4 fallbacks noted. Assumes generic JS/TS lore exists elsewhere.

## Form actions (`+page.server.js`)

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

## Progressive enhancement (`use:enhance`)

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

## Hooks

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

## Env (`$env/*`)

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

## Adapters & deploy (`svelte.config.js`)

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

## Remote functions (experimental, since 2.27)

Type-safe client↔server calls in `*.remote.js`/`*.remote.ts` (anywhere in `src` except `src/lib/server`). Opt in: `kit.experimental.remoteFunctions: true` AND `compilerOptions.experimental.async: true`. Flavours from `$app/server`: `query` (read; `.refresh()`, `loading`, `error`; `.batch`, `.live`), `form` (write; spread onto `<form>`, built-in enhance/validation, auto-invalidates on success), `command` (write from anywhere; NOT during render), `prerender` (static reads). Validate args with any Standard Schema. Experimental — keep behind a flag.

## Sources
- https://svelte.dev/docs/kit/form-actions
- https://svelte.dev/docs/kit/hooks
- https://svelte.dev/docs/kit/$env-static-private
- https://svelte.dev/docs/kit/adapters
- https://svelte.dev/docs/kit/@sveltejs-kit
- https://svelte.dev/docs/kit/remote-functions
