# nuxt — Config, modules & deploy

Current stable: **Nuxt 4.x** (released **2025-07-15**). Nuxt 3 in maintenance until end of Jan 2026. Verify the project's `nuxt` version before writing — directory layout and data-fetching defaults diverge between 3 and 4.

Version anchors:
- **`srcDir` default is `app/`** in Nuxt 4 (was `.`/root in Nuxt 3). App code → `app/`, server → `<rootDir>/server`, new `shared/` dir; `~`/`@` alias → `app/`.
- **`compatibilityDate`** pins date-sensitive behavior of Nitro presets, Nuxt Image, and other modules so they don't shift without a major bump. Set once (`YYYY-MM-DD`).
- **`future.compatibilityVersion: 4`** in Nuxt 3 opted into v4 early; `: 5` opts into Nuxt 5 defaults (in development). v4 behavior is default on v4; a compat fallback keeps old layouts working.
- Data fetching (v4): `data`/`error` default to `undefined` (was `null`); `data` is a `shallowRef`; same-key `useAsyncData`/`useFetch` share one ref.

Config: `nuxt.config.ts` via `defineNuxtConfig({...})`. Modules run **sequentially** in array order — order matters.

## nuxt.config essentials

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

## runtimeConfig & env

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

## Auto-imports

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

## Components

Auto-registered from `components/`; nested paths get a prefix (`components/base/Button.vue` → `<BaseButton>`). `components/global/` → truly global.

DO
- Disable prefixing per-dir with `pathPrefix: false` for flat names.
- Add `{ path: '~/components/global', global: true }` for globally available components.

DON'T
- Don't disable component auto-import with `components: { dirs: [] }` unless intended — it won't remove module-provided components anyway.

```ts
components: [{ path: '~/components', pathPrefix: false }]
```

## Modules

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

## Deploy (Nitro presets)

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

## Sources
- https://nuxt.com/docs/api/nuxt-config
- https://nuxt.com/docs/guide/concepts/auto-imports
- https://nuxt.com/docs/guide/going-further/runtime-config
- https://nuxt.com/docs/guide/going-further/modules
- https://nuxt.com/docs/getting-started/deployment
- https://nuxt.com/docs/getting-started/upgrade
- https://nuxt.com/blog/v4
- https://nitro.build/deploy
- context7 `/nuxt/nuxt` (nuxt-config, components, environment overrides)
