# tailwind — v3 vs v4 & configuration

Utility-first CSS. Framework-agnostic (React/Vue/Svelte/Angular/Astro/plain HTML) — it scans class strings, not components. This file covers the v3→v4 split and config. Assume JS/TS + framework lore live elsewhere.

**v4.0 shipped 2025-01-22; current line is v4.x.** v4 is a ground-up rewrite (Rust engine, internally codenamed "Oxide"; official docs just say "new high-performance engine"). The headline change is CSS-first config: no `tailwind.config.js` by default.

## DO — detect the major before touching anything

- Read `package.json`. `"tailwindcss": "^4"` → v4. `"^3"` → v3.
- v4 tell: `@import "tailwindcss";` in CSS + `@tailwindcss/postcss` or `@tailwindcss/vite` in deps. No `tailwind.config.js` required.
- v3 tell: `@tailwind base/components/utilities;` directives + `tailwind.config.js` with a `content` array + `tailwindcss` used directly as the PostCSS plugin.
- Match the installed major exactly. v4 syntax silently no-ops or errors on v3 and vice versa.

## DON'T

- DON'T add `tailwind.config.js` to a v4 project reflexively. v4 configures in CSS via `@theme`.
- DON'T assume `tailwind.config.js` is auto-loaded in v4 — it is not. See `@config` below.
- DON'T pair v4 with Sass/Less/Stylus. **Preprocessors are unsupported in v4** (v4 already does imports, nesting, vendor prefixing via Lightning CSS).

## DO — v4 setup

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

## DO — v4 theming with `@theme`

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

## DO — keep a JS config in v4 (escape hatch)

```css
@config "../../tailwind.config.js";   /* opt back into JS config */
@plugin "@tailwindcss/typography";    /* load a JS plugin */
```
- `@config` is NOT auto-detected — you must add it.
- Unsupported in JS config under v4: `corePlugins`, `safelist`, `separator`. `resolveConfig` is removed (read CSS vars instead).
- Custom utilities: v3 `@layer utilities { .tab-4 {...} }` → v4 `@utility tab-4 { tab-size: 4; }`.

## DO — run the codemod, then fix by hand

```bash
npx @tailwindcss/upgrade   # needs Node 20+; run on a fresh branch, review diff
```
It rewrites imports, config, and most renamed classes. Verify visually — it won't catch dynamically built class strings.

## DON'T — miss the renamed/removed utilities (v3 → v4)

Scale shift (bare name got a `-sm`, old `-sm` became `-xs`):
- `shadow` → `shadow-sm`, `shadow-sm` → `shadow-xs` (same for `drop-shadow`, `blur`, `backdrop-blur`, `rounded`).
- `outline-none` → `outline-hidden`; `ring` → `ring-3` (default ring width went 3px→1px, color went blue-500→currentColor).

Removed opacity utilities — use the `/` modifier:
- `bg-opacity-50` → `bg-black/50`; same for `text-`, `border-`, `divide-`, `ring-`, `placeholder-opacity-*`.

Renamed:
- `flex-shrink-*`→`shrink-*`, `flex-grow-*`→`grow-*`, `overflow-ellipsis`→`text-ellipsis`, `bg-gradient-*`→`bg-linear-*`.

## DON'T — get bitten by v4 syntax/behavior changes

- Important modifier moved to the end: `!flex` → `flex!`.
- CSS-var arbitrary values use parens: `bg-[--brand]` → `bg-(--brand)`.
- Arbitrary multi-value uses underscores not commas: `grid-cols-[max-content,auto]` → `grid-cols-[max-content_auto]`.
- Variant stacking flipped to left→right: `first:*:pt-0` → `*:first:pt-0`.
- Default `border-*`/`divide-*` color is now `currentColor` (was `gray-200`) — set explicit colors or restore in `@layer base`.
- `hover:` now gated behind `@media (hover: hover)` (won't fire on touch); buttons default to `cursor: default`.
- `@apply` in Vue/Svelte `<style>` or CSS Modules needs `@reference "../app.css";` first (scoped blocks lack theme access).

## DO — respect browser floor

v4 requires **Safari 16.4+, Chrome 111+, Firefox 128+** (uses `@property`, `color-mix()`, cascade layers). Need older support → stay on v3.4 and keep `tailwind.config.js` + `@tailwind` directives.

## Sources

- https://tailwindcss.com/blog/tailwindcss-v4
- https://tailwindcss.com/docs/upgrade-guide
- https://tailwindcss.com/docs/installation/using-vite
- https://tailwindcss.com/docs/theme
