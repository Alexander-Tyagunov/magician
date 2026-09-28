# vue — deep dive

> On-demand companion to `lore/vue.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Composition API & reactivity](#composition-and-reactivity) · [Components & SFC](#components-and-sfc) · [Patterns & pitfalls](#patterns-and-pitfalls)

## Composition API & reactivity <a id="composition-and-reactivity"></a>

Vue 3 (current stable **3.5.x**; Vue 2 EOL 2023-12-31). For new SFC-based apps use **Composition API + `<script setup>`**. Options API is fine for build-less/progressive-enhancement pages, but new component logic should default to `<script setup>`. Reactivity is proxy-based; the mental model differs from React — mutate reactive state in place, don't replace it. Assume JS/TS lore lives separately.

### DO — author with `<script setup>` + Composition API

- DO put logic in `<script setup>`: top-level imports, vars, and functions are auto-exposed to the template. No `return {}`, no `setup()` boilerplate.
- DO prefer `ref()` as the primary state API — it holds any value (primitive or object) and survives destructuring/passing.
- DO access refs with `.value` in JS; templates **auto-unwrap top-level refs** only.
- DO group related state + logic into composables (`useX()` functions) instead of splitting by option type. That is the reuse story replacing mixins.

```vue
<script setup>
import { ref, computed } from 'vue'
const count = ref(0)
const double = computed(() => count.value * 2)   // .value in JS
function inc() { count.value++ }
</script>
<template><button @click="inc">{{ count }} / {{ double }}</button></template>
```

### `ref` vs `reactive`

- DO default to `ref`. Use `reactive()` only for objects you never reassign.
- DON'T reassign a `reactive` object — `state = reactive({...})` breaks tracking. Mutate properties, or use a `ref` and swap `.value`.
- DON'T destructure a `reactive` object or pass its primitive property — reactivity is lost. Use `toRefs(state)` (whole object → refs) or `toRef(state, 'key')` (one property).
- Know `reactive()` returns a **Proxy** (`proxy !== raw`); only the proxy is reactive. Proxy identity is stable. `reactive` can't hold primitives.
- Both `ref` and `reactive` are **deep** by default (nested objects proxied). Opt out with `shallowRef` / `shallowReactive` for large/immutable payloads.

```js
const state = reactive({ count: 0, user: { name: 'a' } })
let { count } = state          // ❌ disconnected
const { count } = toRefs(state) // ✅ count.value stays linked
```

### computed

- DO use `computed()` for derived state — it's cached and only re-evaluates when deps change. Don't call a plain function in template for derivation.
- DON'T mutate inside a computed getter or cause side effects; keep it pure.
- DO use writable computed (`{ get, set }`) when a derived value must be assignable (e.g. proxying a prop/model).

```js
const fullName = computed({
  get: () => `${first.value} ${last.value}`,
  set: v => { [first.value, last.value] = v.split(' ') }
})
```

### watch vs watchEffect

- DO use `watch(source, cb)` when you need the old value, an explicit source, or lazy (not-immediate) behavior. Source = ref, getter, reactive object, or array of these.
- DO use `watchEffect(cb)` when you want it to run immediately and auto-track every reactive dep read synchronously. No old value.
- DON'T `watch(obj.count, …)` a reactive property directly — pass a getter: `watch(() => obj.count, cb)`.
- `watch` is **shallow by default** — reassignment only. Pass `{ deep: true }` for nested mutations. Watching a `reactive` object *directly* is implicitly deep (and `newVal === oldVal`).
- Options: `{ immediate: true }`, `{ deep: true }` (or a **number** for max depth, 3.5+), `{ once: true }` (3.4+), `{ flush: 'pre' | 'post' | 'sync' }`. Use `flush: 'post'` (or `watchPostEffect`) to read updated DOM.
- Watchers created synchronously in setup auto-stop on unmount. Watchers created in async callbacks (`setTimeout`) do **not** — capture the returned stop handle and call it.

```js
watch(() => props.id, (id, prev) => load(id))          // getter + old value
watchEffect(() => console.log(count.value))             // auto-tracked, eager
```

### Reactivity caveats

- Destructuring `reactive` / plain assignment of a primitive severs the link — use `toRefs`/`toRef`.
- Refs auto-unwrap in templates **only as top-level properties** and as the final text interpolation. `object.id` in a template stays a ref; destructure first. Refs are **not** unwrapped inside reactive arrays or `Map`/`Set` — use `.value`.
- Replacing a whole reactive object loses reactivity; mutate in place.

### Props & emits (`defineProps` / `defineEmits`)

- These are **compiler macros** — available in `<script setup>` without import, compiled away. Don't import them.
- DO use either runtime declaration OR type-based, never both.
- DO type emits with the succinct tuple syntax (3.3+): `defineEmits<{ change: [id: number] }>()`.
- Defaults: use `withDefaults(defineProps<Props>(), {...})`. In **3.5+**, prefer **reactive props destructure with native defaults** — destructured vars stay reactive (compiler rewrites reads to `props.x`); mutable defaults need no function wrapper.

```ts
// 3.5+
const { msg = 'hi', items = [] } = defineProps<{ msg?: string; items?: string[] }>()
const emit = defineEmits<{ submit: [payload: Data] }>()
```

- DON'T mutate props. For two-way binding use `defineModel()` (**stabilized 3.4+**): returns a ref bound to `v-model`; `defineModel('count')` targets `v-model:count`. Avoid a `default` when the parent may not pass a value (de-sync risk).
- Other macros: `defineExpose({...})` (components are closed by default), `defineOptions({...})` (3.3+), `defineSlots<…>()` (3.3+, type-only).

### provide / inject

- DO use `provide(key, value)` / `inject(key)` to skip prop drilling; call `provide` synchronously in setup. App-wide: `app.provide(key, value)`.
- DO provide **refs** to keep injectors reactive (injected as-is, not unwrapped). Keep mutations in the provider — expose an updater function alongside the state.
- DO wrap with `readonly()` to prevent injector mutation.
- DO use `Symbol` keys (+ TS `InjectionKey<T>`) in libraries/large apps to avoid collisions; export from a keys module.
- Defaults: `inject('k', fallback)`; factory default `inject('k', () => new X(), true)`.

### Options → Composition mapping

| Options API | Composition API |
| --- | --- |
| `data()` | `ref` / `reactive` |
| `computed` | `computed()` |
| `watch` | `watch` / `watchEffect` |
| `methods` | plain functions |
| `mounted` | `onMounted()` |
| `provide/inject` opts | `provide()` / `inject()` |
| mixins | composables (`useX()`) |

`this` does not exist in `<script setup>`. Lifecycle hooks are imported (`onMounted`, `onUnmounted`, `onBeforeUnmount`, …) and registered synchronously.

### Sources

- https://vuejs.org/guide/introduction.html
- https://vuejs.org/guide/essentials/reactivity-fundamentals.html
- https://vuejs.org/guide/essentials/watchers.html
- https://vuejs.org/api/sfc-script-setup.html
- https://vuejs.org/guide/components/provide-inject.html
- https://vuejs.org/api/
- https://registry.npmjs.org/vue/latest (version 3.5.x)

## Components & SFC <a id="components-and-sfc"></a>

Vue 3 (Composition API + `<script setup>`) is the default. Version-adaptive: notes mark 3.3/3.4/3.5 features and Vue 2 fallbacks. Assumes JS/TS lore is separate.

### SFC + `<script setup>`

DO
- Default to `<script setup>` — least boilerplate, best TS inference. Top-level bindings auto-expose to template.
- Use compiler macros (no import): `defineProps`, `defineEmits`, `defineExpose`, and `defineModel` (3.4+), `defineOptions`/`defineSlots` (3.3+).
- Type props/emits with generics: `defineProps<{ id: number; label?: string }>()` and the succinct emit tuple form (3.3+): `defineEmits<{ change: [id: number] }>()`.
- Prop defaults: destructure defaults are reactive in 3.5+ — `const { msg = 'hi' } = defineProps<Props>()`. On ≤3.4 use `withDefaults(defineProps<Props>(), { msg: 'hi' })` (wrap array/object defaults in a factory fn).
- `defineExpose({...})` to surface members to a template ref — components are closed by default.

DON'T
- Don't mix runtime and type declaration in one `defineProps`/`defineEmits` — compile error.
- Don't reference local `setup` variables inside `defineProps`/`defineEmits`/`defineOptions` — they hoist to module scope (imports are fine).
- Don't mutate props. Emit an event or use `defineModel`.
- Don't reach for `useSlots()`/`useAttrs()` in templates — use `$slots`/`$attrs`. They're for script logic only.

### v-model (component)

Vue 3 default = `modelValue` prop + `update:modelValue` event (Vue 2 was `value`/`input`). `.sync` and the `model` option are removed — use `v-model:arg`.

DO (3.4+)
```vue
<!-- child -->
<script setup>
const model = defineModel()            // modelValue
const title = defineModel('title', { required: true })  // named
</script>
```
- Multiple bindings: `<C v-model:first-name="a" v-model:last-name="b" />` with a `defineModel('firstName')` each.
- Modifiers: `const [model, mods] = defineModel({ set: v => mods.trim ? v.trim() : v })`. Named-arg modifiers land as `arg + "Modifiers"` prop.

DON'T
- On ≤3.3, `defineModel` doesn't exist — declare the prop + `emit('update:modelValue', v)` manually, or use a writable computed.
- Don't set a `default` on `defineModel` unless the parent may omit the binding — it desyncs parent (`undefined`) vs child (default).

### Slots

DO
- Named slots via `<slot name="header">`; parent supplies `<template #header>` (`#` = `v-slot:` shorthand). Unnamed = `default`.
- Provide fallback: `<slot>Fallback</slot>` renders only when no content passed.
- Scoped slots: child does `<slot :row="item" />`, parent destructures `<template #row="{ row }">`.
- Guard optional regions with `v-if="$slots.header"`. Dynamic names: `<template #[name]>`.

