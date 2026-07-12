# react — Patterns & pitfalls

Senior-reviewer checklist. JS/TS lore lives elsewhere; this is React-specific.

**Version anchor (verify against react.dev):** React 19 is the current stable major (Dec 2024). React 19.2 (Oct 2025) is the latest release line — added `<Activity>`, stabilized `useEffectEvent`, added `cacheSignal`. React 18 introduced concurrent rendering (`useTransition`, `useDeferredValue`, `useSyncExternalStore`, automatic batching). Tie every feature below to the version that introduced it.

---

## Composition over inheritance
React has no component inheritance. Compose.

- DO pass UI via `children`/render props for reuse; extract behavior into custom hooks, not base classes.
- DON'T subclass or stack HOCs where a hook or `children` suffices.
- DON'T prop-drill deeply — wrap with `children`, or use context for cross-cutting values (theme, auth). Context is not a state manager; overuse re-renders all consumers.

## Controlled vs uncontrolled inputs
- Controlled: value driven by state — `<input value={x} onChange={e => setX(e.target.value)} />`. Use when you validate, transform, or read on every keystroke.
- Uncontrolled: DOM holds the value — `<input defaultValue={x} ref={ref} />`, read via `ref.current.value`. Use for simple/perf-sensitive forms.
- DON'T mix: passing `value` without `onChange` (and non-null) makes a read-only field and warns. Use `defaultValue`/`defaultChecked` for uncontrolled.
- DON'T flip an input between controlled and uncontrolled across renders (value going `undefined`↔defined). Initialize state to `''`, not `undefined`.
- React 19: prefer form **Actions** + `useActionState` for submit flows; `<form action={fn}>` and `useFormStatus()` (from `react-dom`) for pending state.

## Lifting & colocating state
- DO keep state minimal (DRY). If a value is derivable from props/state, compute it in render — don't store it.
- DO colocate: put state in the lowest component that needs it. Only lift to the closest common parent when siblings must share it; pass setters down as props (one-way flow).
- DON'T copy props into state (`useState(props.x)`) to "sync" — that forks the source of truth. Derive, or lift the state up.
- DON'T `useEffect` to mirror one state into another; compute during render. (react.dev: "You Might Not Need an Effect".)

## Custom hooks for reuse
- DO extract stateful logic into `use*` functions; share logic, not state — each caller gets independent state. `use*` name lets the linter enforce rules of hooks.
- DON'T call hooks conditionally, in loops, or after early returns — same order every render.
- DON'T wrap pure helpers in a hook; only when it uses other hooks.

## Error boundaries
Only **class** components can be error boundaries (no hook/function version as of React 19).

```jsx
class ErrorBoundary extends React.Component {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; } // render fallback
  componentDidCatch(error, info) { log(error, info.componentStack); } // side effect
  render() { return this.state.hasError ? this.props.fallback : this.props.children; }
}
```
- DO use the `react-error-boundary` package instead of hand-rolling (react.dev-recommended).
- DON'T expect boundaries to catch: event-handler errors, async (`setTimeout`), SSR, or errors in the boundary itself. (Exception: errors inside a `startTransition` are caught.) Handle those with try/catch.

## Portals
`createPortal(children, domNode, key?)` (from `react-dom`) renders into a different DOM node (modals, tooltips escaping `overflow:hidden`).
- KEY: events bubble along the **React tree**, not the DOM tree; context still flows in. Stop propagation if a parent `onClick` catches portal clicks unexpectedly.
- DO manage focus/ARIA for dialogs (WAI-ARIA modal pattern).

---

## Pitfalls (the ones that ship bugs)

### Mutating state
- DON'T mutate. `state.push(x)`, `obj.k = v`, `arr.sort()` won't re-render and corrupt snapshots.
- DO replace: `setArr([...arr, x])`, `setObj({...obj, k: v})`, `setArr(arr.toSorted())`. Mutating (`push/pop/sort/reverse/splice`) vs non-mutating (`map/filter/slice/concat/toSorted`).
- Local mutation of objects created **during this render** is fine.

