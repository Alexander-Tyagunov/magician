# Echo (Go) — core digest

DO put `middleware.Recover()` first; it logs stacks to the server log, NOT the client. Keep `e.Debug=false` in prod.
DO bind THEN validate: `c.Bind(&dto)` (400 on bad body); wire `e.Validator` + `c.Validate(&dto)` — Bind never validates.
DON'T `Bind` into entity structs (mass-assignment, e.g. `IsAdmin`); bind a DTO. Headers need `echo.BindHeaders`, not `Bind`.
DO add `middleware.Secure()` (nosniff, X-Frame, XSS; HSTS via `HSTSMaxAge`), `BodyLimit("2M")`.
DO set CORS deliberately: `AllowOrigins` mandatory; NEVER `*`+`AllowCredentials:true` — Echo panics. List origins.
DO set timeouts on your own `*http.Server` + `e.StartServer(s)`; Echo exposes none. `middleware.Timeout()` won't cancel a stuck handler — honor `c.Request().Context()`.
DO group middleware via `e.Group(prefix, mw...)`; radix routing, priority static>param(`:id`)>wildcard(`*`).
WHY over net/http: Go 1.22 ServeMux routes method+wildcard — pick Echo for groups, middleware suite, bind+validate, not routing alone.

Version: v4.15.4 latest v4 (encoded-path hardening; the %2F GHSA-vfp3 fix landed in v4.15.3). v5 is GA (`labstack/echo/v5`, v5.2.x): `*echo.Context` struct, slog, generic binders. v4 supported to 2026-12-31.

Commands: `go get github.com/labstack/echo/v4` · `go run .` · `go test ./...`

Deep dive when writing non-trivial echo — read lore/echo/{routing-middleware-binding}.md

## Sources
echo.labstack.com/{guide/binding,middleware/secure,middleware/cors,middleware/recover} · pkg.go.dev/labstack/echo/v4 & v5 · github.com/labstack/echo/releases
