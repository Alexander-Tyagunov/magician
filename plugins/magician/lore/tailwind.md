# Tailwind — core (always-injected)

Framework-agnostic utility CSS (React/Vue/Svelte/Angular/plain). Version cue: v4 (current) = CSS-first `@theme`, Oxide engine, auto content detection, no JS config, `@import "tailwindcss"`. v3 (prior) = `tailwind.config.js` + `@tailwind base/components/utilities`. Migrate: `npx @tailwindcss/upgrade` (Node 20+; Safari 16.4+/Chrome 111+/Firefox 128+).

Commands (v4): `npm i tailwindcss @tailwindcss/vite` + `tailwindcss()` in vite.config (or `@tailwindcss/postcss`). Then `@import "tailwindcss";`.

DO
- v4: theme tokens in CSS `@theme { --color-*/--breakpoint-*/--font-* }` → CSS vars on :root.
- v4: custom utilities via `@utility name {}`; extra scan paths via `@source`.
- v4: opacity `bg-black/50`; arbitrary var `bg-(--brand)`; important suffix `flex!`.
- Keep legacy JS config mid-migration: `@config "../tailwind.config.js"`.
- Vue/Svelte/CSS-module `<style>`: add `@reference "../app.css"` before `@apply`.
- Container queries are core: `@container`+`@sm:` (no plugin).

DON'T
- v4 won't auto-read `tailwind.config.js` (only via `@config`); drop `postcss-import`/`autoprefixer` (built in).
- Removed/renamed: `bg-opacity-*`→`/50`, `flex-shrink`→`shrink`, `shadow`→`shadow-sm`, `ring`→`ring-3`, `outline-none`→`outline-hidden`, `bg-gradient-*`→`bg-linear-*`.
- Default border/ring color is `currentColor` in v4, not gray. Don't lean on `@apply`.

Deep dive when writing non-trivial tailwind — read lore/tailwind/{v3-vs-v4-and-config,utility-patterns}.md

Sources: tailwindcss.com/docs/upgrade-guide, /blog/tailwindcss-v4
