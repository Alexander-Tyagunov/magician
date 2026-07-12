# SvelteKit — core digest

Version cue: SvelteKit 2 (Svelte 5 default = runes; Node 18.13+). SK2: `error()`/`redirect()` are called, not `throw`n; `cookies.set/delete` need a `path`; `goto` rejects external URLs.

Files (`+` prefix): `+page.svelte` (SSR+CSR); `+page.js`=universal load; `+page.server.js`=server-only load + form `actions`; `+layout.*` cascades; `+server.js`=API, server ONLY, HTTP-verb exports, ignores layouts; `+error.svelte`; `hooks.server.js`/`hooks.client.js`/`hooks.js`.

DO put db/secrets in `+page.server.js`; return only devalue-serializable data (JSON+Date/Map/Set/BigInt). Universal load may return anything.
DO use injected `event.fetch` in load/actions (relative URLs, cookie fwd, SSR)—not global `fetch`.
DON'T wrap `redirect()`/`error()` in `try/catch`, or catch them—they throw to control flow.
DO stream unresolved promises from SERVER load + `{#await}`; universal-load promises aren't streamed.
DO track reruns via `depends()`/`url`/`params`; refresh with `invalidate()`/`invalidateAll()`.
DO actions POST-only: `fail(400,{...})` to validate, `use:enhance` from `$app/forms`; `enctype="multipart/form-data"` for files.
DO secrets via `$env/static/private`; only `PUBLIC_`/`$env/*/public` reach client.
DO auth via `handle`+`event.locals`; `handleError` never throws.

Commands: `npx sv create` · `vite dev` · `vite build` · `vite preview` · `sv check`

Deep dive when writing non-trivial sveltekit — read lore/sveltekit/{routing-and-load,forms-and-server}.md
Sources: svelte.dev/docs/kit {routing,load,form-actions,hooks,migrating-to-sveltekit-2}
