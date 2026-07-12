# Nuxt - core digest

Version cue: Nuxt 4 (stable, Node 22+). Nuxt 3 = same APIs, srcDir was root.

DO auto-import from `app/composables`,`app/components`,`app/utils` - never import by hand.
DO fetch initial/SSR data with `useFetch`/`useAsyncData` - dedupes + ships payload to client, no double fetch.
DON'T bare `fetch`/`$fetch` in setup for SSR - double fetch + hydration mismatch.
DO use `$fetch` only in event handlers/client; DON'T call `useFetch`/`useAsyncData` outside setup or lifecycle.
DO give `useAsyncData`/`useFetch` a stable explicit key; keep `transform`/`pick`/`default`/`deep` consistent per key.
DON'T deep-mutate `data` (Nuxt 4 = shallowRef); replace the ref value.
DO `useState('key', () => v)` for shared state. DON'T module-scope `ref()/reactive()` - server cross-request leak. State must be JSON-serializable.
DO put server routes in `server/api/*` via `defineEventHandler`; secrets via `useRuntimeConfig()`, never inline env client-side.
DO navigate with `navigateTo()`, guard via `defineNuxtRouteMiddleware`, set meta with `definePageMeta`.
Nuxt 4: `srcDir=app/`, `~`=app/, serverDir=`<root>/server`, `shared/` for app+server code; force old layout via `srcDir:'.'`. Removed `dedupe:true/false` - use `'cancel'`/`'defer'`.

Commands: `npm create nuxt@latest`; `nuxt dev`; `nuxt build`; `nuxt generate` (static); `nuxt preview`; `nuxt module add <name>`.

Deep dive when writing non-trivial nuxt — read lore/nuxt/{rendering-and-routing,data-and-state,config-and-modules}.md

## Sources
nuxt.com/docs/4.x: upgrade, data-fetching, state-management, installation, api/commands
