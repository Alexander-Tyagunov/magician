# react — deep dive

> On-demand companion to `lore/react.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Hooks & state](#hooks-and-state) · [Effects & refs](#effects-and-refs) · [Performance](#performance) · [Patterns & pitfalls](#patterns-and-pitfalls)

## Hooks & state <a id="hooks-and-state"></a>

Framework-specific state lore. Assumes JS/TS lore lives elsewhere. Version facts verified against react.dev.

Version anchors: automatic batching → **React 18** (`createRoot`). Actions, `useActionState`, `useOptimistic`, `use`, `<Context>` as provider, ref-as-prop → **React 19** (stable 2024-12-05). Confirm the project's `react` version before using 19-only APIs; fall back to 18 patterns otherwise.

### Rules of Hooks (non-negotiable)

DO
- Call hooks at the **top level** of a component or a custom hook (name starts with `use`), before any early `return`.
- Keep call order identical on every render — React tracks hooks by call index.
- Enforce with `eslint-plugin-react-hooks` (flat config: `reactHooks.configs['recommended-latest']`).

DON'T
- Call hooks in conditions, loops, nested functions, event handlers, class components, or inside `try/catch/finally`.
- Call hooks from plain JS functions — only components and custom hooks.

```js
// 🔴 conditional hook — breaks call order
if (cond) { const t = useContext(Ctx); }
// ✅ hoist, branch on the value
const t = useContext(Ctx);
if (cond) { /* use t */ }
```

Exception: `use` is **not** a hook — it may be called conditionally / after early returns (see below).

### useState

DO
- Destructure `const [state, setState] = useState(init)`.
- Pass an **initializer function** for expensive init so it runs once, not every render: `useState(createInitial)` — pass the function, don't call it.
- Use the **updater form** when the next value derives from the previous, or when batching multiple updates: `setN(n => n + 1)`.
- Treat state as **read-only** — replace objects/arrays (`{...obj}`, `[...arr]`, `.map`, `.filter`); reach for Immer only for deep nesting.

DON'T
- `useState(createInitial())` — runs the work on every render.
- Read state right after `setState` and expect the new value — it applies on the *next* render.
- Mutate then `setObj(obj)` — same reference fails the `Object.is` check and no-ops.
- Stack `setN(n+1); setN(n+1)` expecting +2 — stale `n`; use the updater.

```js
const [todos, setTodos] = useState(createInitialTodos); // lazy init, once
setAge(a => a + 1); setAge(a => a + 1);                  // +2, queued in order
```

### useReducer

DO
- Prefer over `useState` when next state depends on non-trivial logic, or several values update together.
- Keep the reducer **pure** (no side effects, no async) — `(state, action) => newState`.
- Use lazy init: `useReducer(reducer, initialArg, init)`.

DON'T
- Put async or side effects in the reducer (that's what Actions / effects are for).

### Derived vs stored state

DO
- **Compute during render** anything derivable from props/state/existing state — don't store it.
- Memoize the derivation only if measurably expensive: `useMemo(() => derive(a), [a])`.

DON'T
- Mirror a prop into state (`useState(props.x)`) then sync with an effect — it goes stale. Compute inline, or reset via `key`.
- Store `filteredList`, `fullName`, counts, totals in state — recompute.

```js
// 🔴 redundant state + sync effect
const [full, setFull] = useState('');
useEffect(() => setFull(`${first} ${last}`), [first, last]);
// ✅ derive
const full = `${first} ${last}`;
```

### Lifting state / composition

DO
- Lift shared state to the **closest common ancestor**; hand value + setter down as props.
- Prefer **passing JSX as `children`** to avoid prop-drilling through layers that don't use the data.

DON'T
- Duplicate the same source of truth in two siblings.
- Drill a prop through many intermediate components — extract components and pass `children` first.

```jsx
// ✅ Layout doesn't need posts; hand it children
<Layout><Posts posts={posts} /></Layout>
```

### Context — and when it re-renders

Order of escalation: **props → composition (`children`) → context**. Don't overuse context.

DO
- Reach for context only when data is truly cross-cutting (theme, locale, auth, current user).
- **Every consumer re-renders when the provider `value` changes** — `useMemo` the value object and split independent concerns into separate contexts (e.g. state vs dispatch) to limit re-renders.
- React 19: render `<Ctx value={v}>` directly (Provider component is `<Ctx>` itself). Pre-19: `<Ctx.Provider value={v}>`.
- Pair a reducer with context for complex shared state.

DON'T
- Put data in context just because it's passed a few levels deep — props/composition are clearer.
- Pass a fresh inline object as `value` each render — forces all consumers to re-render.

```jsx
const value = useMemo(() => ({ user, setUser }), [user]); // stable
<AuthContext value={value}>{children}</AuthContext>       // React 19
const user = useContext(AuthContext);
```

### Batching (React 18+)

DO
- Rely on **automatic batching** everywhere — event handlers, promises, `setTimeout`, native handlers all batch into one re-render (requires `createRoot`).
- Use `flushSync(() => setX(v))` only when you must read updated DOM synchronously (rare).

DON'T
- Assume N `setState` calls = N renders. Don't sprinkle `flushSync` to "force" order — use updater functions.

### React 19 Actions & async state

Actions = async functions run inside a transition; React manages pending/error/optimistic automatically.

`useActionState(fn, initialState, permalink?)` → `[state, dispatchAction, isPending]`. `fn(prevState, payload)` may be async and have side effects. Dispatch only inside an Action (a `<form action>`, or wrapped in `startTransition`).

```js
const [error, submit, isPending] = useActionState(async (prev, formData) => {
  const err = await save(formData.get('name'));
  return err ?? null;
}, null);
<form action={submit}><input name="name" /><button disabled={isPending}/></form>
```

- **`useActionState`** replaces canary `ReactDOM.useFormState` (deprecated). Import from `react`.
- **`useOptimistic(value, reducer?)`** → `[optimistic, setOptimistic]`. Set only inside an Action; UI shows optimistic value while pending, converges/reverts automatically.
- **`useFormStatus()`** (from `react-dom`) reads the parent `<form>`'s pending state without prop-drilling.

DON'T
- Call `dispatchAction` / `setOptimistic` outside an Action — `isPending` won't track and React errors.

### `use(resource)` (React 19)

DO
- Read a **Promise** (component suspends; needs a `<Suspense>` boundary; errors hit the nearest Error Boundary) or **context**.
- Call it conditionally / after early returns — it is not a hook.
- Pass a **cached/stable** Promise (from a Server Component or a cache), not one created in render.

DON'T
- Wrap `use(promise)` in `try/catch` — use an Error Boundary.
- `use(fetch(...))` inline — new Promise every render → endless fallback. Reading context with `use` is unsupported in Server Components.

### Sources

- https://react.dev/reference/react/hooks
- https://react.dev/reference/rules/rules-of-hooks
- https://react.dev/reference/react/useState
- https://react.dev/reference/react/useActionState
- https://react.dev/reference/react/useOptimistic
- https://react.dev/reference/react/use
- https://react.dev/learn/passing-data-deeply-with-context
- https://react.dev/blog/2024/12/05/react-19
- https://react.dev/blog/2022/03/29/react-v18

## Effects & refs <a id="effects-and-refs"></a>

Effects synchronize a component with an **external system** (network, DOM node, timer, subscription, non-React widget). They are an escape hatch, not the default. Refs hold mutable values that must survive renders but must **not** drive rendering. Covers React 18 & 19; javascript/typescript lore lives separately.

### DO — reach for `useEffect` only to synchronize with external systems

- DO use it for: subscriptions (`addEventListener`), timers (`setInterval`), imperative widgets (map/chart libs, `<dialog>.showModal()`), observers (`IntersectionObserver`), and manual data fetch when no framework/cache exists.
- DO declare **every reactive value** (props, state, values derived from them) referenced by the setup in the dependency array. React compares with `Object.is`.
- DO return a **symmetrical cleanup**: undo exactly what setup did (disconnect what you connected, clear what you set). Cleanup runs before every re-run *and* on unmount.

```js
useEffect(() => {
  const conn = createConnection(serverUrl, roomId);
  conn.connect();
  return () => conn.disconnect();     // symmetrical
}, [serverUrl, roomId]);              // all reactive values
```

- DO guard manual fetches against races with an `ignore` flag (a form of cleanup):

```js
useEffect(() => {
  let ignore = false;
  fetchBio(person).then(r => { if (!ignore) setBio(r); });
  return () => { ignore = true; };
}, [person]);
```

- DO extract repeated Effects into custom hooks (`useOnlineStatus`, `useChatRoom`). Fewer raw Effects = more maintainable.

### DON'T — use an Effect to derive data or run event logic

Ask *why* the code runs. Component was **displayed** → maybe an Effect. **User interaction** → event handler.

- DON'T store derived state. Calculate during render.
  - `const fullName = first + ' ' + last;` — not `useEffect(() => setFullName(...))`.
- DON'T Effect+`setState` for an expensive calc. Use `useMemo(() => fn(a,b), [a,b])`.
- DON'T reset state on prop change with an Effect. Pass a `key` to remount: `<Profile userId={id} key={id} />`.
- DON'T adjust *some* state via Effect. Adjust during render with a prev-value guard, or restructure to compute it:

```js
const [prevItems, setPrevItems] = useState(items);
if (items !== prevItems) { setPrevItems(items); setSelection(null); }
```

- DON'T put user-action logic (notifications, POST on submit, cart add) in an Effect — it fires on unrelated re-renders/refresh. Put it in the handler.
- DON'T chain Effects that `setState` to trigger the next Effect. Compute during render and update all state in one handler; chains cause extra render passes and are fragile.
- DON'T notify the parent from an Effect (`useEffect(() => onChange(v))`). Call `onChange` in the same event as `setState` (React batches → one render), or lift state up.
- DON'T subscribe to an external store by hand — prefer `useSyncExternalStore` (SSR-safe).

### Dependencies — obey the linter

- DON'T suppress `react-hooks/exhaustive-deps`. Removing a dep means *proving* it's non-reactive, not silencing the warning.
- To drop a dep: use the updater form `setCount(c => c + 1)` (drops `count`); move constants **outside** the component; create objects/functions **inside** the effect so their identity isn't a dep.
- Object/function deps created during render change identity every commit → effect over-fires. Define them inside the effect or memoize.
- `[]` = run once after mount; `[a,b]` = run when a dep changes; omitted = run after **every** commit.

### StrictMode double-invoke (dev only)

- React 18+ Strict Mode runs **setup → cleanup → setup** on mount in development to surface missing/asymmetric cleanup. Production runs once.
- This is a **feature, not a bug**: if a double-invoke breaks something (double connections, doubled timers, duplicate fetches), your cleanup is wrong. Fix cleanup — don't add a "ran once" ref guard.
- Effects run **client-only** — never during SSR.

### `useRef` — mutable, non-rendering values

```js
const ref = useRef(null);   // same object every render; ref.current is mutable
```

- DO use for values that persist but don't affect output: timeout/interval IDs, DOM nodes, previous values, non-React instances.
- DON'T read or write `ref.current` **during render** (except lazy init). It makes renders impure. Mutate in effects/handlers. If the value is shown in UI, use state instead.
- DO lazy-init expensive ref contents to avoid recreating each render:

```js
const playerRef = useRef(null);
if (playerRef.current === null) playerRef.current = new VideoPlayer(); // once
```

- DOM refs: `useRef(null)` → `<input ref={inputRef} />` → `inputRef.current` is the node after mount, `null` after removal. Read it in handlers/effects, never during render.

#### React 19 ref changes

- **`ref` is a plain prop** for function components. No `forwardRef`:

```js
function MyInput({ ref, ...props }) { return <input ref={ref} {...props} />; }
```

  `forwardRef` still works in 19 but is slated for deprecation. Pre-19: keep using `forwardRef`.
- **ref callbacks may return a cleanup**: `ref={node => { ...; return () => {...}; }}`. When a cleanup is returned, React no longer calls the ref with `null` on unmount.
- Avoid implicit-return ref callbacks — `ref={n => (inst = n)}` returns a value TS now rejects. Use a block body: `ref={n => { inst = n; }}`.

### `useLayoutEffect` — measure before paint

- Fires **synchronously before the browser repaints**; state updates inside are flushed before paint. Use only to measure DOM layout and re-render before the user sees an intermediate state (e.g. tooltip flip). Produces a two-pass render the user never sees mid-state.
- DON'T reach for it by default — it **blocks paint** and hurts performance. Prefer `useEffect`; upgrade to `useLayoutEffect` only to kill a visible flicker.
- Errors on the server ("does nothing on the server"). For SSR, use `useEffect`, an `isMounted` flag, or `useSyncExternalStore`.

### `useEffectEvent` — non-reactive effect logic

- **Stable since React 19.2** (Oct 2025); imported from `react`. Not available in React 18 / 19.0 / 19.1 — on those, inline the latest value via a ref instead. Use `eslint-plugin-react-hooks@latest` so the linter never adds an Effect Event to a dep array.
- Purpose: read the **latest** props/state inside an effect without adding them as deps (e.g. a timer that shouldn't restart when a read-only value changes). Callable only inside effects; never list it in a dep array; never use it to hide a genuine dependency.

### React 19 note

- Actions / `useActionState` / `use` / RSC change data-flow and async, but do **not** replace effects for external-system sync. Data fetching still belongs in a framework loader or cache (TanStack Query, SWR) over hand-rolled fetch Effects.

### Sources

- https://react.dev/reference/react/useEffect
- https://react.dev/learn/you-might-not-need-an-effect
- https://react.dev/reference/react/useRef
- https://react.dev/reference/react/useLayoutEffect
- https://react.dev/reference/react/useEffectEvent
- https://react.dev/blog/2024/12/05/react-19

## Performance <a id="performance"></a>

Framework-specific render performance. Assumes JS/TS perf lore exists separately.
Verified against react.dev (React 19 current). Tie every optimization to a measurement.

### Profile first, optimize second

DO
- Measure before changing anything. Use React DevTools **Profiler** tab, or the `<Profiler id onRender>` component to capture `actualDuration` vs `baseDuration` programmatically.
- Profile a **production build** with CPU throttling. Dev/StrictMode renders twice and skews timings.
- Time a suspect calculation before memoizing: `console.time('x'); f(); console.timeEnd('x')`. Memoize only if it's ≥~1ms and runs on hot paths.

DON'T
- Don't sprinkle `memo`/`useMemo`/`useCallback` speculatively. "Might be slow" is not a measurement.
- Don't trust dev-mode timings — `<Profiler>` is disabled in prod by default (needs a profiling build).

### React Compiler (prefer over manual memo)

React Compiler auto-memoizes components, values, and functions at build time — more comprehensive than hand-written `memo`/`useMemo`/`useCallback`. Works best with **React 19**; also supports 17/18.

DO
- Prefer enabling the compiler over manual memoization on new code.
- Install per docs: `npm i -D babel-plugin-react-compiler@latest` and lint with `eslint-plugin-react-hooks@latest` (`recommended-latest` preset). React 19: zero config. React 17/18: add `react-compiler-runtime@latest` **and** set `target: '17' | '18'`.
- Once enabled, delete redundant manual `memo`/`useMemo`/`useCallback` — the compiler covers them.

DON'T
- Don't assume it's on. If the build isn't compiled, the manual rules below still apply.
- Don't fight the compiler with impure render logic — it optimizes correct, pure components.

### memo — skip re-render on unchanged props

`memo(Component)` skips re-render when props are shallow-equal (`Object.is` per prop). It's an optimization, not a guarantee; it does NOT stop re-renders from own state or context changes.

DO
- Apply `memo` only when a component **re-renders often with the same props** AND its render is expensive.
- Use it heavily on granular, high-frequency UI (canvas/editor items); rarely on coarse page/section swaps.

DON'T
- Don't wrap a component whose props are always new — `memo` then does nothing (see inline-props below).
- Don't write a custom `arePropsEqual` that skips comparing functions (stale-closure bugs) or does deep equality (can freeze the app).

### Inline object/array/function props break memo

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

### useMemo / useCallback — only three real reasons

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

### Reduce the NEED for memoization (structural fixes > memo)

DO
- Pass JSX via `children` so a stateful wrapper doesn't re-render subtrees it owns.
- Keep state **local**; don't lift it higher than needed.
- Keep render pure; remove unnecessary Effects and Effect deps (move objects/functions inside the Effect).

### Keys in lists

Keys let React match items across renders (reorder/insert/delete). Put the `key` on the element **directly inside `map()`**.

DO
- Use a **stable id from the data** (`item.id`, DB key, `crypto.randomUUID()` stored with the item).

DON'T
- Don't use the array **index** as key for lists that reorder/insert/delete — causes subtle state/DOM bugs (index-as-key is fine only for truly static lists).
- Don't use `key={Math.random()}` — keys never match, everything remounts each render, losing DOM state and input focus.
- `key` is not a prop; give the child the id separately if it needs it: `<Row key={id} id={id} />`. Use `<Fragment key>` (not `<>`) when an item renders multiple nodes.

### Code-splitting — lazy + Suspense

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

### Concurrent rendering — keep input responsive

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

### Sources
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

## Patterns & pitfalls <a id="patterns-and-pitfalls"></a>

Senior-reviewer checklist. JS/TS lore lives elsewhere; this is React-specific.

**Version anchor (verify against react.dev):** React 19 is the current stable major (Dec 2024). React 19.2 (Oct 2025) is the latest release line — added `<Activity>`, stabilized `useEffectEvent`, added `cacheSignal`. React 18 introduced concurrent rendering (`useTransition`, `useDeferredValue`, `useSyncExternalStore`, automatic batching). Tie every feature below to the version that introduced it.

---

### Composition over inheritance
React has no component inheritance. Compose.

- DO pass UI via `children`/render props for reuse; extract behavior into custom hooks, not base classes.
- DON'T subclass or stack HOCs where a hook or `children` suffices.
- DON'T prop-drill deeply — wrap with `children`, or use context for cross-cutting values (theme, auth). Context is not a state manager; overuse re-renders all consumers.

### Controlled vs uncontrolled inputs
- Controlled: value driven by state — `<input value={x} onChange={e => setX(e.target.value)} />`. Use when you validate, transform, or read on every keystroke.
- Uncontrolled: DOM holds the value — `<input defaultValue={x} ref={ref} />`, read via `ref.current.value`. Use for simple/perf-sensitive forms.
- DON'T mix: passing `value` without `onChange` (and non-null) makes a read-only field and warns. Use `defaultValue`/`defaultChecked` for uncontrolled.
- DON'T flip an input between controlled and uncontrolled across renders (value going `undefined`↔defined). Initialize state to `''`, not `undefined`.
- React 19: prefer form **Actions** + `useActionState` for submit flows; `<form action={fn}>` and `useFormStatus()` (from `react-dom`) for pending state.

### Lifting & colocating state
- DO keep state minimal (DRY). If a value is derivable from props/state, compute it in render — don't store it.
- DO colocate: put state in the lowest component that needs it. Only lift to the closest common parent when siblings must share it; hand setters down as props (one-way flow).
- DON'T copy props into state (`useState(props.x)`) to "sync" — that forks the source of truth. Derive, or lift the state up.
- DON'T `useEffect` to mirror one state into another; compute during render. (react.dev: "You Might Not Need an Effect".)

### Custom hooks for reuse
- DO extract stateful logic into `use*` functions; share logic, not state — each caller gets independent state. `use*` name lets the linter enforce rules of hooks.
- DON'T call hooks conditionally, in loops, or after early returns — same order every render.
- DON'T wrap pure helpers in a hook; only when it uses other hooks.

### Error boundaries
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

### Portals
`createPortal(children, domNode, key?)` (from `react-dom`) renders into a different DOM node (modals, tooltips escaping `overflow:hidden`).
- KEY: events bubble along the **React tree**, not the DOM tree; context still flows in. Stop propagation if a parent `onClick` catches portal clicks unexpectedly.
- DO manage focus/ARIA for dialogs (WAI-ARIA modal pattern).

---

### Pitfalls (the ones that ship bugs)

#### Mutating state
- DON'T mutate. `state.push(x)`, `obj.k = v`, `arr.sort()` won't re-render and corrupt snapshots.
- DO replace: `setArr([...arr, x])`, `setObj({...obj, k: v})`, `setArr(arr.toSorted())`. Mutating (`push/pop/sort/reverse/splice`) vs non-mutating (`map/filter/slice/concat/toSorted`).
- Local mutation of objects created **during this render** is fine.

#### setState in render / impurity
- DON'T call `setState`, mutate props/state, or do side effects during render. Rendering must be pure: same inputs → same JSX.
- Calling `setState` unconditionally in render is an infinite loop. Set state in event handlers or effects.
- StrictMode double-invokes components/initializers/updaters in dev to surface impurity — fix the impurity, don't silence it.

#### Stale closures
State/props are a per-render **snapshot**; closures capture the render's values.
- DON'T read state right after setting it — the variable doesn't change mid-function. `setCount(count+1); setCount(count+1)` increments once.
- DO use updater form for sequential/async updates: `setCount(c => c + 1)`.
- DON'T omit deps used inside `useEffect`/`useCallback` to "fix" re-runs — you get stale reads. Include all reactive deps (trust `eslint-plugin-react-hooks`).
- For logic that must read latest values without re-subscribing, use `useEffectEvent` (stable in React 19.2) — declare the event, call it from the effect, never list it as a dep. Pre-19.2: a `useRef` mirror of the latest value.

#### Missing / bad keys
- DO give siblings in a list stable, unique `key`s from data identity (`item.id`).
- DON'T use array `index` as key for reorderable/insertable lists — state/DOM misassociates. Index is acceptable only for static, append-only lists.
- DON'T use `Math.random()`/regenerated keys — remounts every render, loses state and focus.

#### Effect misuse
- DON'T use effects for derived data, event responses, or to transform props for render. Effects are for **external systems** (subscriptions, non-React widgets, network on mount).
- DO return a cleanup; expect effects to run twice on mount in dev StrictMode — cleanup must make that idempotent.

---

### RSC vs Client Components (React 19)
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

### React 19 API shifts (verify before using)
- `ref` is a regular prop on function components (React 19); `forwardRef` is **no longer needed** (still works; deprecation planned for a future version, not yet deprecated). `<Child ref={r} />` then read `props.ref`.
- `use(resource)` — read a Promise or context, callable conditionally (not a hook's ordering rules). React 19.
- `useOptimistic`, `useActionState` (react), `useFormStatus` (react-dom) — Actions/form flow. React 19.
- `<Context>` renders as its own Provider (`<Ctx value>`), no `.Provider` needed. React 19.
- `<Activity mode="visible|hidden">` to pre-render/hide subtrees keeping state. React 19.2.

### Sources
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
