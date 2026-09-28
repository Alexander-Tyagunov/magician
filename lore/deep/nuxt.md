# nuxt — deep dive

> On-demand companion to `lore/nuxt.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Rendering & routing](#rendering-and-routing) · [Data fetching & state](#data-and-state) · [Config, modules & deploy](#config-and-modules)

## Rendering & routing <a id="rendering-and-routing"></a>

Scope: Nuxt 3 & 4 (current stable v4.4.x). Universal (SSR) default, file-based
routing, layouts, route middleware, hybrid rendering (`routeRules`), server
components / islands. Nuxt builds on **vue-router** + Nitro. Verify version
before asserting: `nuxt info` / `package.json`.

### Version map (read first)

- **Nuxt 4** default `srcDir` is `app/` → `~` and `@` point to `app/`. Dirs live
  at `app/pages`, `app/layouts`, `app/components`, `app/middleware`. `serverDir`
  is `<rootDir>/server`; `modules/`, `public/`, `layers/` resolve from `<rootDir>`.
  New `shared/` dir for code shared by Vue app + Nitro.
- **Nuxt 3** keeps these at project root (`pages/`, `layouts/`, `server/`).
- Nuxt 4 auto-detects the old layout; force v3 style with `srcDir: '.'`.
- `future.compatibilityVersion: 5` (v4.2+) opts into Nuxt 5 behaviors early.
- DO write paths version-adaptively: prefer `app/pages/…` for v4, `pages/…` for v3.

### Rendering modes

- DO leave **universal rendering (SSR)** on — it is the default (`ssr: true`).
  Server returns full HTML, client hydrates. Best for SEO, marketing, e-commerce.
- DO set `ssr: false` for pure SPA / back-office / gated dashboards; add
  `app/spa-loading-template.html` (v4) / `~/spa-loading-template.html` to avoid a
  blank screen.
- DON'T assume ESR is a separate mode — "edge-side rendering" is just SSR via
  Nitro deployed to a CDN edge (Cloudflare/Vercel/Netlify). It's a deploy target.
- DON'T reach for hybrid rendering under full static `nuxt generate` — route
  rules for caching are a Nitro-server concern.

### Hybrid rendering — `routeRules`

Per-route rendering/caching in `nuxt.config`. Keys use glob patterns.

```ts
export default defineNuxtConfig({
  routeRules: {
    '/':            { prerender: true },        // build-time static
    '/blog/**':     { isr: 3600 },              // ISR: CDN cache, revalidate 1h
    '/news/**':     { swr: 60 },                // stale-while-revalidate 60s
    '/admin/**':    { ssr: false },             // ship SPA for this branch
    '/api/legacy':  { redirect: '/api/v2' },    // server redirect
    '/old':         { redirect: { to: '/new', statusCode: 301 } },
    '/assets/**':   { headers: { 'cache-control': 's-maxage=31536000' } },
    '/api/**':      { cors: true },
  },
})
```

- Verified rule keys: `redirect`, `ssr`, `cors`, `headers`, `swr`, `isr`,
  `prerender`, `noScripts`, `appMiddleware`, `appLayout`. (`swr`/`isr` take
  `number` seconds or `boolean`.)
- DO use `isr` when your host has a CDN (Vercel/Netlify) — like `swr` but pushes
  to the CDN cache. `swr` caches on the server/proxy.
- DON'T invent `cache`/`static` as top-level route-rule keys in examples;
  fine-grained caching goes under Nitro's own `cache` handling, not shown here.
- Note: `isr`/`swr` routes emit `_payload.json` consumed on client nav.

### File-based routing (`pages/`)

- The `pages/` dir is **optional**: omit it and vue-router isn't bundled. Enable
  with any page file, `pages: true`, or a `router.options.ts`.
- DO add `<NuxtPage />` to `app.vue` to mount routed pages. Without it, `app.vue`
  renders for every route.
- DO know the filename conventions:
  - `about.vue` → `/about`, `index.vue` → `/`
  - `[id].vue` → `/:id` (dynamic) → `useRoute().params.id`
  - `[[slug]].vue` → optional param (matches `/` and `/x`)
  - `[...slug].vue` → catch-all (param is an array)
  - `parent.vue` + `parent/` dir → nested routes; parent MUST contain `<NuxtPage>`
- DON'T give a page multiple root elements — route transitions require one root.
- **Nuxt 4 additions**: route groups `(marketing)/` (no URL effect, exposed at
  `route.meta.groups`); named views `name@view.vue` → `<NuxtPage name="…" />`.

### Navigation

- DO link with `<NuxtLink>` (auto-imported) — SPA transitions after hydration,
  auto-prefetch on viewport entry.
- DO navigate programmatically with `navigateTo(...)` and `await` / `return` it.
- DO read route state with `useRoute()` in `<script setup>`; use `useRouter()`
  for imperative control.
- DON'T mutate `route.params` — treat route as read-only.

### `definePageMeta`

Compiler macro; hoisted out of setup → **no reactive/side-effectful values**.

```ts
definePageMeta({
  layout: 'admin',
  middleware: ['auth'],
  validate: async (route) => /^\d+$/.test(route.params.id as string),
  alias: ['/dashboard'],
  keepalive: true,
  key: (route) => route.fullPath,
})
```

- Verified keys: `layout`, `middleware`, `validate`, `alias`, `keepalive`,
  `key`, `name`, `path`, `props`, `pageTransition`, `layoutTransition`,
  `redirect`. Augment custom keys via the `PageMeta` interface from `#app`.
