# angular — Components, DI & signals

Current stable: **v22** (2026-06). Modern Angular = standalone + `inject()` + signals + built-in control flow. Detect the repo's version (`package.json` → `@angular/core`) and adapt. Never claim a feature earlier than the versions below.

## Verified version map (do not invent)

- `inject()` function — **v14**.
- Standalone components — dev preview **v14**, recommended authoring format **v17**, the **default v19+** (best-practices doc: default in v20+). Don't write `standalone: true`.
- `signal()` / `computed()` — dev preview v16, stable **v17**.
- Built-in control flow `@if`/`@for`/`@switch` — dev preview v17, **stable v18**.
- Deferrable views `@defer` — dev preview v17, stable v18.
- Signal inputs `input()` / `input.required()` — dev preview **v17.1**, stable v19.
- `output()` function — **v17.3**, stable v19.
- `model()` two-way — **v17.2**, stable v19.
- Signal queries `viewChild`/`contentChild`(`ren`) — dev preview v17.2/17.3, stable v19.
- `linkedSignal` — v19, stable **v20**. `resource()` — introduced v19, **stable since v22**.
- Full reactivity set (`signal`,`effect`,`linkedSignal`,queries,inputs) **graduated stable v20**.

## Components (standalone-first)

DO
- Author standalone. Import deps directly in the component's `imports: []`.
- Use `changeDetection: ChangeDetectionStrategy.OnPush` for every new component (mandatory with signals; enables zoneless).
- Keep template/styles in separate files for non-trivial components.

DON'T
- Don't add `standalone: true` on v19+ — it's the default and linted against.
- Don't create `NgModule`s for new features. NgModules are legacy; only touch them in pre-v15 code or when interop demands it. To interop a standalone component into an old NgModule, add it to that module's `imports`.

```ts
import { Component, ChangeDetectionStrategy, input } from '@angular/core';
@Component({
  selector: 'app-user-card',
  imports: [DatePipe],           // direct deps, no NgModule
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `{{ name() }} — {{ joined() | date }}`,
})
export class UserCard {
  name = input.required<string>();
  joined = input<Date>();
}
```

Bootstrap (v14+): `bootstrapApplication(App, { providers: [...] })` in `main.ts` — no `AppModule`.

## Dependency injection

DO
- Prefer `inject()` over constructor params (works in field initializers, cleaner for mixins/inheritance).
- Register app-wide singletons with `@Injectable({ providedIn: 'root' })` — tree-shakeable, no manual provider wiring.
- Register app config via `provide*` functions in `bootstrapApplication` providers: `provideRouter`, `provideHttpClient`, `provideAnimationsAsync`.
- Call `inject()` only in an **injection context** (field initializer, constructor, `runInInjectionContext`, route guards/resolvers, factory).

DON'T
- Don't call `inject()` in lifecycle hooks, callbacks, or after an `await` — throws "outside injection context". Capture it in a field first.
- Don't register a `root` service again in a component's `providers` unless you deliberately want a scoped instance.

```ts
@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);        // field-initializer injection
}
```

Component-scoped instance: put the token in the component's `providers: []`. Use `InjectionToken<T>` for non-class deps; multi-providers with `{ provide, useValue, multi: true }`.

## Signals (modern reactivity — default for state)

DO
- Model component state as `signal()`; derive with `computed()` (lazy + memoized). Read by calling: `count()`.
- Write with `.set(v)` or `.update(prev => …)`.
- Use `effect()` only for side effects to non-reactive APIs (logging, DOM, `localStorage`). Runs in an injection context; reads are tracked synchronously.
- Expose read-only state via `.asReadonly()`; escape tracking with `untracked()`.
- `linkedSignal({source, computation})` (v19+/stable v20) for writable state that resets from a source. `resource()` (introduced v19, **stable v22**) for async→signal.

DON'T
- No `.mutate()` — removed. Produce a new value (`update(a => [...a, x])`).
- Don't put async/`await` logic inside `effect()` and expect post-await reads to be tracked.
- Don't overuse `effect()` to sync state between signals — use `computed`/`linkedSignal`.
- Don't forget `OnPush`; without it signals still work but you lose the perf/zoneless win.
- RxJS interop: `toSignal()` / `toObservable()` from `@angular/core/rxjs-interop`. Prefer signals for view state, RxJS for streams/events.

```ts
count = signal(0);
double = computed(() => this.count() * 2);
inc() { this.count.update(c => c + 1); }
```

## Inputs / outputs

DO
- Signal inputs (v17.1+): `value = input(0)`, required `id = input.required<string>()`. Read as `this.value()`. Reactive, `computed`-friendly, no `ngOnChanges` needed.
- Two-way: `model()` (v17.2+): `checked = model(false)` → parent binds `[(checked)]`. Writable via `.set()`/`.update()`; auto-emits `checkedChange`.
- Outputs: `output()` function (v17.3+): `changed = output<T>()`; emit `this.changed.emit(v)`.
- Transform/alias: `input(0, { transform: booleanAttribute, alias: 'disabled' })`.

DON'T
- Don't mix decorator and signal styles arbitrarily. `@Input()`/`@Output()` remain supported (fine in older code) but prefer `input()`/`output()` for new work. Migrate with `ng generate @angular/core:signal-input-migration` / `output-migration`.
- `model()` does **not** support transforms.
- Required signal inputs error at **build time** if unbound — don't guard for `undefined`.

## Control flow (templates)

DO
- Use built-in `@if`/`@for`/`@switch` (stable v18+). `track` is **mandatory** in `@for` — use a stable id (`track item.id`); `$index` for static lists.
- Use `@empty` for empty collections; `@else`/`@else if`; `@switch`/`@case`/`@default`.
- Migrate legacy templates: `ng generate @angular/core:control-flow`.

DON'T
- Don't reach for `*ngIf`/`*ngFor`/`[ngSwitch]` in new v17+ code (still valid, needs `CommonModule`/`NgIf`/`NgFor` imports). Built-in flow needs **no imports**.
- Don't omit `track` (won't compile) or track by index on dynamic reorderable lists (breaks reuse).

```html
@for (u of users(); track u.id) {
  <app-user-card [name]="u.name" />
} @empty {
  <p>No users</p>
}
@if (loading()) { <spinner/> } @else { <content/> }
```

## Pre-v17 fallbacks
NgModules + `declarations`; constructor DI; `*ngIf`/`*ngFor` with `CommonModule`; RxJS/`@Input` `set` for reactivity (no signals < v16). Don't back-port `@if`, `input()`, `signal()` into those codebases.

## Sources
- https://angular.dev/overview
- https://angular.dev/guide/signals
- https://angular.dev/guide/components/inputs
- https://angular.dev/guide/templates/control-flow
- https://angular.dev/guide/di
- https://angular.dev/roadmap
- https://angular.dev/reference/releases
- https://angular.dev/reference/migrations/outputs
- https://angular.dev/assets/context/best-practices.md