DON'T
- Slot content compiles in the PARENT scope — it can't see child data except via scoped-slot props.
- Don't put `v-slot` on the component tag when also using named slots — use explicit `<template #default>` (mixing errors out).

### Lifecycle hooks (Composition API)

Call synchronously in `setup`/`<script setup>`. Import from `vue`.

`onBeforeMount` `onMounted` `onBeforeUpdate` `onUpdated` `onBeforeUnmount` `onUnmounted` `onErrorCaptured` `onActivated`/`onDeactivated` (KeepAlive) `onServerPrefetch` (SSR) `onRenderTracked`/`onRenderTriggered` (dev-only).

DO
- `onMounted` for DOM/refs and side effects; pair every subscription/timer with `onUnmounted` cleanup.
- `onErrorCaptured((err, inst, info) => false)` — return `false` to stop propagation.

DON'T
- Vue 3 renamed `beforeDestroy`→`onBeforeUnmount`, `destroyed`→`onUnmounted`. Don't use the old names.
- Don't register hooks in async callbacks/`await` — must be sync during setup.

### v-if vs v-show

- `v-if`: real conditional, mounts/unmounts (lazy, cheaper init, costlier toggle). Supports `v-else`/`v-else-if` and `<template>`.
- `v-show`: always rendered, toggles CSS `display` (cheaper toggle). No `<template>`, no `v-else`.
- DO use `v-show` for frequent toggles; `v-if` for rarely-changing conditions.

