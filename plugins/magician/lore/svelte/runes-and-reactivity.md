# svelte — Runes & reactivity (Svelte 5)

Runes are `$`-prefixed compiler keywords (Svelte 5+, `.svelte`/`.svelte.js`/`.svelte.ts`). Not imported, not values — can't be assigned to a variable or passed as args. If the codebase uses `export let` / `$:` / `let x = 0` for reactive state, it's Svelte 4 (legacy) — match the surrounding style; don't mix modes in one file.

## Detect the version first

DO check `svelte` in `package.json`. `^5` → runes. `^4`/`^3` → legacy.
DON'T write runes in a Svelte 4 file or `$:` in a runes file. Runes mode is auto-enabled once any rune appears in a component.

## $state — reactive state

DO: `let count = $state(0)`. Read/write like a plain variable: `count++`.
DO rely on deep reactivity for arrays/plain objects — they become recursive proxies; `todos[0].done = true` and `arr.push(x)` trigger granular updates.
DO use `$state` in class fields: `class Todo { done = $state(false); text = $state(''); }`.
DO use `$state.raw(...)` for large/immutable data you only ever reassign (perf) — mutating properties does nothing; replace the whole value: `person = {...person, age: 50}`.
DO use `$state.snapshot(value)` before passing proxied state to external libs / `structuredClone` / `postMessage`.
DO use reactive builtins from `svelte/reactivity` (`SvelteMap`, `SvelteSet`, `SvelteDate`, `SvelteURL`) — raw `Map`/`Set` aren't reactive.

DON'T destructure reactive state and expect reactivity — `let { a } = obj` captures the value at that point (plain JS).
DON'T pass a class method as a handler bare: `onclick={todo.reset}` loses `this`. Use `onclick={() => todo.reset()}` or an arrow class field `reset = () => {...}`.
DON'T export a reassigned `$state` from a `.svelte.js` module — export an object and mutate its properties, or expose getter functions.

## $derived — computed state

DO: `let doubled = $derived(count * 2)`. Recomputed lazily (push-pull) when a synchronously-read dependency changes.
DO use `$derived.by(() => {...})` for multi-statement logic. `$derived(x)` ≡ `$derived.by(() => x)`.
DO reassign a derived for optimistic UI (Svelte 5.25+, non-`const`): the override holds until a dependency changes and recomputes it.

DON'T put side effects or state mutations inside `$derived` — the compiler forbids it.
DON'T reach for `$effect` to compute a value — that's what `$derived` is for.

## $effect — side effects (escape hatch, use sparingly)

Runs after mount, browser-only (never during SSR), batched in a microtask after DOM updates. Auto-tracks `$state`/`$derived`/`$props` read **synchronously** in its body.

DO use for genuinely external work: third-party libs, canvas drawing, manual DOM, analytics, subscriptions.
DO return a teardown function — runs before each re-run and on destroy: `$effect(() => { const id = setInterval(f); return () => clearInterval(id); })`.
DO use `$effect.pre(() => {...})` to run *before* DOM updates (e.g. capture scroll position).

DON'T use `$effect` to sync/derive state (`$effect(() => doubled = count * 2)`) — use `$derived`. This is the #1 misuse (like React `useEffect` overuse).
DON'T write to state you also read in the same effect → infinite loop; if unavoidable, wrap the read in `untrack(() => ...)` (from `svelte`).
DON'T rely on values read after `await` or inside `setTimeout` — async reads are NOT tracked as dependencies.
DON'T expect property-level tracking on a bare object — an effect reruns when the object reference it read changes, per the values read on the last run (conditional branches change deps).
`$effect.root(fn)` and `$effect.tracking()` are advanced (manual scopes / library authoring) — skip unless required.

## $props — component inputs

DO: `let { adjective = 'happy', ...rest } = $props();`. Fallbacks apply when the prop is missing/`undefined`.
DO rename reserved words: `let { super: trouper } = $props()`.
DO type them (TS): `let { adjective }: { adjective: string } = $props()`, or an `interface Props {...}`. Type `children` and snippets with `Snippet` from `'svelte'`.
DO use `$props.id()` (5.20.0+) for SSR-stable unique ids linking `<label for>`/`<input id>`.

DON'T mutate props — fallbacks aren't reactive proxies; use callbacks or `$bindable`.

## $bindable — opt-in two-way prop

DO mark a prop bindable in the child: `let { value = $bindable() } = $props()` (fallback: `$bindable('x')`). Parent binds: `<Child bind:value={message} />`.
DON'T overuse — it makes data flow hard to trace. Prefer one-way props + callback events. Binding is optional; a normal prop still works.

## Svelte 4 → 5 migration map

| Svelte 4 (legacy) | Svelte 5 (runes) |
|---|---|
| `let count = 0` | `let count = $state(0)` |
| `$: sum = a + b` | `let sum = $derived(a + b)` |
| `$: { total = 0; for (…) total += … }` | `let total = $derived.by(() => {…})` |
| `$: console.log(x)` (side effect) | `$effect(() => console.log(x))` |
| `export let name` | `let { name } = $props()` |
| `export let value` + `bind:value` | `let { value = $bindable() } = $props()` |

Legacy `$:` gotchas (why runes exist): compile-time deps miss values read only inside called functions; indirect ordering can leave stale values; `$:` runs during SSR (guard browser-only code).

## Stores (svelte/store) — de-emphasized, NOT deprecated

DO prefer runes for cross-component shared state in Svelte 5: export a `$state` object from `.svelte.js`/`.svelte.ts` and mutate it (universal reactivity), instead of `writable`.
DO keep/adopt stores for complex async streams, manual update control, or RxJS interop — they still work.
DO use `$store` auto-subscription in components (top-level only; auto-unsubscribes). `writable(v)`→`.set`/`.update`; `readable`; `derived`; `get(store)` (avoid in hot paths — it sub/reads/unsubs each call).
DON'T `$`-prefix non-store locals; DON'T declare a store subscription inside an `if`/function.

## Sources

- https://svelte.dev/docs/svelte/what-are-runes
- https://svelte.dev/docs/svelte/$state
- https://svelte.dev/docs/svelte/$derived
- https://svelte.dev/docs/svelte/$effect
- https://svelte.dev/docs/svelte/$props
- https://svelte.dev/docs/svelte/$bindable
- https://svelte.dev/docs/svelte/legacy-reactive-assignments
- https://svelte.dev/docs/svelte/stores
