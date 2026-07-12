# vanilla-extract — Zero-runtime CSS-in-TS landscape

Framework-agnostic, build-time CSS. Styles authored in TypeScript (`*.css.ts`), extracted to a static `.css` file at build. Zero style injection at runtime → no runtime cost, works cleanly inside React Server Components (RSC). Contrast: runtime CSS-in-JS (styled-components, Emotion) injects styles from client JS and cannot run in Server Components without `"use client"` boundaries + extra SSR wiring.

Versions (verify at build): `@vanilla-extract/css` 1.21.x, `@vanilla-extract/recipes` 0.5.x (still 0.x — API stable but pre-1.0), `@vanilla-extract/sprinkles` 1.7.x. Integrations: `@vanilla-extract/vite-plugin` 5.x, `@vanilla-extract/next-plugin` 2.5.x, plus webpack/esbuild/rollup/parcel/gatsby/astro plugins. A bundler integration is REQUIRED — VE only emits `.css.ts`; the plugin compiles it.

## DO — vanilla-extract
- Put styles in `*.css.ts`. `style({...})` returns a scoped class string; import it into components as a normal value.
- Use camelCase props. Media under `@media` key; simple pseudos (`:hover`, `::before`) at top level; parameterized/combinator selectors under `selectors`.
- Every selector MUST reference `&` (single-element target): `'&:hover'`, `` `${parent} &` ``. Use getters `get selectors()` for interdependent refs.
- Theme with `createTheme()` (returns `[themeClass, vars]`) or `createGlobalTheme(':root', {...})`; type-lock with `createThemeContract()`. Read tokens as `vars.color.brand`.
- Multi-variant components: `recipe()` from `@vanilla-extract/recipes` — `base` / `variants` / `compoundVariants` / `defaultVariants`; type props via `RecipeVariants<typeof x>`.
- Build a typed atomic system with Sprinkles: `defineProperties({ conditions, defaultCondition, responsiveArray, properties, shorthands })` → `createSprinkles(...)`. Enables responsive object/array values `{ mobile:'column', desktop:'row' }`.
- `styleVariants()` for a keyed map of classes; `keyframes()`/`fontFace()`/`createVar()`/`assignVars()` for animations, fonts, dynamic vars.

```ts
// button.css.ts
import { recipe, RecipeVariants } from '@vanilla-extract/recipes';
export const button = recipe({
  base: { borderRadius: 6 },
  variants: { size: { sm: { padding: 12 }, lg: { padding: 24 } } },
  defaultVariants: { size: 'sm' },
});
export type ButtonVariants = RecipeVariants<typeof button>;
```

## DON'T — vanilla-extract
- Don't target another element from a `style` block (`'& a'`, `'& ~ div'`) — invalid. Use `globalStyle('${parent} a', {...})` for descendants (fewer selectors allowed there).
- Don't compute class names from runtime state expecting new CSS — the CSS set is fixed at build. Enumerate variants ahead of time (recipes/sprinkles).
- Don't inline `defineProperties(...)` into `createSprinkles()` — breaks type inference; assign to a variable first.
- Don't expect dynamic values without `createVar()`/`assignVars()` — arbitrary runtime values need CSS custom properties.

## Panda CSS (build-time, framework-agnostic)
Styling engine that generates atomic CSS + recipes at build time via PostCSS plugin (recommended) or CLI; static analysis scans JS/TS/JSX. `@pandacss/dev` has reached **v1 (stable)** — v0.x was the pre-1.0 line; check migration notes when jumping majors. Config in `panda.config.ts`; codegen emits a `styled-system/` dir you import from.

DO
- `css({...})` for atomic styles; `cva({ base, variants, compoundVariants, defaultVariants })` (atomic recipe, colocated) or `defineRecipe({ className, ... })` in config (config recipe, JIT — only emits variants found in code). Slots: `sva()` / `defineSlotRecipe()`.
- Use `tokens` + `semanticTokens` in config; patterns (`stack`, `flex`, `grid`, `hstack`) as layout primitives.
- Enable JSX style props via config `jsxFramework` (react/vue/solid/preact/qwik/svelte...). Frameworks: Next, Vite, Remix, Astro, Solid, Svelte, Vue, Qwik, Preact, Ember, Gatsby.

DON'T
- Don't pass dynamic props to a config recipe and expect all variants: `button({ size })` (variable) emits `defaultVariants` only; `button({ size:'lg' })` (literal) emits `lg`. For runtime-driven variants pre-generate with `staticCss` (e.g. `staticCss: ['*']`).
- Don't forget config recipes lose responsive variant props once `compoundVariants` is set.

```ts
import { cva } from '../styled-system/css';
const btn = cva({ base:{ display:'flex' }, variants:{ size:{ sm:{ p:'4' }, lg:{ p:'8' } } }, defaultVariants:{ size:'lg' } });
```

## StyleX (Meta, atomic, build-time)
Meta's atomic CSS-in-JS (`@stylexjs/stylex`, still **0.x** — pre-1.0, open-sourced late 2023). Compiles via `@stylexjs/babel-plugin` (or unplugin/postcss/eslint plugins) to collision-free atomic CSS in one static file; no runtime style injection (a tiny class-merge runtime remains). Bundle size plateaus as project grows.

DO
- `stylex.create({...})` to define; `stylex.props(styles.a, cond && styles.b)` to apply (spread onto element). Last-write-wins merge order is deterministic.
- Theme with `defineVars` (in a `.stylex.ts`) + `createTheme`.
- Framework-agnostic (anything taking `className`/`style`): React, Preact, Solid, Qwik, Angular, lit; Vue/Svelte need extra config.

DON'T
- Don't skip the compiler — StyleX requires the build plugin; nothing works from raw runtime.
- Don't rely on descendant/global selectors — StyleX is intentionally local/atomic; use vars for cross-cutting theming.

## Choosing — checklist
- Need RSC-safe, zero-runtime, framework-agnostic, TS-typed tokens/themes → vanilla-extract.
- Want atomic CSS + design-system recipes + JSX style props, config-driven → Panda.
- Meta-style strict atomic with enforced locality, large scaling app → StyleX.
- On runtime CSS-in-JS (styled-components — dev slowed but still patched, v7 in prerelease; Emotion) and hitting RSC/`"use client"` friction or SSR flash → migrate to one of the above (or Pigment CSS / Tailwind). All three here are build-time and RSC-compatible.

## Sources
- https://vanilla-extract.style/documentation/
- https://vanilla-extract.style/documentation/styling/
- https://vanilla-extract.style/documentation/packages/recipes/
- https://vanilla-extract.style/documentation/packages/sprinkles/
- https://panda-css.com/docs
- https://panda-css.com/docs/concepts/recipes
- https://stylexjs.com/docs/learn/
- npm registry: `@vanilla-extract/*`, `@pandacss/dev`, `@stylexjs/stylex` (version facts)
