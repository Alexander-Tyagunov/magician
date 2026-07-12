# tailwind — Utility patterns & pitfalls

Framework-agnostic utility CSS (React/Vue/Svelte/Angular/plain HTML). Assume JS/TS + framework lore live elsewhere — this is STYLING only. Verify version facts before asserting; v4.0 shipped 2025-01-22, v4.1 shipped 2025-04-03.

## Version at a glance
- **v4** (current): CSS-first. `@import "tailwindcss";` + `@theme {}` in CSS. New engine (Rust/Lightning CSS), auto content detection, `oklch` palette, container queries built-in. Requires Safari 16.4+/Chrome 111+/Firefox 128+.
- **v3** (prior): JS-first. `tailwind.config.js` + `@tailwind base/components/utilities;`. Use v3.4 for legacy browsers.

## Utility-first mindset
DO
- Compose single-purpose classes in markup: `class="mx-auto flex max-w-sm items-center gap-4 rounded-xl p-6 shadow-lg"`.
- Prefer utilities over inline `style=` — you get design constraints, state variants, and media queries that inline styles can't express.
- Kill duplication in this order: **(1) loop** the markup (class list authored once), **(2) multi-cursor** edit local repeats, **(3) extract a component/partial**, **(4) custom CSS** only as last resort.

DON'T
- Reach for `@apply` to "clean up" markup. It reintroduces the naming/indirection problem Tailwind exists to remove. It's a fallback, not a pattern.
- Add conflicting classes (`class="grid flex"`). Winner is source order in the *generated* stylesheet, NOT attribute order — unpredictable. Pick one conditionally: `class={cond ? "grid" : "flex"}`.

## Responsive & state variants
DO
- Mobile-first: unprefixed = all sizes; `sm: md: lg: xl: 2xl:` = **min-width and up**. `md:flex` means flex at ≥ md, not "only md".
- Stack variants freely: `dark:md:hover:bg-slate-700`, `group-hover:`, `peer-checked:`, `focus-visible:`, `disabled:`, `aria-*:`, `data-*:`.
- v4 stacks variants **left-to-right**: `*:first:pt-0` (v3 was right-to-left: `first:*:pt-0`).

DON'T
- Assume `sm:` = "small screens only" — it's a floor. Use `max-sm:` / `max-md:` for capped ranges.
- Rely on hover on touch in v4: `hover:` is gated behind `@media (hover:hover)`. Restore old behavior with `@custom-variant hover (&:hover);` if truly needed.

## Dark mode
DO (v4)
- Default `dark:` follows `prefers-color-scheme` — zero config.
- Class/attribute toggle: override the variant in CSS.
```css
@import "tailwindcss";
@custom-variant dark (&:where(.dark, .dark *));
/* or attribute: */
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
```
- Set an inline `<head>` script that toggles `.dark` before paint to avoid FOUC.

DON'T
- Look for `darkMode: 'class'` in v4 — the JS `darkMode` option is gone; it's `@custom-variant dark` in CSS. (v3: `darkMode: 'class' | 'media' | ['selector', '[data-theme=dark]']`.)

## @apply — sparingly
DO
- Use only for tiny, genuinely-reused primitives (`.btn`) or third-party markup you can't touch. Prefer plain CSS with theme vars: `color: var(--color-violet-500)` over `@apply text-violet-500` (faster, no indirection).
- v4 in scoped/separately-bundled stylesheets (Vue/Svelte `<style>`, CSS Modules): `@apply` and `theme()` see nothing unless you add `@reference "../app.css";` at the top of that block. Better: use the CSS var directly and skip `@reference`.

DON'T
- Build a component library out of `@apply` — you've rebuilt Bootstrap and lost Tailwind's advantages.

## Arbitrary values & custom utilities
DO
- One-offs in brackets: `bg-[#316ff6]`, `grid-cols-[24rem_2.5rem_minmax(0,1fr)]`, `max-h-[calc(100dvh-4rem)]`.
- Spaces → underscores inside brackets: v4 `grid-cols-[max-content_auto]` (v3 allowed commas: `[max-content,auto]`).
- Reference a CSS var with **parens** in v4: `bg-(--brand)` (v3 was `bg-[--brand]`).
- v4 custom utility: `@utility tab-4 { tab-size: 4; }` (v3 was `@layer utilities { .tab-4 {...} }`).
- v4 many utilities are now dynamic without config: `grid-cols-15`, `w-17`, `mt-29`.