- `validate` returns `false` → 404, or `{ statusCode, statusMessage }`.
- **Nuxt 4**: `name`/`path` set here live on the route object, no longer
  duplicated on `route.meta` (`scanPageMeta` on by default). Override metadata in
  the new `pages:resolved` hook (scan now runs after `pages:extend`).

### Route middleware

- DO define with `defineNuxtRouteMiddleware((to, from) => {…})`. Return
  `navigateTo(...)`, `abortNavigation(...)`, or nothing.
- Three kinds: inline (in the page), **named** (`app/middleware/auth.ts`, applied
  via `definePageMeta`), **global** (`app/middleware/*.global.ts`, every nav).
- Names kebab-case: `someMiddleware` → `some-middleware`.
- DON'T expect route middleware to run for `/api/*` (Nitro) routes — use server
  middleware. It also does **not** run when rendering islands.
- Nuxt 4: `app/middleware/*/index.ts` subfolders are now scanned.

### Layouts

- DO wrap with `<NuxtLayout><NuxtPage/></NuxtLayout>` in `app.vue`;
  `app/layouts/default.vue` is the fallback. Page renders in the layout's
  `<slot />`.
- DON'T create a layout file when you only have one — use `app.vue` directly.
- Select per page: `definePageMeta({ layout: 'custom' })`; disable with
  `layout: false`. Switch at runtime with `setPageLayout('custom')`.
- Names normalize kebab-case; nested `layouts/desktop/default.vue` →
  `desktop-default`. Layout must have a single root element (not `<slot/>`).
- v4.4+: pass typed props — `layout: { name: 'panel', props: { title: 'X' } }`
  or `setPageLayout('panel', { title: 'X' })`; also `appLayout` in route rules.

### Server components & islands (experimental)

- Status: **experimental** — enable `experimental.componentIslands: true`.
  Context format may change. DON'T assume stable.
- DO use `.server.vue` components ("islands") to keep heavy libs (markdown,
  syntax highlight) out of the client bundle — always rendered server-side; prop
  changes trigger an in-place network re-render (via `<NuxtIsland>` internally).
- `.server.vue` / `.client.vue` **pages** also exist: server-only vs client-only
  page rendering.
- Island constraints: single root element; props passed as URL query params
  (length-limited); `useRoute()`/vue-router reflect the island request, not the
  page — pass route data explicitly; plugins re-run unless `env: { islands: false }`.
- Interactive island: add `nuxt-client` to a child inside a server component;
  requires `experimental.componentIslands.selectiveClient: true`
  (`'deep'` for client-component slots).
- DON'T confuse with `<ClientOnly>` (skips SSR for wrapped content) — that's a
  stable built-in, unrelated to islands.

### Sources

- https://nuxt.com/docs/getting-started/views
- https://nuxt.com/docs/getting-started/routing
- https://nuxt.com/docs/guide/concepts/rendering
- https://nuxt.com/docs/guide/directory-structure/pages
- https://nuxt.com/docs/guide/directory-structure/layouts
- https://nuxt.com/docs/guide/directory-structure/components
- https://nuxt.com/docs/getting-started/upgrade

## Data fetching & state <a id="data-and-state"></a>

Nuxt 3/4. Assumes JS/TS + Vue 3 lore. Composables are auto-imported. Nuxt-4-only changes flagged inline (checked vs nuxt.com 4.x).

### Pick the right tool

