# nextjs — Routing, config & deploy

Scope: App Router file conventions, routing, middleware/proxy, `next.config`, images/fonts, env, output modes. Current stable: **Next.js 16.2.x**. App Router stable since **13.4.0**; Pages Router still supported. Verify against the running project's `next` version before applying version-gated advice.

## App Router file conventions

Special names (extensions `.js|.jsx|.tsx`; `route` is `.js|.ts`):

- `layout` — shared UI wrapping children; persists across nav (no re-render). Root layout required; must render `<html>`/`<body>`.
- `page` — makes a segment routable. Async server component by default.
- `loading` — Suspense boundary (instant loading UI).
- `error` — React error boundary; `'use client'`; receives `{ error, reset }`.
- `global-error` — catches root-layout errors; renders own `<html>`/`<body>`; `'use client'`.
- `not-found` — UI for `notFound()` and unmatched URLs.
- `template` — like layout but re-mounts on navigation (fresh state/effects).
- `route` — Route Handler; export `GET`/`POST`/etc. Cannot share a folder with `page`.
- `default` — fallback for unmatched parallel-route slots.

Render order (outer→inner): `layout` → `template` → `error` → `loading` → `not-found` → `page`.

DO
- Keep one root layout with `<html lang>`/`<body>`; use route groups for multiple root layouts.
- Mark `error.tsx`/`global-error.tsx` `'use client'`.
- Colocate helpers in a segment; they are non-routable until a `page`/`route` exists.

DON'T
- Don't put `page` and `route` in the same folder.
- Don't expect `layout` state to reset on navigation — use `template` for that.

## Segment & folder syntax

- Dynamic: `[slug]` → `params.slug`. Catch-all: `[...slug]` (array). Optional catch-all: `[[...slug]]` (matches parent too).
- `params` and `searchParams` are **Promises** in App Router (await them): `const { slug } = await params`. (Promises since v15; synchronous access was deprecated-with-warning in 15 and removed in 16.)
- Route groups: `(marketing)` — organize without adding a URL segment.
- Private folders: `_components` — opt a folder out of routing entirely.
- Parallel routes: `@slot` — named slots rendered as props by the parent `layout`; pair with `default.tsx`.
- Intercepting routes: `(.)` same level, `(..)` one up, `(..)(..)` two up, `(...)` from app root — e.g. modal over a list.

DO use `generateStaticParams()` to pre-render dynamic routes at build. DON'T rely on intercepting routes in static export (unsupported).

## Middleware → Proxy (v16 rename)

**Breaking in v16.0.0:** the `middleware` file convention is deprecated and renamed to **`proxy`** (`proxy.ts` at project root / `src`, export `proxy` or default). Codemod: `npx @next/codemod@canary middleware-to-proxy .`. On ≤15, use `middleware.ts` with the same `config.matcher` API.

Runtime: Proxy defaults to the **Node.js runtime** in v16 (the `runtime` config option is not allowed in proxy files). Middleware's Node.js runtime went stable in **15.5.0** (experimental 15.2.0); before that it was Edge-only.

```ts
// proxy.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
export function proxy(req: NextRequest) {
  if (!isAuthed(req)) return NextResponse.redirect(new URL('/login', req.url))
  return NextResponse.next()
}
export const config = {
  // exclude static/image/metadata assets
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
```

DO
- Always set a `matcher`; without one it runs on **every** request (including assets) and can block CSS/JS/images.
- Re-check auth **inside** Server Functions/Route Handlers — a matcher gap silently skips them.
- Use `has`/`missing` matcher objects to skip prefetch requests.

DON'T
- Don't rely on shared module state/globals in proxy (may run at the edge/CDN, separate from app runtime).
- Don't set large response headers (431 risk). `_next/data` still runs proxy even if excluded (intentional).

## next.config

Location: `next.config.js|mjs|ts` at project root (`.cjs`/`.cts` unsupported). `next.config.ts` is supported (TS config).

