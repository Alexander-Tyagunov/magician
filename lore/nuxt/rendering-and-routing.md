# nuxt — Rendering & routing

Scope: Nuxt 3 & 4 (current stable v4.4.x). Universal (SSR) default, file-based
routing, layouts, route middleware, hybrid rendering (`routeRules`), server
components / islands. Nuxt builds on **vue-router** + Nitro. Verify version
before asserting: `nuxt info` / `package.json`.

## Version map (read first)

- **Nuxt 4** default `srcDir` is `app/` → `~` and `@` point to `app/`. Dirs live
  at `app/pages`, `app/layouts`, `app/components`, `app/middleware`. `serverDir`
  is `<rootDir>/server`; `modules/`, `public/`, `layers/` resolve from `<rootDir>`.
  New `shared/` dir for code shared by Vue app + Nitro.
- **Nuxt 3** keeps these at project root (`pages/`, `layouts/`, `server/`).
- Nuxt 4 auto-detects the old layout; force v3 style with `srcDir: '.'`.
- `future.compatibilityVersion: 5` (v4.2+) opts into Nuxt 5 behaviors early.
- DO write paths version-adaptively: prefer `app/pages/…` for v4, `pages/…` for v3.

## Rendering modes

- DO leave **universal rendering (SSR)** on — it is the default (`ssr: true`).
  Server returns full HTML, client hydrates. Best for SEO, marketing, e-commerce.
- DO set `ssr: false` for pure SPA / back-office / gated dashboards; add
  `app/spa-loading-template.html` (v4) / `~/spa-loading-template.html` to avoid a
  blank screen.
- DON'T assume ESR is a separate mode — "edge-side rendering" is just SSR via
  Nitro deployed to a CDN edge (Cloudflare/Vercel/Netlify). It's a deploy target.
- DON'T reach for hybrid rendering under full static `nuxt generate` — route
  rules for caching are a Nitro-server concern.

## Hybrid rendering — `routeRules`

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

## File-based routing (`pages/`)

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

## Navigation

- DO link with `<NuxtLink>` (auto-imported) — SPA transitions after hydration,
  auto-prefetch on viewport entry.
- DO navigate programmatically with `navigateTo(...)` and `await` / `return` it.
- DO read route state with `useRoute()` in `<script setup>`; use `useRouter()`
  for imperative control.
- DON'T mutate `route.params` — treat route as read-only.

## `definePageMeta`

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

## Route middleware

- DO define with `defineNuxtRouteMiddleware((to, from) => {…})`. Return
  `navigateTo(...)`, `abortNavigation(...)`, or nothing.
- Three kinds: inline (in the page), **named** (`app/middleware/auth.ts`, applied
  via `definePageMeta`), **global** (`app/middleware/*.global.ts`, every nav).
- Names kebab-case: `someMiddleware` → `some-middleware`.
- DON'T expect route middleware to run for `/api/*` (Nitro) routes — use server
  middleware. It also does **not** run when rendering islands.
- Nuxt 4: `app/middleware/*/index.ts` subfolders are now scanned.

## Layouts

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

## Server components & islands (experimental)

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

## Sources

- https://nuxt.com/docs/getting-started/views
- https://nuxt.com/docs/getting-started/routing
- https://nuxt.com/docs/guide/concepts/rendering
- https://nuxt.com/docs/guide/directory-structure/pages
- https://nuxt.com/docs/guide/directory-structure/layouts
- https://nuxt.com/docs/guide/directory-structure/components
- https://nuxt.com/docs/getting-started/upgrade
