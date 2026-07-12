# react — Effects & refs

Effects synchronize a component with an **external system** (network, DOM node, timer, subscription, non-React widget). They are an escape hatch, not the default. Refs hold mutable values that must survive renders but must **not** drive rendering. Covers React 18 & 19; javascript/typescript lore lives separately.

## DO — reach for `useEffect` only to synchronize with external systems

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

## DON'T — use an Effect to derive data or run event logic

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

## Dependencies — obey the linter

- DON'T suppress `react-hooks/exhaustive-deps`. Removing a dep means *proving* it's non-reactive, not silencing the warning.
- To drop a dep: use the updater form `setCount(c => c + 1)` (drops `count`); move constants **outside** the component; create objects/functions **inside** the effect so their identity isn't a dep.
- Object/function deps created during render change identity every commit → effect over-fires. Define them inside the effect or memoize.
- `[]` = run once after mount; `[a,b]` = run when a dep changes; omitted = run after **every** commit.

## StrictMode double-invoke (dev only)

- React 18+ Strict Mode runs **setup → cleanup → setup** on mount in development to surface missing/asymmetric cleanup. Production runs once.
- This is a **feature, not a bug**: if a double-invoke breaks something (double connections, doubled timers, duplicate fetches), your cleanup is wrong. Fix cleanup — don't add a "ran once" ref guard.
- Effects run **client-only** — never during SSR.

## `useRef` — mutable, non-rendering values

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

### React 19 ref changes

- **`ref` is a plain prop** for function components. No `forwardRef`:

```js
function MyInput({ ref, ...props }) { return <input ref={ref} {...props} />; }
```

  `forwardRef` still works in 19 but is slated for deprecation. Pre-19: keep using `forwardRef`.
- **ref callbacks may return a cleanup**: `ref={node => { ...; return () => {...}; }}`. When a cleanup is returned, React no longer calls the ref with `null` on unmount.
- Avoid implicit-return ref callbacks — `ref={n => (inst = n)}` returns a value TS now rejects. Use a block body: `ref={n => { inst = n; }}`.

## `useLayoutEffect` — measure before paint

- Fires **synchronously before the browser repaints**; state updates inside are flushed before paint. Use only to measure DOM layout and re-render before the user sees an intermediate state (e.g. tooltip flip). Produces a two-pass render the user never sees mid-state.
- DON'T reach for it by default — it **blocks paint** and hurts performance. Prefer `useEffect`; upgrade to `useLayoutEffect` only to kill a visible flicker.
- Errors on the server ("does nothing on the server"). For SSR, use `useEffect`, an `isMounted` flag, or `useSyncExternalStore`.

## `useEffectEvent` — non-reactive effect logic

- **Stable since React 19.2** (Oct 2025); imported from `react`. Not available in React 18 / 19.0 / 19.1 — on those, inline the latest value via a ref instead. Use `eslint-plugin-react-hooks@latest` so the linter never adds an Effect Event to a dep array.
- Purpose: read the **latest** props/state inside an effect without adding them as deps (e.g. a timer that shouldn't restart when a read-only value changes). Callable only inside effects; never list it in a dep array; never use it to hide a genuine dependency.

## React 19 note

- Actions / `useActionState` / `use` / RSC change data-flow and async, but do **not** replace effects for external-system sync. Data fetching still belongs in a framework loader or cache (TanStack Query, SWR) over hand-rolled fetch Effects.

## Sources

- https://react.dev/reference/react/useEffect
- https://react.dev/learn/you-might-not-need-an-effect
- https://react.dev/reference/react/useRef
- https://react.dev/reference/react/useLayoutEffect
- https://react.dev/reference/react/useEffectEvent
- https://react.dev/blog/2024/12/05/react-19