- `$fetch` — raw request (ofetch). Client-side events/mutations only.
- `useFetch(url, opts)` — SSR-safe wrapper over `useAsyncData` + `$fetch`. Default for loading component data by URL.
- `useAsyncData(key, handler, opts)` — SSR-safe wrapper for arbitrary async (custom `$fetch`, CMS/DB/query layer, multiple calls). More control.

`useFetch(url)` ≈ `useAsyncData(url, () => $fetch(url))` with an auto key.

### DO — useFetch / useAsyncData

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

### DON'T — useFetch / useAsyncData

- DON'T forget `await` — unawaited SSR fetch races hydration.
- DON'T wrap `useAsyncData` in a composable without an explicit key (auto-key collision → shared/wrong data).
- DON'T give same-key calls conflicting `handler`, `deep`, `transform`, `pick`, `getCachedData`, or `default` — dev warning + inconsistent state. (`server`, `lazy`, `immediate`, `dedupe`, `watch` may differ.)
- DON'T use these for side effects (analytics, Pinia mutations). They cache/read. Use `callOnce` for once-per-request side effects.
- DON'T pass a plain string you expect to react — pass a getter.

### Nuxt 4 changes (vs Nuxt 3) — verify before asserting versions

- `data` returned as **`shallowRef`** (was deep `ref`). Mutating a nested field won't trigger reactivity — reassign `.value`, or set `deep: true`.
- `data` and `error` **default to `undefined`** (were `null` in v3).
- `dedupe` takes string literals **`'cancel'` | `'defer'`** (booleans removed; `true`→`'cancel'`, `false`→`'defer'`).
- `getCachedData(key, nuxtApp, ctx)` now runs on **every** fetch incl. watcher/`refreshNuxtData` (v3 skipped it); `ctx.cause` says why.
- App code lives under `app/` by default; `server/` stays at root. Revert with `srcDir: '.'`.

### DO — $fetch

- DO use in event handlers / form submits / mutations: `await $fetch('/api/x', { method: 'POST', body })`.
- DO rely on it internally on the server hitting your own `/api/*` — Nuxt calls the handler directly, no real HTTP round trip.

### DON'T — $fetch

- DON'T call bare `$fetch` in `<script setup>` top-level for initial data — it runs on server **and** client (double fetch; no payload transfer). Wrap in `useAsyncData` or use `useFetch`.

### DO — useState (SSR-safe shared state)

- DO use `useState('key', () => init)` for state that must survive hydration and be shared across components. It's an SSR-friendly `ref` replacement, keyed globally.
- DO wrap in a composable for reuse + typing: `export const useCounter = () => useState('counter', () => 0)`.
- DO branch init on `import.meta.server` / `import.meta.client` when seeding from headers vs browser APIs.
- DO keep values JSON-serializable.

```ts
export const useColor = () => useState<string>('color', () => 'pink')
```

### DON'T — useState

- DON'T `const x = ref()` at **module top-level** and export it — on the server that ref is shared across all requests → cross-request state leak + memory leak. Always use `useState` (or a composable returning it).
- DON'T store classes, functions, symbols (breaks serialization), or server secrets (serializes to client payload).
- Reset with `clearNuxtState(key)`. For heavier app state, use Pinia (official).

### DO — runtimeConfig & secrets

- DO declare all runtime values in `nuxt.config`. Top-level = server-only; `public` = exposed to client.

```ts
runtimeConfig: { apiSecret: '', public: { apiBase: '/api' } }
```

- DO read with `useRuntimeConfig()`; in server routes pass the event: `useRuntimeConfig(event)`.
- DO override at runtime via env vars matching the shape with `NUXT_` prefix, `_` for nesting: `apiSecret`→`NUXT_API_SECRET`, `public.apiBase`→`NUXT_PUBLIC_API_BASE`.

### DON'T — runtimeConfig

- DON'T read a top-level (private) key on the client — only `public` and `app` exist there. Reading a secret client-side = leak.
- DON'T render a secret into markup, or push it into `useState`/`data`/props — all ship to the browser.
- DON'T map a config key to a differently named env var (`process.env.OTHER`) — works at build, breaks at runtime. Match names.
- DON'T rely on `.env` at production runtime — it's read only in dev/build/generate.

### DO — server routes (Nitro / h3)

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

### DON'T — server routes

- DON'T `readBody` on a GET (throws 405).
- DON'T call external APIs with secret keys from a client component — proxy through a server route.
- DON'T import `app/` code into `server/` (different context); share via `shared/` or `#server` alias.

