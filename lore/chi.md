# Chi — core digest

Version cue: chi v5 (`github.com/go-chi/chi/v5`); supports the 4 latest Go majors, 100% net/http-compatible — handlers/middleware are plain `http.Handler`. Since Go 1.22 stdlib ServeMux does method+wildcard routing; reach for chi when you need sub-routers, per-group middleware stacks, `Mount`, regexp/`*` params.

DO order middleware before routes via `r.Use`: `RequestID`, `Logger`, `Recoverer`, `Timeout`.
DO always mount `middleware.Recoverer` — turns handler panics into 500 with no crash or stack leak.
DO group routes: `r.Route("/api",…)`, `r.Group(…)` for a fresh stack, `r.With(mw).Get(…)` inline; read params via `chi.URLParam(r,"id")`.
DO set timeouts on `http.Server` (`ReadHeaderTimeout`,`WriteTimeout`,`IdleTimeout`) + `middleware.Timeout`; chi sets none.
DO validate/bind yourself (chi has none): decode + `go-playground/validator`; cap `http.MaxBytesReader`.
DON'T use `middleware.RealIP` — deprecated, IP-spoofable, mutates `RemoteAddr`; use a `ClientIPFrom*` middleware, read `GetClientIP(r)`.
DON'T rely on chi for CORS/secure headers — add `github.com/go-chi/cors`, explicit origins (never `*` with credentials).
DON'T leak internals — set a custom error responder; never echo panic/error text to clients.

Commands: `go get github.com/go-chi/chi/v5 github.com/go-chi/cors` · `go run .`

Deep dive when writing non-trivial chi — read lore/chi/{routing-and-middleware}.md

## Sources
github.com/go-chi/chi · pkg.go.dev/github.com/go-chi/chi/v5 · go-chi.io
