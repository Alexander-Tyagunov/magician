# Angular — core lore

Version: Angular v22 (2026); supported 22/21/20. Standalone is default since v19 (omit `standalone`); signals stable since v17; built-in control flow + `@defer` stable since **v18**.

DO
- Standalone components/directives/pipes; list deps in `imports:`. Don't author new NgModules.
- `inject()` over constructor params; valid in field initializers.
- Signals for state: `signal()`, `computed()`, `effect()`. Read by calling `x()`; write `x.set()/x.update()`.
- Signal I/O: `input()`, `input.required()`, `output()`, `model()` (two-way) over `@Input/@Output`.
- Template control flow `@if/@for/@switch/@defer`; `@for` MUST have `track`.
- `ChangeDetectionStrategy.OnPush`. Bootstrap `bootstrapApplication(App,{providers:[provideRouter(...),provideHttpClient()]})`.
- Clean up RxJS: `async` pipe, `toSignal()`, or `takeUntilDestroyed()`.

DON'T
- No `*ngIf/*ngFor` in new code — use `@if/@for`.
- Signals have no `.mutate` (removed) — use `.update()`; never set a signal inside `computed()`.
- Don't reach for `effect()` when `computed()` derives the value.
- No NgModule-based lazy routes — use `loadComponent`. No `any`.
- Don't subscribe without teardown; keep heavy work out of constructors.

Commands: `ng new`, `ng generate component x`, `ng serve`, `ng build`, `ng test`, `ng update`.

Deep dive when writing non-trivial angular — read lore/angular/{components-di-and-signals,rxjs-and-async,patterns-and-pitfalls}.md

## Sources
angular.dev/overview, /reference/versions, /reference/migrations/{outputs,inject-function}; context7 /angular/angular
