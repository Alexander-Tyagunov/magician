# nextjs — Rendering & caching

App Router (13.4+ stable). Verify the installed major before applying defaults — caching defaults changed across 14 → 15 → 16. Check `next --version` / `package.json`.

## Version cheat-sheet (defaults differ — do not guess)

- **14**: `fetch` **cached** by default (`force-cache`). `GET` route handlers cached by default.
- **15**: `fetch` **uncached** by default. `GET` route handlers uncached by default. Client Router Cache `staleTime` for page segments = **0** (page segments re-fetched on nav). Request APIs (`cookies`, `headers`, `draftMode`, `params`, `searchParams`) became **async** (breaking).
- **16**: adds **Cache Components** (`cacheComponents: true`) — dynamic-by-default, opt-in caching via `use cache`. When enabled, `dynamic`/`dynamicParams`/`revalidate`/`fetchCache` segment configs and `experimental_ppr` are **removed**; PPR is the default behavior.

## DO — dynamic vs static rendering

- DO know: a route is **static** (prerendered at build) unless it reads request-time data. Reading `cookies()`, `headers()`, `draftMode()`, `searchParams`, an uncached/`no-store` `fetch`, or `connection()` opts the route into **dynamic** rendering.
- DO `await` request APIs on 15+: `const c = await cookies()`. Sync access warns in dev, breaks later.
- DO wrap slow/dynamic subtrees in `<Suspense>` to stream them while the static shell ships instantly.
- DO force a mode explicitly (pre-16 / no Cache Components):
  ```ts
  export const dynamic = 'force-static'   // prerender; cookies/headers return empty
  export const dynamic = 'force-dynamic'  // render per request
  export const revalidate = 3600          // ISR: static, re-gen every 3600s
  ```
- DON'T assume 14's "cached by default" on 15+. On 15+ an unadorned `fetch` is dynamic data — a page with one becomes dynamic unless you cache it.

## DO — fetch cache + revalidate/tags

- DO opt into caching on 15+: `fetch(url, { cache: 'force-cache' })`.
- DO time-revalidate (ISR): `fetch(url, { next: { revalidate: 3600 } })` (seconds).
- DO tag for on-demand invalidation: `fetch(url, { next: { tags: ['posts'] } })`.
- DO revalidate from a Server Action / Route Handler:
  ```ts
  import { revalidateTag, revalidatePath } from 'next/cache'
  revalidateTag('posts')
  revalidatePath('/blog')
  ```
- DO cache non-`fetch` work (ORM/DB) with `unstable_cache(fn, keyParts, { tags, revalidate })`.
- DO dedupe per-request DB reads with React `cache()` (memoization within one render). `fetch` is auto-memoized.
- DON'T write `revalidate = 60 * 10` — must be a static literal (`revalidate = 600`). Not available on `runtime = 'edge'`.
- DON'T expect dev caching: pages always render on-demand in `next dev`.

## DO — generateStaticParams + dynamicParams (13.0+)

- DO prerender dynamic segments at build. Return an **array of objects** keyed by segment name:
  ```ts
  export async function generateStaticParams() {
    const posts = await fetch('https://.../posts').then(r => r.json())
    return posts.map(p => ({ slug: p.slug }))   // /blog/[slug]
  }
  ```
  Catch-all `[...slug]` → `{ slug: string[] }[]`. Multi-segment → include every key.
- DO control unlisted paths with `dynamicParams` (default `true`):
  - `true`: unlisted params render on-demand (ISR) at first visit.
  - `false`: unlisted params → 404.
- DO generate a subset at build + rest on-demand: return partial list, keep `dynamicParams = true`.
- DO combine with ISR at runtime for all paths: return `[]` **and** set `export const dynamic = 'force-static'` (empty array alone → dynamic route pre-16).
- DO nest correctly: a page can generate params for its own + ancestor segments (bottom-up), never descendants. Child `generateStaticParams` runs once per parent param.
- DON'T forget: `params` is a **Promise** in the page/layout on 15+ (`const { slug } = await params`), but the arg passed **into** a child `generateStaticParams` is sync (`{ params: { category } }`).
- DON'T call it during ISR revalidation — it runs at build only (and on-nav in dev).
- Cache Components (16): `generateStaticParams` must return **≥1** param; empty array is a build error.

## DO — route segment config (pre-16, or non–Cache-Components)

```ts
export const dynamic = 'auto' | 'force-dynamic' | 'error' | 'force-static'
export const dynamicParams = true            // boolean
export const revalidate = false | 0 | number // false=indefinite, 0=always dynamic
export const fetchCache = 'auto' | 'default-cache' | 'only-cache'
  | 'force-cache' | 'force-no-store' | 'default-no-store' | 'only-no-store'
export const runtime = 'nodejs' | 'edge'
export const maxDuration = 5
```
- `fetchCache = 'default-cache'`: cache `fetch`es lacking an explicit `cache` (opt a whole subtree back to 14-style). `'force-*'` overrides every `fetch`.
- `dynamic = 'error'`: prerender-or-fail — errors if any request API / uncached fetch is used.
- The **lowest** `revalidate` across a route's layouts+page wins for the whole route.
- DON'T set these on 16 with `cacheComponents: true` — they're removed; migrate to `use cache` + `cacheLife`/`cacheTag`.

## DO — GET route handlers

- DO opt a `GET` handler into static caching on 15+: `export const dynamic = 'force-static'`.
- `generateStaticParams` works in `route.ts` to prebuild API responses.

## DO — Partial Prerendering / Cache Components (flag status matters)

- **14 / 15**: PPR is **experimental**. Enable per-project `experimental.ppr` in `next.config`, opt a route in with `export const experimental_ppr = true`. Only on canary/experimental — don't rely on it in stable prod.
- **16**: `experimental.ppr` and `experimental_ppr` are **removed**. Use `cacheComponents: true` — PPR becomes the default rendering model. Verify your version before recommending either flag.
  ```ts
  // next.config.ts (v16)
  const nextConfig = { cacheComponents: true }
  ```
- With Cache Components: data is **dynamic by default**; opt into caching with `'use cache'` on a function/component/page, tune with `cacheLife('hours')` and `cacheTag('posts')`; invalidate with `updateTag`/`revalidateTag`. Wrap runtime-data components in `<Suspense>`; use `connection()` before non-deterministic ops (`Math.random`, `Date.now`, `crypto.randomUUID`).
- DON'T claim PPR is stable/on-by-default on 14/15, and DON'T reference `experimental_ppr` on 16.

## Client Router Cache (15 change)

- On 15+, page segments are **not** reused on `<Link>`/`useRouter` nav (still reused on back/forward and for shared layouts + loading states). Opt back in via `experimental.staleTimes` (`next.config`):
  ```js
  experimental: { staleTimes: { dynamic: 30, static: 180 } }
  ```

## Sources

- https://nextjs.org/docs/app/getting-started/caching
- https://nextjs.org/docs/app/guides/caching-without-cache-components
- https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config
- https://nextjs.org/docs/app/api-reference/functions/generate-static-params
- https://nextjs.org/docs/app/api-reference/config/next-config-js/cacheComponents
- https://nextjs.org/docs/app/guides/upgrading/version-15