### Sources

- https://nuxt.com/docs/getting-started/data-fetching
- https://nuxt.com/docs/getting-started/state-management
- https://nuxt.com/docs/guide/going-further/runtime-config
- https://nuxt.com/docs/guide/directory-structure/server
- https://nuxt.com/docs/getting-started/upgrade
- https://nuxt.com/docs/api/composables/use-fetch
- https://nuxt.com/docs/api/composables/use-async-data
- https://nuxt.com/docs/api/utils/dollarfetch

## Config, modules & deploy <a id="config-and-modules"></a>

Current stable: **Nuxt 4.x** (released **2025-07-15**). Nuxt 3 in maintenance until end of Jan 2026. Verify the project's `nuxt` version before writing — directory layout and data-fetching defaults diverge between 3 and 4.

Version anchors:
- **`srcDir` default is `app/`** in Nuxt 4 (was `.`/root in Nuxt 3). App code → `app/`, server → `<rootDir>/server`, new `shared/` dir; `~`/`@` alias → `app/`.
- **`compatibilityDate`** pins date-sensitive behavior of Nitro presets, Nuxt Image, and other modules so they don't shift without a major bump. Set once (`YYYY-MM-DD`).
- **`future.compatibilityVersion: 4`** in Nuxt 3 opted into v4 early; `: 5` opts into Nuxt 5 defaults (in development). v4 behavior is default on v4; a compat fallback keeps old layouts working.
- Data fetching (v4): `data`/`error` default to `undefined` (was `null`); `data` is a `shallowRef`; same-key `useAsyncData`/`useFetch` share one ref.

Config: `nuxt.config.ts` via `defineNuxtConfig({...})`. Modules run **sequentially** in array order — order matters.

### nuxt.config essentials

DO
- Always set `compatibilityDate` and `modules`. Keep secrets out of the config file itself — use `runtimeConfig` + env.
- Use per-environment overrides: `$production`, `$development`, `$env: { staging: {...} }`. Select with `nuxt build --envName staging`.
- Put hybrid-rendering rules in `routeRules` (per-path): `prerender`, `ssr: false`, `isr`, `swr`, `redirect`, `headers`, `cache`.
- Use `$client` / `$server` inside `vite` for environment-specific Vite options.

DON'T
- Don't put non-serializable values (functions, `Map`, `Set`) in `runtimeConfig` or anything serialized into Nitro — use a plugin instead.
- Don't rename `srcDir` to fight v4; adopt `app/`. Only override `dir`/`srcDir` for legacy layouts.

```ts
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  modules: ['@nuxt/image', '@pinia/nuxt'],
  routeRules: {
    '/blog/**': { isr: true },
    '/admin/**': { ssr: false },
    '/old': { redirect: '/new' },
  },
  $production: { routeRules: { '/**': { isr: true } } },
})
```

### runtimeConfig & env

Private keys = server-only; keys under `public` reach the client. Read with `useRuntimeConfig()` (pass `event` in server routes: `useRuntimeConfig(event)`).

DO
- Declare every runtime value in `nuxt.config` first — env vars only override **already-declared** keys (prevents leaks).
- Override at runtime with `NUXT_` (private) / `NUXT_PUBLIC_` (public), uppercased, `_` between key segments: `apiSecret` → `NUXT_API_SECRET`; `public.apiBase` → `NUXT_PUBLIC_API_BASE`.
- Type it by augmenting `nuxt/schema` (`RuntimeConfig`, `PublicRuntimeConfig`).

DON'T
- Don't rely on `myVar: process.env.OTHER_NAME` — that binds at **build time only** and breaks at runtime. Match env names to the config shape instead.
- Don't expect the built server to read `.env` — the CLI reads `.env` only in **dev/build/generate**. Provide real env vars in production.
- Don't render private keys into HTML or `useState` — they'll ship to the client.

```ts
runtimeConfig: {
  apiSecret: '',                 // server-only; set via NUXT_API_SECRET
  public: { apiBase: '/api' },   // client+server; NUXT_PUBLIC_API_BASE
}
```

**`app.config.ts` vs `runtimeConfig`:** use `app.config.ts` (`defineAppConfig`, read via `useAppConfig()`) for **public, build-time, reactive** values (theming, feature flags) — HMR-updatable, **cannot** be overridden by env. Use `runtimeConfig` for secrets and anything set per-deploy via env.

### Auto-imports

