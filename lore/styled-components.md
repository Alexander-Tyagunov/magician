# styled-components (core)

React CSS-in-JS (runtime); React Native via `styled-components/native`. Tagged-template API.

DO define styled components at module scope — NEVER inside render/component body (a new component each render busts caching and remounts the DOM node).
DO use transient props (`$primary`) so custom props don't reach the DOM; override specificity with `&&&`, not `!important`.
DO use the `css` helper for reusable fragments with interpolations/`keyframes` (a bare template literal there throws).
DO theming via `<ThemeProvider>` + `useTheme`; put continuously-changing values in `.attrs()` inline `style`, not interpolated into the template (new class per value). DON'T `@import` inside `createGlobalStyle`.
DO install the Babel/SWC plugin (stable class names, SSR, smaller bundles).

Version cue: current **v6** (peer `react >=16.8`; native TS types → uninstall `@types/styled-components`; `shouldForwardProp` no longer default → use `$` transient props; vendor prefixes off → `enableVendorPrefixes`). **v5** = last IE11 build; **v7** in prerelease. Active development has slowed (still patched, not sunset) — for perf-critical/zero-runtime or RSC, prefer vanilla-extract/Panda or CSS modules.

Commands: `npm i styled-components` · `npm i -D babel-plugin-styled-components`

Deep dive when writing non-trivial styled-components — read lore/styled-components/{patterns-and-migration}.md

## Sources
styled-components.com/docs, /docs/faqs; github.com/styled-components/styled-components/releases
