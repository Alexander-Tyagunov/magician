# Vue — core digest

Version cue: Vue 3.5 (3.5.39) current; 3.6/Vapor in beta. Vue 2 EOL Dec 2023. New code: Composition API + `<script setup>` + SFC.

DO use `<script setup>` — top-level bindings auto-expose to template; hooks run synchronously (not after await).
DO `ref()` for any value (`.value` in JS, auto-unwrapped in template); `reactive()` for objects only.
DON'T destructure or reassign a `reactive()` object — reactivity is lost. (Props destructure IS reactive in 3.5+.)
DO `computed()` for cached derived state (readonly); no side effects inside.
DO prefer `watch()` (lazy, old+new) over `watchEffect()`; `{deep:true}` for nested, `{once}` (3.4+); `onWatcherCleanup()` (3.5+) called sync before any await.
DO declare `defineProps`/`defineEmits` (macros, no import); type-based OR runtime, not both. `defineModel()` (3.4+) for `v-model`.
DON'T mutate props; DON'T reference setup-local vars in macro options (hoisted).
DO give every `v-for` a stable `:key` (not index); DON'T put `v-if` + `v-for` on the same element.
DON'T reach for Options API `this`/`data()`/mixins in new code — extract composables.
DO `<style scoped>`; `:deep()` to pierce child styles.

Commands: scaffold `npm create vue@latest`; dev/build `vite`; typecheck `vue-tsc --noEmit`.

Deep dive when writing non-trivial vue — read lore/vue/{composition-and-reactivity,components-and-sfc,patterns-and-pitfalls}.md

Sources: vuejs.org/guide/introduction.html, /api/sfc-script-setup.html, /api/reactivity-core.html, github.com/vuejs/core/releases
