# chi — Routing & middleware (stdlib-first)

Verified against chi **v5.3.1** (2026-07-06). Import `github.com/go-chi/chi/v5`.
chi is a Patricia-radix-trie router that is **100% `net/http`-compatible**: `*Mux`
implements `http.Handler`, and every middleware is a plain
`func(http.Handler) http.Handler`. No non-stdlib deps. Assumes the Go / `net/http`
lore lives elsewhere — this covers chi-specifics only.

## When chi earns its keep over stdlib (Go 1.22+)

Since Go 1.22, `net/http.ServeMux` does method + wildcard routing natively:
`mux.HandleFunc("GET /items/{id}", h)`, read with `r.PathValue("id")`,
`{rest...}` for trailing segments, precedence by pattern specificity.

- **DON'T** add chi for a handful of `METHOD /path/{id}` routes — stdlib `ServeMux` suffices.
- **DO** reach for chi when you need a **composable middleware stack** (`Use`),
  **nested sub-routers/groups** with per-group middleware, `Mount`, regex path
  params, or `Walk`-based route introspection. That is chi's actual value-add.
- **DON'T** jump to a heavyweight framework (Gin/Echo/Fiber) when chi + stdlib
  covers it — chi keeps handlers as ordinary `http.HandlerFunc`.

## DO — routing

```go
r := chi.NewRouter()               // *Mux, implements http.Handler
r.Get("/health", healthHandler)    // Get/Post/Put/Delete/Patch/Head/Options...
r.Method("REPORT", "/x", h)        // arbitrary verb; RegisterMethod first for custom
http.ListenAndServe(":3000", r)
```

- **DO** read params with `chi.URLParam(r, "id")` (pattern `/users/{id}`), or
  `chi.URLParamFromCtx(ctx, "id")` when you only hold the context.
- **DO** use regex params when you need validation at the router:
  `/date/{yyyy:\d\d\d\d}/{mm:\d\d}`. RE2 syntax; `/` never matches inside a param.
- **DO** capture the tail with `*`: pattern `/files/*` → `chi.URLParam(r, "*")`.
- **DO** set fallbacks: `r.NotFound(fn)` (default 404) and
  `r.MethodNotAllowed(fn)` (default 405, empty body).
- **DON'T** rely on implicit trailing-slash handling — `/user` and `/user/` are
  distinct. Normalize with `middleware.StripSlashes` or `RedirectSlashes`.

## DO — sub-routers, groups, mount

```go
r.Route("/api/v1", func(r chi.Router) {   // sub-router along a prefix
    r.Use(authRequired)                   // scoped middleware
    r.Route("/users", func(r chi.Router) {
        r.Get("/", listUsers)
        r.Get("/{id}", getUser)
    })
})

r.Group(func(r chi.Router) {              // fresh mw stack, no new prefix
    r.Use(rateLimit)
    r.Post("/upload", upload)
})

r.With(adminOnly).Delete("/{id}", del)   // inline mw for ONE endpoint
r.Mount("/debug", middleware.Profiler()) // attach any http.Handler subtree
```

- `Route` = mount a sub-router on a prefix. `Group` = inline router with its own
  middleware stack, same prefix. `With` = per-endpoint middleware.
- **DON'T** `Mount` two handlers on the **same** pattern — it **panics**.
- **DON'T** put `r.Use(...)` after routes are registered on that router — add
  middleware before defining the routes it should wrap.

## DO — middleware stack (order matters)

```go
r.Use(middleware.RequestID)                 // adds request id to ctx
r.Use(middleware.Logger)                    // log BEFORE response-altering mw
r.Use(middleware.Recoverer)                 // recover panics -> 500
r.Use(middleware.Timeout(60 * time.Second)) // constructor: takes time.Duration
```

- `Use` middlewares run **before route matching**, so they can short-circuit.
- **DO** order `RequestID` → `Logger` → `Recoverer`. Logger must precede any
  middleware that changes the response (per official docs).
- **Direct** middlewares pass straight to `Use` (`Logger`, `Recoverer`,
  `RequestID`, `StripSlashes`, `GetHead`, `NoCache`, `CleanPath`, `URLFormat`).
  **Constructors** must be **called** first: `Timeout(d)`, `Compress(5, ...)`,
  `Throttle(n)`, `Heartbeat("/ping")`, `SetHeader(k,v)`, `AllowContentType(...)`.

## Security

- **DO** always run `middleware.Recoverer` — it recovers panics, logs a
  backtrace, and returns **500** (never leaks the panic to the client body). It
  prints the `RequestID` when present. Keep it high in the stack.
- **DON'T** ship the panic stack to clients. Recoverer already replies with a
  bare 500; don't add handlers that echo `recover()` output.
- **DO** enforce timeouts. `middleware.Timeout(d)` cancels the request `ctx` and
  returns **504** — but you **must** `select` on `ctx.Done()` in slow handlers or
  the cancellation is ignored. Also set server-level `ReadTimeout`,
  `WriteTimeout`, `IdleTimeout` on `http.Server` (chi does not do this).
- **DON'T** use `middleware.RealIP` — **deprecated in v5.3.0** as spoofable (it
  trusts client-supplied `X-Forwarded-For`/`X-Real-IP`/`True-Client-IP` and
  mutates `r.RemoteAddr`). Use the infra-appropriate replacement:
  `ClientIPFromRemoteAddr` (direct exposure), `ClientIPFromHeader("...")`
  (single trusted proxy), `ClientIPFromXFF(...)` / `ClientIPFromXFFTrustedProxies(n)`
  (known proxy chain); read via `GetClientIP` / `GetClientIPAddr`.
- **DO** restrict bodies with `middleware.AllowContentType("application/json")`
  and gate with `middleware.Throttle(n)` for backpressure.
- **NOTE** chi has **no built-in CORS or validation**. Use `go-chi/cors`
  (configure origins/methods deliberately — never `*` with credentials) and a
  validator (e.g. `go-playground/validator`) after decoding + binding input.
- **DO** set secure response headers explicitly via `middleware.SetHeader` or a
  dedicated headers middleware; chi ships none by default.

## Observability

- **DO** read the matched pattern for metrics with
  `chi.RouteContext(r.Context()).RoutePattern()` — but only **after**
  `next.ServeHTTP`, because the value is built up during routing and changes
  mid-execution.
- **DO** enumerate registered routes with `chi.Walk(r, fn)`.

## Common patterns

- **DON'T** hand-roll JSON error/response plumbing — `go-chi/render` pairs with
  chi for content negotiation and `render.JSON`.
- **DO** version by mounting: `r.Mount("/v1", v1Router)`; each version is an
  independent `*Mux` with its own middleware.

## Sources

- https://github.com/go-chi/chi
- https://pkg.go.dev/github.com/go-chi/chi/v5
- https://pkg.go.dev/github.com/go-chi/chi/v5/middleware
- https://go.dev/blog/routing-enhancements
- https://pkg.go.dev/net/http#ServeMux
