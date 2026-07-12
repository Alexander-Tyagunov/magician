# bootstrap — Customization & v5

Version cue: **v5.3.x** (current, e.g. 5.3.8). v5 = **no jQuery** (vanilla JS), `data-bs-*` attrs, Popper 2, dropped IE. v4 = jQuery + `data-*`. Color modes (`data-bs-theme`) landed in **v5.3.0**; navbar/container CSS vars in v5.2.0. Framework-agnostic CSS/JS (React/Vue/Angular/Svelte/plain). Customize via **Sass source**, not by editing dist.

## Setup / JS (DO)
- DO load `bootstrap.bundle.min.js` (Popper included) before `</body>`, or split Popper + `bootstrap.min.js`. Skip Popper only if no dropdowns/tooltips/popovers.
- DO instantiate with a selector: `new bootstrap.Modal('#m')`; `_getInstance()` → `getInstance()` in v5.
- DON'T ship jQuery or use `$('...').modal()` — gone. DON'T use `data-toggle`/`data-target`; it's `data-bs-toggle`/`data-bs-target`.
- DON'T reuse a CDN `integrity` hash across upgrades — it's per-file; regenerate on bump.

## Sass import order (DO — this is the whole game)
Overrides only take effect *before* Bootstrap consumes them (every var is `!default`).
```scss
@import "bootstrap/scss/functions";   // 1. first — enables color/map helpers
$primary: #0074d9;                     // 2. VARIABLE overrides here
$body-bg: #000;
@import "bootstrap/scss/variables";
@import "bootstrap/scss/variables-dark";
// 3. MAP overrides here (map-merge / map-remove)
@import "bootstrap/scss/maps";
@import "bootstrap/scss/mixins";
@import "bootstrap/scss/root";
@import "bootstrap/scss/reboot";       // 4. components you need
@import "bootstrap/scss/buttons";
@import "bootstrap/scss/utilities";
// 5. $utilities map-merge here
@import "bootstrap/scss/utilities/api"; // last — emits utility classes
```
- DO import only the parts you use (smaller CSS). `@import "bootstrap/scss/bootstrap"` pulls everything but disallows var overrides (functions load too late).
- DON'T put var overrides after `variables`, or map overrides after `maps` — silently ignored.
- DON'T remove `primary`/`success`/`danger` from `$theme-colors` — links/buttons/form states depend on them (changing values is fine).

## Sass maps (DO)
- DO edit theme colors as standalone vars (`$primary`, `$danger`); Bootstrap reassembles the map.
- DO add: `$theme-colors: map-merge($theme-colors, ("brand": #900));`
- DO remove (after `variables`, before `maps`): `$theme-colors: map-remove($theme-colors, "info", "light");`
- DO use `tint-color($c, 10%)` / `shade-color($c, 30%)`. DON'T use `lighten()`/`darken()` (v4-era) or `color-yiq()` → now `color-contrast()`.

## Global `$enable-*` flags (set before variables)
Default **on**: `$enable-rounded`, `$enable-transitions`, `$enable-grid-classes`, `$enable-container-classes`, `$enable-rfs`, `$enable-smooth-scroll`, `$enable-important-utilities`, `$enable-dark-mode`, `$enable-reduced-motion`, `$enable-validation-icons`.
Default **off**: `$enable-shadows`, `$enable-gradients`, `$enable-negative-margins`, `$enable-cssgrid`.
- DO flip these instead of writing overrides (`$enable-negative-margins: true` for `.m-n1`).
- DO set `$enable-important-utilities: false` if utility `!important` fights your CSS.

## Utility API — `$utilities` map (DO)
Generate/modify utility classes in Sass. Keys: `property` (req), `values` (req), `class`, `state` (hover/focus), `responsive`, `print`, `rtl`, `css-var`, `css-variable-name`, `local-vars`.
```scss
$utilities: map-merge($utilities, (
  "cursor": (property: cursor, class: cursor, responsive: true,
             values: auto pointer grab),
));
```
- DO modify an existing utility via nested merge:
```scss
"opacity": map-merge(map-get($utilities, "opacity"), (responsive: true)),
```
- DO remove: `map-remove($utilities, "float")` or set the key to `null`.
- DO merge **between** `utilities` and `utilities/api` imports — nowhere else.
- `class: null` → classes straight from value keys (`.visible`). `css-var: true` → emits `--bs-*` not rules.

