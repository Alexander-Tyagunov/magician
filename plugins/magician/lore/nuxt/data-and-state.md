# nuxt — Data fetching & state

Nuxt 3/4. Assumes JS/TS + Vue 3 lore. Composables are auto-imported. Nuxt-4-only changes flagged inline (checked vs nuxt.com 4.x).

## Pick the right tool

- `$fetch` — raw request (ofetch). Client-side events/mutations only.
- `useFetch(url, opts)` — SSR-safe wrapper over `useAsyncData` + `$fetch`. Default for loading component data by URL.
- `useAsyncData(key, handler, opts)` — SSR-safe wrapper for arbitrary async (custom `$fetch`, CMS/DB/query layer, multiple calls). More control.

`useFetch(url)` ≈ `useAsyncData(url, () => $fetch(url))` with an auto key.

## DO — useFetch / useAsyncData

- DO `await` them in `<script setup>` (they return a Promise). Blocking = data ready before render.
- DO destructure the reactive returns: `data`, `error`, `status`, `refresh`/`execute`, `clear`, `pending`. They are refs — use `.value` in script, unwrapped in template.
- DO gate the UI on `status` (`'idle' | 'pending' | 'success' | 'error'`), not on `data` truthiness.
- DO give `useAsyncData` an explicit string key. Auto keys derive from **file + line** only — a wrapping composable reused in N places collides.

```ts
const { data, status, error, refresh } = await useFetch('/api/posts')
const { data: user } = await useAsyncData('user:me', () => $fetch('/api/me'))
```

- DO use a **reactive URL/key** (getter/computed/ref) so it refetches on change. Watching a value alone won't rebuild the URL string.

```ts
const route = useRoute()
const { data } = await useFetch(() => `/api/posts/${route.params.id}`) // refetches on param change
```

- DO watch reactive `query`/`params`; they refetch automatically (`watch: true` default). Opt out with `watch: false`.
- DO use `pick` / `transform` to shrink the SSR payload.
- DO use `lazy: true` (or `useLazyFetch`/`useLazyAsyncData`) for non-blocking nav; handle `pending`/null data in the template.
- DO use `server: false` for client-only/private data — `data` stays `undefined` on the server pass and until hydration.
- DO set `immediate: false` for on-demand fetches, then call `execute()`/`refresh()`.
- DO share reads by reusing the **same key** — they share `data`/`error`/`status` refs (Nuxt 4 singleton layer). Read elsewhere with `useNuxtData(key)`.

## DON'T — useFetch / useAsyncData

- DON'T forget `await` — unawaited SSR fetch races hydration.
- DON'T wrap `useAsyncData` in a composable without an explicit key (auto-key collision → shared/wrong data).
- DON'T give same-key calls conflicting `handler`, `deep`, `transform`, `pick`, `getCachedData`, or `default` — dev warning + inconsistent state. (`server`, `lazy`, `immediate`, `dedupe`, `watch` may differ.)
- DON'T use these for side effects (analytics, Pinia mutations). They cache/read. Use `callOnce` for once-per-request side effects.
- DON'T pass a plain string you expect to react — pass a getter.

## Nuxt 4 changes (vs Nuxt 3) — verify before asserting versions

- `data` returned as **`shallowRef`** (was deep `ref`). Mutating a nested field won't trigger reactivity — reassign `.value`, or set `deep: true`.
- `data` and `error` **default to `undefined`** (were `null` in v3).
- `dedupe` takes string literals **`'cancel'` | `'defer'`** (booleans removed; `true`→`'cancel'`, `false`→`'defer'`).
- `getCachedData(key, nuxtApp, ctx)` now runs on **every** fetch incl. watcher/`refreshNuxtData` (v3 skipped it); `ctx.cause` says why.
- App code lives under `app/` by default; `server/` stays at root. Revert with `srcDir: '.'`.

## DO — $fetch

- DO use in event handlers / form submits / mutations: `await $fetch('/api/x', { method: 'POST', body })`.
- DO rely on it internally on the server hitting your own `/api/*` — Nuxt calls the handler directly, no real HTTP round trip.

