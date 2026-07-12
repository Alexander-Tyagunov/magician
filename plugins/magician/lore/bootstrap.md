# Bootstrap (core)

Version: current **v5.3.x** (dark mode) — prior major **v4** (jQuery). Migrating v4→v5: NO jQuery (vanilla JS); `data-toggle`→`data-bs-toggle`; RTL-safe utils (`ml-*`/`mr-*`→`ms-*`/`me-*`, `float-left`→`float-start`); `.no-gutters`→`.g-0`; `.custom-select`→`.form-select`; drops IE.

DO require `<!doctype html>` + viewport meta, or styling breaks.
DO load CSS in `<head>`, JS before `</body>`; use `bootstrap.bundle.min.js` (includes Popper).
DO instantiate JS with a selector: `new bootstrap.Modal('#m')`; skip separate Popper only if no dropdown/tooltip/popover.
DO dark mode via `data-bs-theme="dark"` on `:root`/wrapper/component (v5.3+).
DO customize via Sass — override maps between `@import "variables"` and `@import "maps"`.
DON'T use dropped-v4 markup: `.form-group`, `.btn-block` (→`.d-grid`), `.badge-pill` (→`.rounded-pill`), `.jumbotron`, `.media`, `.close` (→`.btn-close`).
DON'T use deprecated dark variants (`.navbar-dark`, `.dropdown-menu-dark`) — use `data-bs-theme` (v5.3).
DON'T use `.text-muted` (→`.text-body-secondary`) or `.sr-only` (→`.visually-hidden`).
DON'T edit `bootstrap.min.css`; override with Sass or CSS vars (`--bs-*`).

Commands: `npm i bootstrap@5.3.8` (or jsDelivr CDN); import `bootstrap/dist/css/bootstrap.min.css` + `bootstrap/dist/js/bootstrap.bundle.min.js`.

Deep dive when writing non-trivial bootstrap — read lore/bootstrap/{customization-and-v5}.md

Sources: getbootstrap.com/docs/5.3/getting-started/introduction, /migration