## CSS variables (runtime, no recompile)
- All prefixed `--bs-` (change via `$prefix`). Root: `--bs-primary`, `--bs-primary-rgb`, `--bs-body-bg`, `--bs-body-color`, `--bs-border-radius`, `--bs-font-sans-serif`. Component-scoped: `--bs-card-bg`, `--bs-btn-color`, `--bs-navbar-*`, table vars.
- DO override per-scope: `.panel { --bs-card-bg:#222; }`; use RGB for alpha: `rgba(var(--bs-primary-rgb),.5)`.
- DON'T use `--bs-` vars inside `@media` breakpoint queries — CSS spec forbids custom props in media conditions. Use Sass breakpoints/JS instead.

## Color modes / dark (v5.3.0+)
- DO set `data-bs-theme="dark"` on `<html>` (global) or any element (scoped, e.g. a light navbar in a dark page). It swaps CSS vars via `[data-bs-theme=...]`.
- DO define custom modes: `[data-bs-theme="brand"]{ --bs-body-bg: … }`. Toggle in JS: `document.documentElement.setAttribute('data-bs-theme', t)` + persist in `localStorage`.
- DO add new theme colors to the emphasis/subtle maps for **both** modes (`$theme-colors-bg-subtle` + `-dark` variants) or alerts/list-groups break.
- Build behavior: `$color-mode-type: data` (default, per-component) vs `media-query` (auto via `prefers-color-scheme`, no toggle). `$enable-dark-mode: false` to drop it.

## RTL
- DO ship `bootstrap.rtl.min.css` + `<html dir="rtl" lang="ar">`. From source, RTL is generated by RTLCSS (PostCSS build), not a single `$enable-rtl` toggle in the public dist.
- DO rely on logical utilities — `ms-*/me-*` (start/end), `ps-*/pe-*`, `float-start/end`, `text-start/end`, `rounded-start/end` auto-flip. Set `rtl: false` on a custom utility to exclude it from RTL output.

## v4 → v5 migration (DON'T carry these over)
- Directional → logical: `ml-*/mr-*`→`ms-*/me-*`, `pl/pr`→`ps/pe`, `float-left/right`→`float-start/end`, `text-left/right`→`text-start/end`, `border-left/right`→`border-start/end`.
- Renamed: `font-weight-*`→`fw-*`, `font-italic`→`fst-italic`, `text-monospace`→`font-monospace`, `no-gutters`→`g-0`, `sr-only`→`visually-hidden`, `.close`→`.btn-close`, `.badge-pill`→`.rounded-pill`, `.custom-select`→`.form-select`.
- Dropped: **jumbotron**, `.media`, `.card-deck`/`.card-columns`, `.btn-block` (use `.d-grid`), `.badge-*` color classes (use `.bg-*`), `.form-group`/`.form-row`/`.form-inline`, `.input-group-prepend/append` (children now direct).
- Forms: `.custom-*` unified into `.form-check`/`.form-switch`/`.form-select`/`.form-range`; labels need `.form-label`; toggle buttons use `.btn-check` (no JS).
- Grid: new `xxl` breakpoint (1400px); gutters in rem (`.g-*/.gx-*/.gy-*`). `media-breakpoint-down(lg)` now means "< lg". JS: `whiteList`→`allowList`.

## Framework note
- CSS is framework-agnostic; import the Sass or link dist anywhere. For React components (not official Bootstrap), **react-bootstrap v2** targets Bootstrap 5 and is jQuery-free (v1 = Bootstrap 4). Style/customize via the same Sass vars — react-bootstrap ships no CSS.

## Sources
- https://getbootstrap.com/docs/5.3/getting-started/introduction/
- https://getbootstrap.com/docs/5.3/migration/
- https://getbootstrap.com/docs/5.3/customize/sass/
- https://getbootstrap.com/docs/5.3/customize/options/
- https://getbootstrap.com/docs/5.3/customize/css-variables/
- https://getbootstrap.com/docs/5.3/customize/color-modes/
- https://getbootstrap.com/docs/5.3/utilities/api/
