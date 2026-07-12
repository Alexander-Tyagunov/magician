# react — Hooks & state

Framework-specific state lore. Assumes JS/TS lore lives elsewhere. Version facts verified against react.dev.

Version anchors: automatic batching → **React 18** (`createRoot`). Actions, `useActionState`, `useOptimistic`, `use`, `<Context>` as provider, ref-as-prop → **React 19** (stable 2024-12-05). Confirm the project's `react` version before using 19-only APIs; fall back to 18 patterns otherwise.

## Rules of Hooks (non-negotiable)

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

## useState

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

## useReducer

DO
- Prefer over `useState` when next state depends on non-trivial logic, or several values update together.
- Keep the reducer **pure** (no side effects, no async) — `(state, action) => newState`.
- Use lazy init: `useReducer(reducer, initialArg, init)`.

DON'T
- Put async or side effects in the reducer (that's what Actions / effects are for).

## Derived vs stored state

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

## Lifting state / composition

DO
- Lift shared state to the **closest common ancestor**; pass value + setter down as props.
- Prefer **passing JSX as `children`** to avoid prop-drilling through layers that don't use the data.

DON'T
- Duplicate the same source of truth in two siblings.
- Drill a prop through many intermediate components — extract components and pass `children` first.

```jsx
// ✅ Layout doesn't need posts; hand it children
<Layout><Posts posts={posts} /></Layout>
```

## Context — and when it re-renders

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

## Batching (React 18+)

DO
- Rely on **automatic batching** everywhere — event handlers, promises, `setTimeout`, native handlers all batch into one re-render (requires `createRoot`).
- Use `flushSync(() => setX(v))` only when you must read updated DOM synchronously (rare).

DON'T
- Assume N `setState` calls = N renders. Don't sprinkle `flushSync` to "force" order — use updater functions.

## React 19 Actions & async state

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

## `use(resource)` (React 19)

DO
- Read a **Promise** (component suspends; needs a `<Suspense>` boundary; errors hit the nearest Error Boundary) or **context**.
- Call it conditionally / after early returns — it is not a hook.
- Pass a **cached/stable** Promise (from a Server Component or a cache), not one created in render.

DON'T
- Wrap `use(promise)` in `try/catch` — use an Error Boundary.
- `use(fetch(...))` inline — new Promise every render → endless fallback. Reading context with `use` is unsupported in Server Components.

## Sources

- https://react.dev/reference/react/hooks
- https://react.dev/reference/rules/rules-of-hooks
- https://react.dev/reference/react/useState
- https://react.dev/reference/react/useActionState
- https://react.dev/reference/react/useOptimistic
- https://react.dev/reference/react/use
- https://react.dev/learn/passing-data-deeply-with-context
- https://react.dev/blog/2024/12/05/react-19
- https://react.dev/blog/2022/03/29/react-v18