DON'T
- Overuse arbitrary values — they bypass the system. If a value recurs, add a token in `@theme`.

## Avoiding class soup (JSX/Vue/Svelte)
DO
- Extract to a component/partial with a single source of truth (works in any framework).
- Merge conditional + conflicting classes at runtime with **`clsx`** (conditional join) + **`tailwind-merge`** (`twMerge` dedupes conflicts so the last wins). Common combo:
```ts
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
export const cn = (...a) => twMerge(clsx(a)); // used by shadcn/ui, CVA
```
- Use **CVA** (`class-variance-authority`) for variant→class maps on reusable components.

DON'T
- Let consumers spread arbitrary `className` onto internal elements without `twMerge` — order-of-generation wins, so raw concatenation produces flaky overrides.
- Confuse these libs with Tailwind: they are runtime JS helpers, not part of Tailwind core.

## Config, build & purge/JIT
DO (v4)
- Configure in CSS: `@theme { --color-brand: oklch(...); --breakpoint-3xl: 120rem; --font-display: "Satoshi"; }`. Tokens become real CSS vars on `:root`.
- Content is auto-detected (respects `.gitignore`, skips binaries). Widen with `@source "../packages/ui";`; safelist dynamic classes with v4.1 `@source inline("bg-red-500");`.
- Pick a plugin: `@tailwindcss/vite` (best) or `@tailwindcss/postcss`. CLI is now `@tailwindcss/cli`. `postcss-import` and `autoprefixer` are built in — remove them.
- Keep a JS config only for back-compat: `@config "../tailwind.config.js";` (loses `corePlugins`, `safelist`, `separator`).

DON'T
- Write class names via string interpolation (`text-${color}-500`) — the scanner can't see them, so they get purged. Map full class names instead. This is the #1 "missing styles in prod" bug in both v3 and v4.
- Use Sass/Less with v4 — unsupported; Tailwind *is* the preprocessor. Nesting/imports/vars are native.
- Expect `resolveConfig`/`corePlugins`/JS `theme()` in v4 — removed; read generated CSS vars instead.

## Plugins
DO
- Official plugins still ship: `@tailwindcss/typography` (`prose`), `@tailwindcss/forms`. Load in v4 CSS via `@plugin "@tailwindcss/typography";`.
- Container queries are **core** in v4 (`@container`, `@sm:`, `@max-md:`) — drop `@tailwindcss/container-queries`. Same for the old 3D/aspect plugins now built in.

DON'T
- Install community plugins for things v4 absorbed (container queries, aspect-ratio).

## v3 → v4 migration checklist
- Run `npx @tailwindcss/upgrade` (Node 20+) on a branch; review diff.
- `@tailwind` directives → `@import "tailwindcss";`.
- Renamed scale defaults: `shadow`→`shadow-sm`, `shadow-sm`→`shadow-xs`, `rounded`→`rounded-sm`, `blur`→`blur-sm`, `outline-none`→`outline-hidden`, `ring`→`ring-3` (default ring is now 1px `currentColor`, not 3px `blue-500`).
- Removed: `bg-opacity-*` → `bg-black/50`; `flex-shrink-*`→`shrink-*`, `flex-grow-*`→`grow-*`; `bg-gradient-*`→`bg-linear-*`.
- Important modifier moved to the **end**: `!flex` → `flex!`.
- Default border/divide color changed `gray-200` → `currentColor` — set colors explicitly.
- `transform-none` no longer resets individual `rotate/scale/translate` (now native props); use `scale-none` etc.

## Sources
- https://tailwindcss.com/blog/tailwindcss-v4
- https://tailwindcss.com/blog/tailwindcss-v4-1
- https://tailwindcss.com/docs/upgrade-guide
- https://tailwindcss.com/docs/dark-mode
- https://tailwindcss.com/docs/styling-with-utility-classes
- https://tailwindcss.com/docs/installation
