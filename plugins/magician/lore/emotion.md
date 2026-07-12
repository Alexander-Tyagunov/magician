# Emotion (CSS-in-JS) — core

Version: v11 current (Nov 2020); v10 prior. React-first; framework-agnostic via `@emotion/css`.

DO
- React: `@emotion/react` (css prop + theming) + `@emotion/styled`. No-babel/agnostic: `@emotion/css` (`css`, `cx`).
- Enable css prop: `/** @jsxImportSource @emotion/react */` OR `@emotion/babel-plugin` (`runtime:'automatic',importSource:'@emotion/react'`).
- Type theme: `declare module '@emotion/react'{ export interface Theme{...} }`; read via `css={t=>({color:t.primary})}` or `props.theme`.
- Static styles at module scope; object styles for dynamic values.
- SSR advanced path: `createCache({key})` + `createEmotionServer` → `extractCriticalToChunks` + `constructStyleTagsFromChunks`; wrap `CacheProvider`; hydrate client cache.
- Next.js App Router: `CacheProvider` inside a `"use client"` provider using `useServerInsertedHTML`.

DON'T
- No css prop without pragma/plugin → renders `[object Object]`.
- No v10 names: `@emotion/core`→`@emotion/react`, `emotion`→`@emotion/css`, `emotion-theming` folded in, `babel-plugin-emotion`→`@emotion/babel-plugin`.
- Don't trust default SSR with `nth-child` (inline style tags break it) — use advanced path; advanced ≠ streaming.
- Stylis v4 (v11): `prefix` option removed, `@import` must be top-level; custom cache `key` required & unique (not `'css'`).

Commands: `npm i @emotion/react @emotion/styled`; SSR `@emotion/server`; agnostic `@emotion/css`.

Deep dive when writing non-trivial emotion — read lore/emotion/{patterns-and-ssr}.md

Sources: emotion.sh/docs {css-prop, emotion-11, ssr}
