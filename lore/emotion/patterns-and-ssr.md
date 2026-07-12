# emotion — Patterns & SSR

CSS-in-JS for **React** (`@emotion/react`, `@emotion/styled`) with a framework-agnostic core (`@emotion/css`). Runtime style injection with hashed class names. **Current: Emotion 11** — `@emotion/react@11.14.0`, `@emotion/styled@11.14.1` (Dec 2024 / Jun 2025). The default style engine for **MUI v5+**. React-only for the `css` prop / `styled` / theming; `@emotion/css` alone is framework-agnostic.

Assumes JS/TS + React lore exist separately. This covers styling specifics.

## Packages
- **`@emotion/react`** — `css` prop, `ThemeProvider`, `Global`, `keyframes`, `CacheProvider`. The React-recommended entry.
- **`@emotion/styled`** — `styled.div` component API. Install *alongside* `@emotion/react`.
- **`@emotion/css`** — framework-agnostic; `css()`/`cx()`/`injectGlobal`. No Babel/config needed. SSR needs manual `@emotion/server` setup.
- **`@emotion/cache`** — `createCache`; **`@emotion/server`** — SSR extraction.

## css prop — DO
- Prefer the **automatic runtime** (React `>=16.14.0`). No per-file pragma, best DX.
  - **Babel:** `["@babel/preset-react", { "runtime": "automatic", "importSource": "@emotion/react" }]` + plugin `"@emotion/babel-plugin"`.
  - **TS (react-jsx):** `tsconfig.json` → `"jsx": "react-jsx"`, `"jsxImportSource": "@emotion/react"`.
  - **Vite:** `@vitejs/plugin-react` → `react({ jsxImportSource: '@emotion/react', babel: { plugins: ['@emotion/babel-plugin'] } })`.
  - **Next.js (next/babel):** `["next/babel", { "preset-react": { "runtime": "automatic", "importSource": "@emotion/react" } }]` + `"@emotion/babel-plugin"`.
- `@emotion/babel-plugin` adds source maps, `label`, minification — enable it in prod builds.

```jsx
import { css } from '@emotion/react'
const box = css`color: hotpink; &:hover { color: rebeccapurple; }`
<div css={box} />
<div css={theme => ({ color: theme.colors.primary })} />
```

## css prop — DON'T
- **DON'T** forget the pragma if you skip the automatic runtime — classic runtime needs `/** @jsx jsx */` + `import { jsx } from '@emotion/react'`, or the per-file `/** @jsxImportSource @emotion/react */`. Missing it renders `[object Object]` / a raw class object.
- **DON'T** use `@emotion/babel-preset-css-prop` on Create React App or configs that forbid custom Babel — use `jsxImportSource` / pragma instead.
- **DON'T** mix the object `style` prop expecting Emotion features — only `css` supports nesting, media queries, vendor prefixing.

## styled vs css prop — DO / DON'T
- **DO** use `css` prop for one-off / co-located styles; use `styled` for reusable named components or when props drive style.
- **DO** read props/theme in `styled`: `` styled.button`color: ${p => p.theme.c};` ``.
- **DON'T** treat them as different engines — both compile to the same runtime; pick per ergonomics, don't import both for the same element.

## Theming — DO
- Wrap once: `import { ThemeProvider } from '@emotion/react'` → `<ThemeProvider theme={theme}>`.
- Read via `useTheme()` (hook), the `css` prop function `theme => ...`, or `styled` interpolation `p => p.theme`.
- TS: augment `@emotion/react`'s `Theme` interface (`declare module '@emotion/react' { export interface Theme {...} }`) for typed theme access.

## Composition — DO / DON'T
- **DO** compose with arrays; later entries win: `<div css={[base, active && activeStyles]} />`.
- **DO** interpolate serialized styles into others: `` css`${base}; padding:8px;` ``.
- **DON'T** rely on class-string order for merge precedence with `@emotion/css` — use `cx()` (it dedupes/merges correctly), not string concatenation.

## Performance — DON'T (hot paths)
- **DON'T** call `css()` / `styled()` inside render or per-item in a list — it re-serializes every render and defeats caching. Define styles at module scope.
```jsx
// BAD: new serialized style each render
const Row = ({c}) => <div css={css`color:${c}`} />
// GOOD: static at module scope; dynamic bits via css prop function or CSS vars
const row = css`color: var(--row-c);`
```
- **DON'T** generate `styled` components inside components — creates a new component type each render, remounting the subtree.
- **DO** push high-frequency dynamic values through CSS custom properties instead of new serialized rules.

## SSR — DO (default, zero-config)
- With `@emotion/react` + `@emotion/styled`, SSR **works with no setup**. Call React's `renderToString` / `renderToPipeableStream` directly — style tags are inserted inline above each element. Hydration is automatic (Emotion 11 uses `useInsertionEffect` with fallbacks → concurrent/React 18-safe insertion).
- This is the right default for **React 18 streaming** (`renderToPipeableStream`); the advanced path below does **not** support streaming.

## SSR — DON'T / advanced (only for `:nth-child`)
- Inline tags **can break `:nth-child` and sibling selectors**. Only then switch to critical extraction (no streaming):
```js
import createCache from '@emotion/cache'
import createEmotionServer from '@emotion/server/create-instance'
const cache = createCache({ key: 'css' })
const { extractCriticalToChunks, constructStyleTagsFromChunks } = createEmotionServer(cache)
// render app inside <CacheProvider value={cache}>
const chunks = extractCriticalToChunks(html)
const styleTags = constructStyleTagsFromChunks(chunks)
```
- Client: `createCache` with the same `key`; hydration of `data-emotion` ids is automatic on cache creation. **No manual `hydrate`** for `@emotion/react`.
- `@emotion/css` (framework-agnostic) instead uses `extractCritical` + manual `hydrate(ids)` from `@emotion/css` — else all rules reinsert.

## SSR — framework specifics
- **Next.js Pages router:** v10+ "just works"; use a custom `_document` with `extractCriticalToChunks` only if you hit `:nth-child` issues. (Note: `@emotion/styled@11.13.5` fixed dev/prod hash mismatches most visible on the Pages router.)
- **Next.js App Router (RSC):** default Emotion is a Client-Component runtime — wrap client subtrees in `CacheProvider` and flush with `useServerInsertedHTML` (see MUI's Next.js integration guide for the canonical pattern). Server Components can't use the `css` prop.
- **MUI:** Emotion is MUI v5/v6/v7's default engine; MUI's zero-runtime **Pigment CSS** is the opt-out for those wanting no runtime.

## Sources
- https://emotion.sh/docs/introduction
- https://emotion.sh/docs/ssr
- https://emotion.sh/docs/css-prop
- https://github.com/emotion-js/emotion/releases
- https://mui.com/material-ui/integrations/nextjs/
