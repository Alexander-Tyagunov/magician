# styled-components — Patterns, SSR & maintenance-mode migration

React-only CSS-in-JS (tagged template literals). Not framework-agnostic; there is no official Vue/Svelte/Angular port. Runtime styling: styles are generated in the browser (or on the server per request), unlike zero-runtime tools (vanilla-extract, Panda, StyleX). Current stable: **v6** (v6.4.x). **v7** is in prerelease as of 2026. Prefer official docs — versions are the point.

## Maintenance status — READ FIRST

- **Announced 2025-03-17** (Open Collective, by maintainer quantizor): the project is in "maintenance mode." Direct quote: *"For new projects, I would not recommend adopting styled-components or most other css-in-js solutions."* Stated reason: React's Context API has no RSC migration path (a characterization Dan Abramov later disputed in comments).
- It still ships patches — v6.4.3 (2026) and v7.0.0 prereleases exist — but treat it as feature-frozen strategically.

DO
- Keep existing styled-components apps on **v6**; it is stable and still patched.
- For **new** projects, choose a zero-runtime option: **vanilla-extract**, **Panda CSS**, or **CSS Modules** (framework-agnostic; no per-render runtime cost, RSC-native).
- Migrate incrementally when moving to RSC-heavy React — styled components must be Client Components.

DON'T
- Start a greenfield RSC/Next-App-Router project on styled-components expecting long-term feature growth.
- Assume it works in React Server Components without `'use client'` — the styled factory needs a client boundary (v6.3+ relaxed some cases; verify).

## v6 upgrade (from v5) — breaking changes

DO
- `npm i styled-components@^6 stylis@^4` and **`npm uninstall @types/styled-components`** — types ship built-in in v6.
- Prefix every custom style-only prop with **`$` (transient props)** so it is filtered from the DOM: `` styled.div`color:${p=>p.$active?'red':'gray'}` ``.
- Restore v5's automatic DOM-prop filtering with `StyleSheetManager` + `shouldForwardProp` (v6 no longer filters by default):

```jsx
import isPropValid from '@emotion/is-prop-valid';
<StyleSheetManager shouldForwardProp={(prop, el) =>
  typeof el === 'string' ? isPropValid(prop) : true}>
```

- Opt vendor prefixing back in with **`enableVendorPrefixes`** (v6 dropped auto-prefixing; the old flag `disableVendorPrefixes` was inverted).
- Replace `withComponent()` and `$as`/`$forwardedAs` with the polymorphic **`as`** / **`forwardedAs`** props (those transient variants were removed).

DON'T
- Rely on an implicit `&` for nested selectors that don't start with `&` — v6 no longer injects it. Write `& .child` explicitly.
- Stay on Node <16 or stylis v3 (v6 requires Node 16+, stylis v4). Need IE11? Stay on v5.

## `.attrs` (v6.4)

DO
- Return values from the callback; the props argument is now an **immutable snapshot** — mutating it is a no-op.
- Expect `.attrs`-provided props to be **auto-optional** on the component's type (v6.4).

```jsx
const Input = styled.input.attrs(p => ({ type: 'text', $size: p.$size ?? '1em' }))`
  font-size: ${p => p.$size};
`;
```

DON'T
- Assume order: `.attrs` apply **innermost → outermost**, so an outer wrapper overrides an inner one.

## Theming

DO
- Wrap the tree in **`ThemeProvider`** (React context) and read theme via interpolation `p => p.theme.colors.primary`.
- Read theme outside styled components with the **`useTheme`** hook.
- Type the theme by augmenting the built-in **`DefaultTheme`** interface:

```ts
// styled.d.ts
import 'styled-components';
declare module 'styled-components' {
  export interface DefaultTheme { colors: { primary: string } }
}
```

DON'T
- Overload `ThemeProvider` for one-off values you could pass as props.

## Don't create styled components in render

DON'T
- Define `styled.*` **inside** a component body / render. Official docs: doing so *"will thwart caching and drastically slow down rendering"* — a new component class is generated every render.

DO
- Declare all styled components at module top level; drive variation with props/transient props or the `css` helper.

## SSR

DO
- Server-render with **`ServerStyleSheet`**: `collectStyles(<App/>)` (or `StyleSheetManager`), then inject `sheet.getStyleTags()` (string) or `sheet.getStyleElement()` (React elements). Always call **`sheet.seal()`** afterward.

```jsx
const sheet = new ServerStyleSheet();
const html = renderToString(sheet.collectStyles(<App />));
const styleTags = sheet.getStyleTags();
sheet.seal();
```

- Use `renderToPipeableStream` for React 18 **streaming SSR** (support added v6.2).
- **Add the compiler plugin** — Babel (`babel-plugin-styled-components`) or the SWC transform — for **deterministic component IDs** so server and client class names match (prevents hydration mismatch), plus minification and readable debug names.
  - Next.js: set `compiler.styledComponents: true` in `next.config.js`.
- RSC (v6.3+): factories work without `'use client'` in more cases; v6.4 adds `stylisPluginRSC` and automatic CSP **nonce** detection.

DON'T
- Ship SSR without the compiler plugin — non-deterministic IDs cause class-name mismatches and hydration warnings.
- Use `@import` inside `createGlobalStyle` in RSC/production — it *"silently fails in production."*

## Migration-away cheatsheet

| From styled-components | To (zero-runtime) |
|---|---|
| `` styled.div`...` `` + `$props` | vanilla-extract `style()` + `recipe()`; Panda `css()` / `cva()` |
| `ThemeProvider` runtime theme | CSS custom properties / `createTheme` (v-e) or Panda tokens |
| Runtime dynamic styles | CSS variables set inline; static variants at build time |

DO prefer CSS custom properties for dynamic values — portable across styled-components v6, vanilla-extract, and Panda, and RSC-safe.

## Sources

- https://styled-components.com/docs/basics
- https://styled-components.com/docs/advanced
- https://styled-components.com/docs/faqs
- https://opencollective.com/styled-components/updates/thank-you (maintenance-mode announcement, 2025-03-17)
- https://github.com/orgs/styled-components/discussions/5568
- https://github.com/styled-components/styled-components (README, releases: v6.4.3, v7.0.0 prereleases)