```ts
// next.config.ts
import type { NextConfig } from 'next'
const nextConfig: NextConfig = {
  images: { remotePatterns: [new URL('https://cdn.example.com/**')] },
  // output: 'standalone' | 'export'
}
export default nextConfig
```

Common keys: `basePath`, `assetPrefix`, `redirects()`, `rewrites()`, `headers()`, `trailingSlash`, `transpilePackages`, `serverExternalPackages`, `output`, `turbopack`, `typedRoutes`, `env`. Config may be a function `(phase, { defaultConfig }) => {}` (sync or async since 12.1).

## Images (`next/image`)

Required: `src`, `alt`. Provide `width`+`height`, or `fill` (parent needs `position: relative`; add `sizes`).

- `remotePatterns` (config, required to allow external hosts) — `new URL(...)` shorthand or objects; `**` wildcards (start/end only). `domains` is **deprecated since v14** → migrate.
- `localPatterns` restricts optimizable local paths. `qualities: [...]` gates `quality` prop (default `75`).
- `placeholder="blur"` + `blurDataURL` (auto for static imports); keep it small. `unoptimized` serves as-is.
- `next/image`: `onLoadingComplete` is deprecated — use `onLoad`. SVGs blocked unless `dangerouslyAllowSVG` (prefer `unoptimized` for `.svg`).

DO define `remotePatterns` for every external host. DON'T use `domains`.

## Fonts (`next/font`)

Import from `next/font/google` or `next/font/local` (renamed from `@next/font` in **13.2.0**; no install needed). Self-hosted at build — no runtime requests to Google.

```ts
import { Inter } from 'next/font/google'
const inter = Inter({ subsets: ['latin'], display: 'swap', variable: '--font-inter' })
// <html className={inter.variable}> then font-family: var(--font-inter)
```

DO set `subsets` (warns otherwise when preload on). DO use variable fonts (no `weight` needed). For non-variable fonts, `weight` is required. DON'T call the loader per-render — define once and import (each call = one hosted instance).

## Env vars

- Load order (first wins): `process.env` → `.env.$(NODE_ENV).local` → `.env.local` → `.env.$(NODE_ENV)` → `.env`. `.env.local` skipped when `NODE_ENV=test`.
- `NEXT_PUBLIC_` vars are **inlined at build time** into the client bundle — frozen after build; never for secrets or per-env runtime values. Dynamic lookups (`process.env[varName]`) are **not** inlined.
- Non-prefixed vars stay server-only; read at **runtime** during dynamic rendering (`await connection()`, or after `cookies()`/`headers()`) — enables one image across envs.
- `.env*` files live at project root even with `src/`. Use `@next/env` `loadEnvConfig` to load outside Next (ORM/test config).

## Output modes & deploy

- Default: server build with Output File Tracing (`.nft.json`); needs `next start` + `node_modules`.
- `output: 'standalone'` — emits `.next/standalone` with minimal `server.js` and only required `node_modules`; manually copy `public/` and `.next/static/` (CDN-served, not auto-copied). Ideal for Docker; `PORT`/`HOSTNAME` env respected. Set `outputFileTracingRoot` in monorepos.
- `output: 'export'` — static HTML/CSS/JS into `out/`; SPA-style. `next export` CLI removed in **14.0.0** (use this config).

Static export **unsupported**: Proxy/middleware, `redirects`/`rewrites`/`headers`, ISR, Server Actions, cookies/draft mode, non-`GET` route handlers, intercepting routes, default image loader (need `loader: 'custom'` + `loaderFile`), dynamic routes without `generateStaticParams()` or with `dynamicParams: true`.

## Sources

- https://nextjs.org/docs/app/getting-started/project-structure
- https://nextjs.org/docs/app/api-reference/file-conventions/proxy
- https://nextjs.org/docs/app/api-reference/config/next-config-js
- https://nextjs.org/docs/app/api-reference/config/next-config-js/output
- https://nextjs.org/docs/app/api-reference/components/image
- https://nextjs.org/docs/app/api-reference/components/font
- https://nextjs.org/docs/app/guides/environment-variables
- https://nextjs.org/docs/app/guides/static-exports