### setState in render / impurity
- DON'T call `setState`, mutate props/state, or do side effects during render. Rendering must be pure: same inputs → same JSX.
- Calling `setState` unconditionally in render is an infinite loop. Set state in event handlers or effects.
- StrictMode double-invokes components/initializers/updaters in dev to surface impurity — fix the impurity, don't silence it.

### Stale closures
State/props are a per-render **snapshot**; closures capture the render's values.
- DON'T read state right after setting it — the variable doesn't change mid-function. `setCount(count+1); setCount(count+1)` increments once.
- DO use updater form for sequential/async updates: `setCount(c => c + 1)`.
- DON'T omit deps used inside `useEffect`/`useCallback` to "fix" re-runs — you get stale reads. Include all reactive deps (trust `eslint-plugin-react-hooks`).
- For logic that must read latest values without re-subscribing, use `useEffectEvent` (stable in React 19.2) — declare the event, call it from the effect, never list it as a dep. Pre-19.2: a `useRef` mirror of the latest value.

### Missing / bad keys
- DO give siblings in a list stable, unique `key`s from data identity (`item.id`).
- DON'T use array `index` as key for reorderable/insertable lists — state/DOM misassociates. Index is acceptable only for static, append-only lists.
- DON'T use `Math.random()`/regenerated keys — remounts every render, loses state and focus.

### Effect misuse
- DON'T use effects for derived data, event responses, or to transform props for render. Effects are for **external systems** (subscriptions, non-React widgets, network on mount).
- DO return a cleanup; expect effects to run twice on mount in dev StrictMode — cleanup must make that idempotent.

---

## RSC vs Client Components (React 19)
Server Components render on the server/at build, never ship to the browser. **They are the default** — there is no `"use server"`-for-components directive.

- `"use client"` — marks the boundary; everything imported below it is a Client Component (can use state/effects/handlers/browser APIs).
- `"use server"` — marks **Server Functions** (server actions callable from the client), NOT Server Components. Common confusion — do not mislabel.

Server Components:
- CAN be `async` and `await` data (DB/fs/CMS) directly; use heavy deps without bundling them.
- CANNOT use `useState`, `useEffect`, event handlers, refs, or browser-only APIs.
- DO pass only **serializable** props across the boundary (primitives, plain objects/arrays, JSX/`children`, Promises). No functions (except Server Functions), class instances, or Dates-in-the-wrong-place.
- DO start a promise on the server and resolve on the client with `use(promise)` inside `<Suspense>` to stream.
- DON'T add `"use client"` at the app root — it opts the whole tree out of RSC. Push the boundary as low as possible; keep leaves interactive, parents server.
- Framework: Next.js **App Router** (stable since 13.4) is the mainstream RSC host; the Pages Router has no RSC. Vite/other setups need an RSC-capable bundler.

## React 19 API shifts (verify before using)
- `ref` is a regular prop on function components (React 19); `forwardRef` is **no longer needed** (still works; deprecation planned for a future version, not yet deprecated). `<Child ref={r} />` then read `props.ref`.
- `use(resource)` — read a Promise or context, callable conditionally (not a hook's ordering rules). React 19.
- `useOptimistic`, `useActionState` (react), `useFormStatus` (react-dom) — Actions/form flow. React 19.
- `<Context>` renders as its own Provider (`<Ctx value>`), no `.Provider` needed. React 19.
- `<Activity mode="visible|hidden">` to pre-render/hide subtrees keeping state. React 19.2.

## Sources
- https://react.dev/reference/react — hooks/API index
- https://react.dev/reference/react/hooks
- https://react.dev/reference/react/useState
- https://react.dev/reference/react/useEffectEvent
- https://react.dev/reference/react/Component — error boundaries
- https://react.dev/reference/react-dom/createPortal
- https://react.dev/reference/rsc/server-components
- https://react.dev/reference/rsc/directives
- https://react.dev/learn/thinking-in-react
- https://react.dev/learn/keeping-components-pure
- https://react.dev/learn/you-might-not-need-an-effect
- https://react.dev/blog/2024/12/05/react-19 — React 19 stable
- https://react.dev/blog/2025/10/01/react-19-2 — Activity, useEffectEvent, cacheSignal
- https://nextjs.org/docs/app — App Router (RSC host)