### v-for + key

DO
- Always bind a stable, unique, primitive `:key` (`item.id`) so Vue reorders instead of in-place patching stateful nodes.
- Put `:key` on `<template v-for>`, not the inner element.
- Filter with a computed, not inline `v-if`.

DON'T
- Don't use array index as key when the list reorders/filters/mutates — breaks form/component state.
- Don't put `v-if` + `v-for` on the same element. In Vue 3 `v-if` evaluates FIRST (Vue 2: `v-for` first), so `v-if` can't see the loop variable. Move `v-for` to a wrapping `<template>`.
- `v-for="n in 10"` starts at 1, not 0. Object form: `(value, key, index)`.

### Dynamic components

DO
- `<component :is="tab" />` — `is` takes a component (import ref) or, in-DOM templates, a registered name/string.
- Wrap in `<KeepAlive>` to preserve state of swapped components; use `onActivated`/`onDeactivated` there.

DON'T
- With `<script setup>`, `:is` needs the actual component in scope (imported), not a bare name string.

### Teleport

Vue 3.

DO
- `<Teleport to="body">…</Teleport>` for modals/overlays escaping `overflow`/`transform`/`z-index` ancestors. Logical tree (props/inject/events) unchanged.
- `:disabled` to render inline conditionally (e.g. mobile). Multiple teleports to one target append in order.
- `defer` (3.5+) when the target renders later in the same tick.

