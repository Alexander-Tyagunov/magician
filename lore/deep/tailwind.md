# tailwind — deep dive

> On-demand companion to `lore/tailwind.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [v3 vs v4 & configuration](#v3-vs-v4-and-config) · [Utility patterns & pitfalls](#utility-patterns)

## v3 vs v4 & configuration <a id="v3-vs-v4-and-config"></a>

Utility-first CSS. Framework-agnostic (React/Vue/Svelte/Angular/Astro/plain HTML) — it scans class strings, not components. This file covers the v3→v4 split and config. Assume JS/TS + framework lore live elsewhere.

**v4.0 shipped 2025-01-22; current line is v4.x.** v4 is a ground-up rewrite (Rust engine, internally codenamed "Oxide"; official docs just say "new high-performance engine"). The headline change is CSS-first config: no `tailwind.config.js` by default.

### DO — detect the major before touching anything

- Read `package.json`. `"tailwindcss": "^4"` → v4. `"^3"` → v3.
- v4 tell: `@import "tailwindcss";` in CSS + `@tailwindcss/postcss` or `@tailwindcss/vite` in deps. No `tailwind.config.js` required.
- v3 tell: `@tailwind base/components/utilities;` directives + `tailwind.config.js` with a `content` array + `tailwindcss` used directly as the PostCSS plugin.
- Match the installed major exactly. v4 syntax silently no-ops or errors on v3 and vice versa.

### DON'T

- DON'T add `tailwind.config.js` to a v4 project reflexively. v4 configures in CSS via `@theme`.
- DON'T assume `tailwind.config.js` is auto-loaded in v4 — it is not. See `@config` below.
- DON'T pair v4 with Sass/Less/Stylus. **Preprocessors are unsupported in v4** (v4 already does imports, nesting, vendor prefixing via Lightning CSS).

### DO — v4 setup

Vite (preferred):
```ts
// vite.config.ts
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({ plugins: [tailwindcss()] })
```
```css
/* app.css */
@import "tailwindcss";
```
```bash
npm install tailwindcss @tailwindcss/vite
```

PostCSS (when not on Vite):
```js
// postcss.config.mjs
export default { plugins: { "@tailwindcss/postcss": {} } }
```
- CLI is now `npx @tailwindcss/cli`, not `npx tailwindcss`.
- Remove `postcss-import` and `autoprefixer` — both are built in.
- Content detection is **automatic** in v4 (no `content` globs). It honors `.gitignore` and skips binaries. Add missed sources with `@source "../node_modules/@acme/ui";`.

### DO — v4 theming with `@theme`

`@theme` defines CSS variables **that also generate utilities**. Use `:root` for plain variables that should NOT produce utilities.
```css
@import "tailwindcss";
@theme {
  --color-brand-500: oklch(0.72 0.11 178); /* -> bg-brand-500, text-brand-500 */
  --font-display: "Satoshi", sans-serif;    /* -> font-display */
  --breakpoint-3xl: 1920px;                  /* -> 3xl: variant */
  --spacing: 0.25rem;                        /* base spacing unit */
}
```
- Namespaces drive which utilities exist: `--color-*`, `--font-*`, `--text-*`, `--font-weight-*`, `--tracking-*`, `--leading-*`, `--breakpoint-*`, `--container-*`, `--spacing-*`, `--radius-*`, `--shadow-*`, `--drop-shadow-*`, `--blur-*`, `--ease-*`, `--animate-*`, `--aspect-*`.
- Tokens emit as real CSS custom properties on `:root` — reference with `var(--color-brand-500)` anywhere.
- `@theme inline { --font-sans: var(--font-inter); }` — use `inline` when a token references another variable (e.g. a Next.js font var), else it resolves wrong.
- Override a default by redefining it; reset a namespace with `--color-*: initial;`; nuke all defaults with `--*: initial;`.
- `theme()` fn is superseded by `var()`: `theme(colors.red.500)` → `var(--color-red-500)`.

### DO — keep a JS config in v4 (escape hatch)

```css
@config "../../tailwind.config.js";   /* opt back into JS config */
@plugin "@tailwindcss/typography";    /* load a JS plugin */
```
- `@config` is NOT auto-detected — you must add it.
- Unsupported in JS config under v4: `corePlugins`, `safelist`, `separator`. `resolveConfig` is removed (read CSS vars instead).
- Custom utilities: v3 `@layer utilities { .tab-4 {...} }` → v4 `@utility tab-4 { tab-size: 4; }`.

### DO — run the codemod, then fix by hand

```bash
npx @tailwindcss/upgrade   # needs Node 20+; run on a fresh branch, review diff
```
It rewrites imports, config, and most renamed classes. Verify visually — it won't catch dynamically built class strings.

### DON'T — miss the renamed/removed utilities (v3 → v4)

Scale shift (bare name got a `-sm`, old `-sm` became `-xs`):
- `shadow` → `shadow-sm`, `shadow-sm` → `shadow-xs` (same for `drop-shadow`, `blur`, `backdrop-blur`, `rounded`).
- `outline-none` → `outline-hidden`; `ring` → `ring-3` (default ring width went 3px→1px, color went blue-500→currentColor).

Removed opacity utilities — use the `/` modifier:
- `bg-opacity-50` → `bg-black/50`; same for `text-`, `border-`, `divide-`, `ring-`, `placeholder-opacity-*`.

Renamed:
- `flex-shrink-*`→`shrink-*`, `flex-grow-*`→`grow-*`, `overflow-ellipsis`→`text-ellipsis`, `bg-gradient-*`→`bg-linear-*`.

### DON'T — get bitten by v4 syntax/behavior changes

- Important modifier moved to the end: `!flex` → `flex!`.
- CSS-var arbitrary values use parens: `bg-[--brand]` → `bg-(--brand)`.
- Arbitrary multi-value uses underscores not commas: `grid-cols-[max-content,auto]` → `grid-cols-[max-content_auto]`.
- Variant stacking flipped to left→right: `first:*:pt-0` → `*:first:pt-0`.
- Default `border-*`/`divide-*` color is now `currentColor` (was `gray-200`) — set explicit colors or restore in `@layer base`.
- `hover:` now gated behind `@media (hover: hover)` (won't fire on touch); buttons default to `cursor: default`.
- `@apply` in Vue/Svelte `<style>` or CSS Modules needs `@reference "../app.css";` first (scoped blocks lack theme access).

### DO — respect browser floor

v4 requires **Safari 16.4+, Chrome 111+, Firefox 128+** (uses `@property`, `color-mix()`, cascade layers). Need older support → stay on v3.4 and keep `tailwind.config.js` + `@tailwind` directives.

### Sources

- https://tailwindcss.com/blog/tailwindcss-v4
- https://tailwindcss.com/docs/upgrade-guide
- https://tailwindcss.com/docs/installation/using-vite
- https://tailwindcss.com/docs/theme

## Utility patterns & pitfalls <a id="utility-patterns"></a>

Framework-agnostic utility CSS (React/Vue/Svelte/Angular/plain HTML). Assume JS/TS + framework lore live elsewhere — this is STYLING only. Verify version facts before asserting; v4.0 shipped 2025-01-22, v4.1 shipped 2025-04-03.

### Version at a glance
- **v4** (current): CSS-first. `@import "tailwindcss";` + `@theme {}` in CSS. New engine (Rust/Lightning CSS), auto content detection, `oklch` palette, container queries built-in. Requires Safari 16.4+/Chrome 111+/Firefox 128+.
- **v3** (prior): JS-first. `tailwind.config.js` + `@tailwind base/components/utilities;`. Use v3.4 for legacy browsers.

### Utility-first mindset
DO
- Compose single-purpose classes in markup: `class="mx-auto flex max-w-sm items-center gap-4 rounded-xl p-6 shadow-lg"`.
- Prefer utilities over inline `style=` — you get design constraints, state variants, and media queries that inline styles can't express.
- Kill duplication in this order: **(1) loop** the markup (class list authored once), **(2) multi-cursor** edit local repeats, **(3) extract a component/partial**, **(4) custom CSS** only as last resort.

DON'T
- Reach for `@apply` to "clean up" markup. It reintroduces the naming/indirection problem Tailwind exists to remove. It's a fallback, not a pattern.
- Add conflicting classes (`class="grid flex"`). Winner is source order in the *generated* stylesheet, NOT attribute order — unpredictable. Pick one conditionally: `class={cond ? "grid" : "flex"}`.

### Responsive & state variants
DO
- Mobile-first: unprefixed = all sizes; `sm: md: lg: xl: 2xl:` = **min-width and up**. `md:flex` means flex at ≥ md, not "only md".
- Stack variants freely: `dark:md:hover:bg-slate-700`, `group-hover:`, `peer-checked:`, `focus-visible:`, `disabled:`, `aria-*:`, `data-*:`.
- v4 stacks variants **left-to-right**: `*:first:pt-0` (v3 was right-to-left: `first:*:pt-0`).

DON'T
- Assume `sm:` = "small screens only" — it's a floor. Use `max-sm:` / `max-md:` for capped ranges.
- Rely on hover on touch in v4: `hover:` is gated behind `@media (hover:hover)`. Restore old behavior with `@custom-variant hover (&:hover);` if truly needed.

### Dark mode
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

### @apply — sparingly
DO
- Use only for tiny, genuinely-reused primitives (`.btn`) or third-party markup you can't touch. Prefer plain CSS with theme vars: `color: var(--color-violet-500)` over `@apply text-violet-500` (faster, no indirection).
- v4 in scoped/separately-bundled stylesheets (Vue/Svelte `<style>`, CSS Modules): `@apply` and `theme()` see nothing unless you add `@reference "../app.css";` at the top of that block. Better: use the CSS var directly and skip `@reference`.

DON'T
- Build a component library out of `@apply` — you've rebuilt Bootstrap and lost Tailwind's advantages.

### Arbitrary values & custom utilities
DO
- One-offs in brackets: `bg-[#316ff6]`, `grid-cols-[24rem_2.5rem_minmax(0,1fr)]`, `max-h-[calc(100dvh-4rem)]`.
- Spaces → underscores inside brackets: v4 `grid-cols-[max-content_auto]` (v3 allowed commas: `[max-content,auto]`).
- Reference a CSS var with **parens** in v4: `bg-(--brand)` (v3 was `bg-[--brand]`).
- v4 custom utility: `@utility tab-4 { tab-size: 4; }` (v3 was `@layer utilities { .tab-4 {...} }`).
- v4 many utilities are now dynamic without config: `grid-cols-15`, `w-17`, `mt-29`.

DON'T
- Overuse arbitrary values — they bypass the system. If a value recurs, add a token in `@theme`.

### Avoiding class soup (JSX/Vue/Svelte)
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

### Config, build & purge/JIT
DO (v4)
- Configure in CSS: `@theme { --color-brand: oklch(...); --breakpoint-3xl: 120rem; --font-display: "Satoshi"; }`. Tokens become real CSS vars on `:root`.
- Content is auto-detected (respects `.gitignore`, skips binaries). Widen with `@source "../packages/ui";`; safelist dynamic classes with v4.1 `@source inline("bg-red-500");`.
- Pick a plugin: `@tailwindcss/vite` (best) or `@tailwindcss/postcss`. CLI is now `@tailwindcss/cli`. `postcss-import` and `autoprefixer` are built in — remove them.
- Keep a JS config only for back-compat: `@config "../tailwind.config.js";` (loses `corePlugins`, `safelist`, `separator`).

DON'T
- Write class names via string interpolation (`text-${color}-500`) — the scanner can't see them, so they get purged. Map full class names instead. This is the #1 "missing styles in prod" bug in both v3 and v4.
- Use Sass/Less with v4 — unsupported; Tailwind *is* the preprocessor. Nesting/imports/vars are native.
- Expect `resolveConfig`/`corePlugins`/JS `theme()` in v4 — removed; read generated CSS vars instead.

### Plugins
DO
- Official plugins still ship: `@tailwindcss/typography` (`prose`), `@tailwindcss/forms`. Load in v4 CSS via `@plugin "@tailwindcss/typography";`.
- Container queries are **core** in v4 (`@container`, `@sm:`, `@max-md:`) — drop `@tailwindcss/container-queries`. Same for the old 3D/aspect plugins now built in.

DON'T
- Install community plugins for things v4 absorbed (container queries, aspect-ratio).

### v3 → v4 migration checklist
- Run `npx @tailwindcss/upgrade` (Node 20+) on a branch; review diff.
- `@tailwind` directives → `@import "tailwindcss";`.
- Renamed scale defaults: `shadow`→`shadow-sm`, `shadow-sm`→`shadow-xs`, `rounded`→`rounded-sm`, `blur`→`blur-sm`, `outline-none`→`outline-hidden`, `ring`→`ring-3` (default ring is now 1px `currentColor`, not 3px `blue-500`).
- Removed: `bg-opacity-*` → `bg-black/50`; `flex-shrink-*`→`shrink-*`, `flex-grow-*`→`grow-*`; `bg-gradient-*`→`bg-linear-*`.
- Important modifier moved to the **end**: `!flex` → `flex!`.
- Default border/divide color changed `gray-200` → `currentColor` — set colors explicitly.
- `transform-none` no longer resets individual `rotate/scale/translate` (now native props); use `scale-none` etc.

### Sources
- https://tailwindcss.com/blog/tailwindcss-v4
- https://tailwindcss.com/blog/tailwindcss-v4-1
- https://tailwindcss.com/docs/upgrade-guide
- https://tailwindcss.com/docs/dark-mode
- https://tailwindcss.com/docs/styling-with-utility-classes
- https://tailwindcss.com/docs/installation
