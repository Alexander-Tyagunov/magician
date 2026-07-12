# react — Performance

Framework-specific render performance. Assumes JS/TS perf lore exists separately.
Verified against react.dev (React 19 current). Tie every optimization to a measurement.

## Profile first, optimize second

DO
- Measure before changing anything. Use React DevTools **Profiler** tab, or the `<Profiler id onRender>` component to capture `actualDuration` vs `baseDuration` programmatically.
- Profile a **production build** with CPU throttling. Dev/StrictMode renders twice and skews timings.
- Time a suspect calculation before memoizing: `console.time('x'); f(); console.timeEnd('x')`. Memoize only if it's ≥~1ms and runs on hot paths.

DON'T
- Don't sprinkle `memo`/`useMemo`/`useCallback` speculatively. "Might be slow" is not a measurement.
- Don't trust dev-mode timings — `<Profiler>` is disabled in prod by default (needs a profiling build).

## React Compiler (prefer over manual memo)

React Compiler auto-memoizes components, values, and functions at build time — more comprehensive than hand-written `memo`/`useMemo`/`useCallback`. Works best with **React 19**; also supports 17/18.

DO
- Prefer enabling the compiler over manual memoization on new code.
- Install per docs: `npm i -D babel-plugin-react-compiler@latest` and lint with `eslint-plugin-react-hooks@latest` (`recommended-latest` preset). React 19: zero config. React 17/18: add `react-compiler-runtime@latest` **and** set `target: '17' | '18'`.
- Once enabled, delete redundant manual `memo`/`useMemo`/`useCallback` — the compiler covers them.

DON'T
- Don't assume it's on. If the build isn't compiled, the manual rules below still apply.
- Don't fight the compiler with impure render logic — it optimizes correct, pure components.

## memo — skip re-render on unchanged props

`memo(Component)` skips re-render when props are shallow-equal (`Object.is` per prop). It's an optimization, not a guarantee; it does NOT stop re-renders from own state or context changes.

DO
- Apply `memo` only when a component **re-renders often with the same props** AND its render is expensive.
- Use it heavily on granular, high-frequency UI (canvas/editor items); rarely on coarse page/section swaps.

DON'T
- Don't wrap a component whose props are always new — `memo` then does nothing (see inline-props below).
- Don't write a custom `arePropsEqual` that skips comparing functions (stale-closure bugs) or does deep equality (can freeze the app).

## Inline object/array/function props break memo

New `{}`, `[]`, `() => {}` each render are never reference-equal, so they defeat `memo` on the child.

DON'T
```jsx
<Child style={{ margin: 8 }} items={[a, b]} onSave={() => save(id)} />  // 🔴 new refs every render
```

DO — best to worst:
```jsx
// 1. Pass primitives, not objects
<Child margin={8} />

// 2. Hoist static values out of the component
const STYLE = { margin: 8 };
<Child style={STYLE} />

// 3. Memoize when the value must be derived
const items = useMemo(() => [a, b], [a, b]);
const onSave = useCallback(() => save(id), [id]);
<Child items={items} onSave={onSave} />
```

## useMemo / useCallback — only three real reasons

`useMemo` caches a value; `useCallback` caches a function (`useCallback(fn,d) === useMemo(()=>fn,d)`). Both compare deps with `Object.is`.

DO — use only when:
1. Skipping an expensive, rarely-changing calculation.
2. Producing a stable prop for a `memo`-wrapped child.
3. Producing a value that is a dependency of another Hook (`useEffect`/`useMemo`).

DON'T
- Don't list an object/function created in the render body as a dep — it changes every render. Move it **inside** the memo callback and depend on primitives:
```jsx
const items = useMemo(() => {
  const opts = { mode: 'whole-word', text };   // ✅ inside
  return search(all, opts);
}, [all, text]);                                // ✅ primitive deps
```
- Don't rely on the cache for correctness — React may discard it. For guaranteed persistence use `useState`/`useRef`.
- Don't call hooks in loops/conditions; for per-item memo, extract a child component instead.

## Reduce the NEED for memoization (structural fixes > memo)

DO
- Pass JSX via `children` so a stateful wrapper doesn't re-render subtrees it owns.
- Keep state **local**; don't lift it higher than needed.
- Keep render pure; remove unnecessary Effects and Effect deps (move objects/functions inside the Effect).

## Keys in lists

Keys let React match items across renders (reorder/insert/delete). Put the `key` on the element **directly inside `map()`**.

DO
- Use a **stable id from the data** (`item.id`, DB key, `crypto.randomUUID()` stored with the item).

DON'T
- Don't use the array **index** as key for lists that reorder/insert/delete — causes subtle state/DOM bugs (index-as-key is fine only for truly static lists).
- Don't use `key={Math.random()}` — keys never match, everything remounts each render, losing DOM state and input focus.
- `key` is not a prop; pass the id separately if the child needs it: `<Row key={id} id={id} />`. Use `<Fragment key>` (not `<>`) when an item renders multiple nodes.

## Code-splitting — lazy + Suspense

`lazy(() => import('./X'))` defers a component's code until first render; it suspends while loading. Requires a default export and bundler `import()` support.

DO
- Split at route boundaries and heavy, rarely-used views; wrap in `<Suspense fallback={...}>`.
- Declare `lazy(...)` at **module top level**.

DON'T
```jsx
function Editor() {
  const Preview = lazy(() => import('./Preview'));  // 🔴 remounts + resets state every render
}
```
- Add an Error Boundary around lazy trees — a rejected import throws to the nearest boundary.

## Concurrent rendering — keep input responsive

Use these when an expensive re-render blocks typing/interaction.

`useTransition` — you own the `setState`:
```jsx
const [isPending, startTransition] = useTransition();
startTransition(() => setTab(next));   // non-blocking, interruptible
```
DO use `isPending` for pending UI. DON'T use transitions for controlled text inputs (input updates must be sync).

`useDeferredValue` — you receive a value you don't control:
```jsx
const deferred = useDeferredValue(query);   // lags behind; input stays responsive
<SlowList text={deferred} />                 // MUST be memo() or deferral is pointless
```
DON'T pass objects created during render to `useDeferredValue` (new ref → needless background renders). Prefer it over debounce/throttle for render deferral — it's interruptible and adapts to device speed (still debounce/throttle *network* calls if needed).

React 19 note: **Actions** — `startTransition` accepts async functions; `isPending` spans the async work. After an `await`, wrap follow-up state updates in another `startTransition` (async context is lost). For ordered async, prefer `useActionState`/`<form>` actions. `useDeferredValue`'s `initialValue` param is also 19+.

Version fallback: `useTransition`/`useDeferredValue`/`lazy`/`Suspense`/`memo` exist in React 18. Async transitions/Actions and `initialValue` are React 19 only — on 18, do post-await updates without the Action pattern and drive spinners manually.

## Sources
- https://react.dev/reference/react/memo
- https://react.dev/reference/react/useMemo
- https://react.dev/reference/react/useCallback
- https://react.dev/reference/react/useTransition
- https://react.dev/reference/react/useDeferredValue
- https://react.dev/reference/react/lazy
- https://react.dev/reference/react/Profiler
- https://react.dev/learn/react-compiler
- https://react.dev/learn/react-compiler/installation
- https://react.dev/reference/react-compiler/configuration
- https://react.dev/learn/rendering-lists