DON'T
- Target must exist in the DOM when Teleport mounts (unless `defer`).

### Async components & Suspense

DO
```js
const Comp = defineAsyncComponent(() => import('./Comp.vue'))
```
- Advanced: `{ loader, loadingComponent, delay: 200, errorComponent, timeout }`.
- Lazy hydration (3.5+, SSR only): `hydrate: hydrateOnVisible()` / `hydrateOnIdle()` / `hydrateOnInteraction('click')` / `hydrateOnMediaQuery(...)` — import each strategy for tree-shaking.
- `<Suspense>`: `#default` holds async children, `#fallback` shows while resolving.

DON'T
- `<Suspense>` is still experimental (API may change) — don't rely on it for critical prod flows without guarding.
- Don't wrap `defineAsyncComponent` call itself in the render — define it at module scope.

### Vue 2 fallbacks (only if on Vue 2)
- No `<script setup>`/Composition macros (unless `@vue/composition-api`). Use Options API: `data/computed/methods/props`.
- v-model = `value`/`input`; multiple bindings via `.sync`; rename via `model` option.
- Slots: legacy `slot`/`slot-scope` (deprecated) → `v-slot`. No Teleport/Suspense/`defineModel`.

### Sources
- https://vuejs.org/api/sfc-script-setup.html
- https://vuejs.org/guide/components/v-model.html
- https://vuejs.org/guide/components/slots.html
- https://vuejs.org/api/composition-api-lifecycle.html
- https://vuejs.org/guide/essentials/conditional.html
- https://vuejs.org/guide/essentials/list.html
- https://vuejs.org/guide/built-ins/teleport.html
- https://vuejs.org/guide/components/async.html
- https://vuejs.org/guide/built-ins/suspense.html

## Patterns & pitfalls <a id="patterns-and-pitfalls"></a>

Scope: Vue-specific guidance. Assume JS/TS lore lives elsewhere. Current stable: **Vue 3.5** (Vue 2 EOL 2023-12-31). Default to **Composition API + `<script setup>` + SFC** for apps; Options API is fine for build-less/low-complexity. Version-tag every feature below.

### Composables for reuse

DO
- Extract stateful logic into `useX()` composables returning refs/computed. Name `useMouse`, `useFetch`.
- Accept reactive inputs as **getters or refs**, then normalize with `toValue()` inside the composable so callers can pass a ref, getter, or plain value.
```js
export function useFetch(url) { // url: string | Ref | () => string
  const data = ref(null)
  watchEffect(() => { fetch(toValue(url)).then(/*...*/) }) // re-runs when url changes
  return { data }
}
```
- Register lifecycle/watchers **synchronously** at composable top level so they bind to the owner and auto-dispose.
- Return refs (not `reactive()` bundles); let callers destructure without losing reactivity.

DON'T
- Don't call composables conditionally or inside callbacks/`await` — lifecycle hooks and injections won't bind.
- Don't take a plain unwrapped value expecting it to stay reactive; a bare `url` string is a snapshot.

### State: Pinia, not Vuex

DO
- Use **Pinia** for new apps (official, Vue-core-maintained; Composition-style API, strong TS inference, devtools/HMR/SSR).
- Prefer setup stores: `defineStore('id', () => { const n = ref(0); ... return { n } })`.
- Destructure state with `storeToRefs(store)` to keep reactivity; call actions directly off the store.

DON'T
- Don't start new projects on **Vuex** — maintenance mode, no new features.
- Don't destructure state straight off the store (`const { n } = store`) — that drops reactivity. Use `storeToRefs`.
- Don't reach for a store when a composable or props/emit suffices.

### Avoiding reactivity loss

DO
- Keep access on the reactive source: `state.count`, `props.foo`, `store.n`.
- Use `toRefs(reactive_obj)` / `toRef()` to destructure a `reactive()` object without losing tracking.
- Pass reactive values into functions as getters (`() => x`) and read with `toValue()`.

DON'T
- Don't destructure a `reactive()` object directly — `const { count } = reactive({count:0})` yields a disconnected primitive.
- Don't spread/`Object.assign` a reactive object and expect reactivity to survive.
- Don't replace a `reactive` object wholesale via reassignment; mutate its properties or use a `ref`.

