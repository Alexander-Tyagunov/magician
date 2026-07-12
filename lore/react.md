# React — core digest

Version cue: React 19.2 (Oct 2025) current; 19.0 = Dec 2024. Check `react` version; gate 19-only APIs. Compiler 1.0 stable.

DO keep render pure: same props/state/context → same output; no side effects, no prop/state mutation. Side effects go in handlers/Effects.
DO call Hooks only at top level of components/custom Hooks — never in loops, conditions, or after early returns.
DON'T call `useEffect` to derive state — compute in render; render via JSX `<Comp/>`, never call `Comp()`.
DO treat state as immutable; use updater `setX(x=>x+1)`; give lists a stable `key`, not index.

React 19: `ref` is a plain prop (`forwardRef` deprecating). `use(promise|context)` reads in render (conditional-safe). Actions: `useActionState`, `useOptimistic`, `<form action>`, `useFormStatus`, async `useTransition`. RSC: `'use client'`/`'use server'`.
19.2: `useEffectEvent` (non-reactive Effect logic; NEVER in deps), `<Activity mode>`.
DON'T over-memoize under React Compiler — it auto-memoizes; drop manual `useMemo`/`useCallback`. No compiler: keep them.
DON'T use removed 18-era APIs: `ReactDOM.render`/`hydrate`, string refs, legacy context, function `propTypes`/`defaultProps`.

Commands: scaffold `npm create vite@latest`; lint `eslint-plugin-react-hooks`; compiler `npm i -D babel-plugin-react-compiler@latest`.

Deep dive when writing non-trivial react — read lore/react/{hooks-and-state,effects-and-refs,performance,patterns-and-pitfalls}.md

Sources: react.dev/reference/{react,rules,react/forwardRef}, /blog/2025/10/01/react-19-2, /blog/2025/10/07/react-compiler-1