## DON'T — $fetch

- DON'T call bare `$fetch` in `<script setup>` top-level for initial data — it runs on server **and** client (double fetch; no payload transfer). Wrap in `useAsyncData` or use `useFetch`.

## DO — useState (SSR-safe shared state)

- DO use `useState('key', () => init)` for state that must survive hydration and be shared across components. It's an SSR-friendly `ref` replacement, keyed globally.
- DO wrap in a composable for reuse + typing: `export const useCounter = () => useState('counter', () => 0)`.
- DO branch init on `import.meta.server` / `import.meta.client` when seeding from headers vs browser APIs.
- DO keep values JSON-serializable.

```ts
export const useColor = () => useState<string>('color', () => 'pink')
```

## DON'T — useState

- DON'T `const x = ref()` at **module top-level** and export it — on the server that ref is shared across all requests → cross-request state leak + memory leak. Always use `useState` (or a composable returning it).
- DON'T store classes, functions, symbols (breaks serialization), or server secrets (serializes to client payload).
- Reset with `clearNuxtState(key)`. For heavier app state, use Pinia (official).

## DO — runtimeConfig & secrets

- DO declare all runtime values in `nuxt.config`. Top-level = server-only; `public` = exposed to client.

```ts
runtimeConfig: { apiSecret: '', public: { apiBase: '/api' } }
```

- DO read with `useRuntimeConfig()`; in server routes pass the event: `useRuntimeConfig(event)`.
- DO override at runtime via env vars matching the shape with `NUXT_` prefix, `_` for nesting: `apiSecret`→`NUXT_API_SECRET`, `public.apiBase`→`NUXT_PUBLIC_API_BASE`.

## DON'T — runtimeConfig

- DON'T read a top-level (private) key on the client — only `public` and `app` exist there. Reading a secret client-side = leak.
- DON'T render a secret into markup, or push it into `useState`/`data`/props — all ship to the browser.
- DON'T map a config key to a differently named env var (`process.env.OTHER`) — works at build, breaks at runtime. Match names.
- DON'T rely on `.env` at production runtime — it's read only in dev/build/generate.

## DO — server routes (Nitro / h3)

- DO put API under `server/api/*` (auto `/api` prefix); use `server/routes/*` for no prefix.
- DO export `defineEventHandler(async (event) => {...})`; return a value → auto JSON.
- DO scope by method via filename suffix: `todos.get.ts`, `todos.post.ts` (unmatched method → 405).
- DO use dynamic segments `[id].ts` and read with `getRouterParam(event, 'id')`; catch-all `[...slug].ts`.
- DO read input with `getQuery(event)`, `await readBody(event)` (POST/PUT only), `parseCookies(event)`. Prefer validated variants `getValidatedQuery` / `readValidatedBody` (+ Zod) on untrusted input.
- DO error with `throw createError({ statusCode: 404, statusMessage })`; status via `setResponseStatus(event, 201)`.
- DO put secret-touching logic here — server routes never ship to the client. This is where private `runtimeConfig` is safe.

```ts
// server/api/posts/[id].get.ts
export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  const cfg = useRuntimeConfig(event)
  return await $fetch(`https://cms/${id}`, { headers: { Authorization: cfg.apiSecret } })
})
```

## DON'T — server routes

- DON'T `readBody` on a GET (throws 405).
- DON'T call external APIs with secret keys from a client component — proxy through a server route.
- DON'T import `app/` code into `server/` (different context); share via `shared/` or `#server` alias.

## Sources

- https://nuxt.com/docs/getting-started/data-fetching
- https://nuxt.com/docs/getting-started/state-management
- https://nuxt.com/docs/guide/going-further/runtime-config
- https://nuxt.com/docs/guide/directory-structure/server
- https://nuxt.com/docs/getting-started/upgrade
- https://nuxt.com/docs/api/composables/use-fetch
- https://nuxt.com/docs/api/composables/use-async-data
- https://nuxt.com/docs/api/utils/dollarfetch