### Reactive Props Destructure (3.5)

DO (3.5+)
- Destructure `defineProps` freely — the compiler rewrites refs to `props.foo` in the same `<script setup>`. Native defaults work: `const { size = 'md' } = defineProps<{ size?: string }>()`.
- When passing a destructured prop to `watch`/composable, wrap in a getter: `watch(() => foo, cb)`, `useX(() => foo)`.

DON'T
- Don't assume this in **≤3.4** — there destructured props are static constants; use `props.foo` or `toRefs`.
- Don't do `watch(foo, cb)` — that watches a value, not a source (compiler warns).

### Prop mutation

DO
- Treat props as read-only (one-way down). Seed a local `ref(props.initial)` for editable initial values.
- Derive with `computed(() => props.size.trim())` for transforms.
- Emit an event (or `defineModel()`, stable 3.4) for two-way; let the parent own the write.

DON'T
- Don't assign to a prop (`props.foo = x`) — warns, and gets overwritten on parent re-render.
- Don't mutate nested fields of object/array props; Vue won't stop you but data flow breaks. Emit instead.

### Keys in v-for / v-if

DO
- Give `v-for` a **stable unique** `:key="item.id"`.
- Split `v-if` off `v-for`: filter via a `computed`, or move `v-if` to a wrapping `<template>`.

DON'T
- Don't use array **index** as key when the list reorders/inserts/deletes — causes state bleed and wrong patches.
- Don't put `v-if` and `v-for` on the same element — `v-if` has higher priority (3.x) and can't see the loop var.

### Watch cleanup & lifetime

DO
- Register async-side-effect cleanup. Two options:
  - `onWatcherCleanup(fn)` (**3.5+**) — must be called **synchronously**, before any `await`.
  - `onCleanup` arg — 3rd arg of `watch` cb, 1st arg of `watchEffect`; not subject to the sync constraint.
```js
watch(id, (n) => {
  const c = new AbortController()
  fetch(`/api/${n}`, { signal: c.signal })
  onWatcherCleanup(() => c.abort()) // aborts stale request on re-run/unmount
})
```
- Create watchers **synchronously** in setup so they auto-stop on unmount.
- Use `{ once: true }` (**3.4+**) for fire-once; `{ immediate: true }` to run eagerly.

DON'T
- Don't create watchers inside `setTimeout`/async callbacks without stopping them — they won't bind and leak. Capture the returned stop handle and call it, or keep the watch synchronous with a conditional body.
- Don't call `onWatcherCleanup()` after an `await` — it won't register.
- Don't blanket `{ deep: true }` on large objects; deep watch traverses everything. In **3.5+** cap with `deep: <number>` (max depth).

### Performance

DO
- `shallowRef()` / `shallowReactive()` for large immutable-ish payloads (big lists, API blobs); replace the whole `.value` to trigger, or `triggerRef()` after in-place edits.
- `v-memo="[a, b]"` (**3.2+**) on hot `v-for` rows (length ~>1000). Put it on the **same element** as `v-for`; `:key` is auto-inferred into the memo.
- `v-once` for truly static subtrees rendered once. `v-memo="[]"` ≡ `v-once`.
- Prefer `computed` over methods for cached derived values.

DON'T
- Don't under-specify the `v-memo` array — a missing dependency skips updates that should apply.
- Don't nest `v-memo` inside `v-for` (only works on the loop element itself).
- Don't deep-reactive-wrap large data you never mutate field-by-field — use `shallowRef`.

### Composition helpers (3.5)

DO
- `useTemplateRef('name')` (**3.5+**) for template refs instead of matching a same-named `ref`.
- `useId()` (**3.5+**) for SSR-stable unique ids (a11y `for`/`aria-*`).
- `useModel()` underlies `defineModel()`; prefer the `defineModel()` macro (**3.4 stable**).

DON'T
- Don't hand-roll SSR-safe id generation — hydration mismatches; use `useId()`.

### Sources
- https://vuejs.org/guide/introduction.html
- https://vuejs.org/api/
- https://vuejs.org/guide/essentials/watchers.html
- https://vuejs.org/guide/scaling-up/state-management.html
- https://vuejs.org/guide/components/props.html
- https://vuejs.org/api/built-in-directives.html
- https://pinia.vuejs.org
