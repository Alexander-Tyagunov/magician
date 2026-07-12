# vue — Composition API & reactivity

Vue 3 (current stable **3.5.x**; Vue 2 EOL 2023-12-31). For new SFC-based apps use **Composition API + `<script setup>`**. Options API is fine for build-less/progressive-enhancement pages, but new component logic should default to `<script setup>`. Reactivity is proxy-based; the mental model differs from React — mutate reactive state in place, don't replace it. Assume JS/TS lore lives separately.

## DO — author with `<script setup>` + Composition API

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

## `ref` vs `reactive`

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

## computed

- DO use `computed()` for derived state — it's cached and only re-evaluates when deps change. Don't call a plain function in template for derivation.
- DON'T mutate inside a computed getter or cause side effects; keep it pure.
- DO use writable computed (`{ get, set }`) when a derived value must be assignable (e.g. proxying a prop/model).

```js
const fullName = computed({
  get: () => `${first.value} ${last.value}`,
  set: v => { [first.value, last.value] = v.split(' ') }
})
```

## watch vs watchEffect

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

## Reactivity caveats

- Destructuring `reactive` / plain assignment of a primitive severs the link — use `toRefs`/`toRef`.
- Refs auto-unwrap in templates **only as top-level properties** and as the final text interpolation. `object.id` in a template stays a ref; destructure first. Refs are **not** unwrapped inside reactive arrays or `Map`/`Set` — use `.value`.
- Replacing a whole reactive object loses reactivity; mutate in place.

## Props & emits (`defineProps` / `defineEmits`)

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

## provide / inject

- DO use `provide(key, value)` / `inject(key)` to skip prop drilling; call `provide` synchronously in setup. App-wide: `app.provide(key, value)`.
- DO provide **refs** to keep injectors reactive (injected as-is, not unwrapped). Keep mutations in the provider — expose an updater function alongside the state.
- DO wrap with `readonly()` to prevent injector mutation.
- DO use `Symbol` keys (+ TS `InjectionKey<T>`) in libraries/large apps to avoid collisions; export from a keys module.
- Defaults: `inject('k', fallback)`; factory default `inject('k', () => new X(), true)`.

## Options → Composition mapping

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

## Sources

- https://vuejs.org/guide/introduction.html
- https://vuejs.org/guide/essentials/reactivity-fundamentals.html
- https://vuejs.org/guide/essentials/watchers.html
- https://vuejs.org/api/sfc-script-setup.html
- https://vuejs.org/guide/components/provide-inject.html
- https://vuejs.org/api/
- https://registry.npmjs.org/vue/latest (version 3.5.x)
