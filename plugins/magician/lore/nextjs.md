# Next.js — core

Version cue: Next 16 current; App Router stable since 13.4. Assume App Router + React 19 (Actions, `use`, RSC) unless Pages Router (`pages/`) is present.

DO default to Server Components; add `"use client"` only for interactivity (state, effects, event handlers, browser APIs).
DON'T import server-only code (db, secrets, `fs`) into a `"use client"` module.
DO `await` request APIs — `cookies()`, `headers()`, `draftMode()`, and `params`/`searchParams` props are async (Next 15+).
DO fetch in Server Components; stream via `<Suspense>`. DON'T fetch client-side when the server can.
DO mutate with Server Actions (`"use server"`, stable 14); refresh via `revalidatePath`/`revalidateTag`.
DON'T assume caching: `fetch` and GET Route Handlers are uncached by default (Next 15). Opt in: `fetch(url,{cache:'force-cache'})` or `export const dynamic='force-static'`.
DON'T call `cookies()`/`headers()` inside a `"use cache"` scope — read outside, pass as args.
DO use `next/link`, `next/image`, `next/font` + Metadata API; DON'T use `<a>`/`<img>`/`next/head` in App Router.
DO keep secrets server-only; only `NEXT_PUBLIC_*` env reaches the client.
`use cache`: experimental in 15, enabled via `cacheComponents:true` in 16.

Commands: `next dev` · `next build` · `next start` · `next info` (no `next lint` — removed in 16; use ESLint/Biome)

Deep dive when writing non-trivial nextjs — read lore/nextjs/{app-router-and-rsc,rendering-and-caching,data-and-server-actions,routing-and-config}.md

Sources: nextjs.org/docs, /docs/app (routing · caching · upgrading · use-cache)