Auto-imported without `import`: your `components/`, `composables/`, `utils/`, server-side `server/utils/`, plus Vue APIs (`ref`, `computed`, lifecycle) and Nuxt built-ins (`useFetch`, `useState`, `useRuntimeConfig`, `navigateTo`…).

DO
- Drop composables in `app/composables/` and helpers in `app/utils/` — top-level exports are picked up. Add extra dirs via `imports: { dirs: ['stores'] }`.
- Make an import explicit when needed: `import { ref } from '#imports'`.
- Call Nuxt/Vue composables **synchronously** inside setup, a plugin, or route middleware. "Nuxt instance is unavailable" = wrong context.
- Auto-import third-party symbols via `imports.presets` (e.g. `useI18n` from `vue-i18n`).

DON'T
- Don't expect deep-nested exports to auto-import — only top-level files in scanned dirs.
- Don't set `imports.autoImport: false` (kills all composable/util auto-imports) or `imports.scan: false` (breaks layer overrides) unless you know the tradeoff; `#imports` still works when disabled.
- Remember: auto-imported `ref`/`computed` are **not** unwrapped in `<template>` when not top-level to it.

### Components

Auto-registered from `components/`; nested paths get a prefix (`components/base/Button.vue` → `<BaseButton>`). `components/global/` → truly global.

DO
- Disable prefixing per-dir with `pathPrefix: false` for flat names.
- Add `{ path: '~/components/global', global: true }` for globally available components.

DON'T
- Don't disable component auto-import with `components: { dirs: [] }` unless intended — it won't remove module-provided components anyway.

```ts
components: [{ path: '~/components', pathPrefix: false }]
```

### Modules

DO
- Install with `npx nuxi module add <name>` (installs + edits config) or add to `modules[]` manually. Order matters — later modules override earlier.
- Author with `defineNuxtModule` from `@nuxt/kit`: set `meta` (`name`, `configKey`, `compatibility`), `defaults`, and `setup(options, nuxt)`.
- In `setup`, use kit helpers: `addComponent`, `addImports`/`addImportsDir`, `addPlugin`, `addServerHandler`, `extendPages`, `installModule` (for module deps), and `nuxt.hook(...)` for lifecycle.

DON'T
- Don't reorder modules blindly — a module that extends another must run after it.
- Don't reach into Nuxt internals from a module; go through `@nuxt/kit`.

```ts
export default defineNuxtModule({
  meta: { name: 'my-mod', configKey: 'myMod' },
  defaults: { enabled: true },
  setup(options, nuxt) { if (options.enabled) addPlugin(resolve('./runtime/plugin')) },
})
```

### Deploy (Nitro presets)

Nitro is the deploy engine. Preset is **auto-detected** in CI (Vercel, Netlify, Cloudflare, AWS Amplify, Azure, Firebase App Hosting, and more); falls back to **`node-server`**.

DO
- Force a target with `nitro: { preset: '...' }`, or `NITRO_PRESET=... nuxt build` (also `SERVER_PRESET` / `--preset`) — env approach is best for CI.
- **Node server:** `nuxt build` → run `node .output/server/index.mjs` with `NODE_ENV=production`. Tune with `NITRO_PORT`/`PORT`, `NITRO_HOST`/`HOST`, `NITRO_SSL_CERT`/`NITRO_SSL_KEY`. Use `node_cluster` for multi-process.
- **Static/SSG:** `nuxt generate` (keeps `ssr: true`, prerenders + emits `200.html`/`404.html` fallbacks). For prerendering select routes, add fallbacks explicitly via `routeRules`.
- **SPA:** `ssr: false` for a client-only shell; prefer wrapping only interactive parts in `<ClientOnly>` to keep SEO.

DON'T
- Don't ship `ssr: false` when you need SEO — you lose server-rendered HTML.
- Don't assume the host uses the same SPA fallback (`200.html` vs `404.html`) — check the provider's rewrite settings.
- Behind Cloudflare, disable "Rocket Loader" and "Email Address Obfuscation" — injected scripts cause hydration errors.

### Sources
- https://nuxt.com/docs/api/nuxt-config
- https://nuxt.com/docs/guide/concepts/auto-imports
- https://nuxt.com/docs/guide/going-further/runtime-config
- https://nuxt.com/docs/guide/going-further/modules
- https://nuxt.com/docs/getting-started/deployment
- https://nuxt.com/docs/getting-started/upgrade
- https://nuxt.com/blog/v4
- https://nitro.build/deploy
- context7 `/nuxt/nuxt` (nuxt-config, components, environment overrides)
