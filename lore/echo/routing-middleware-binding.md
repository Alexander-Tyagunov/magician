# echo — Routing, middleware & binding

Framework-specific lore. Assumes Go + `net/http` foundation lore exists separately.

**Version pin (verify before use):** Echo **v5** is the current GA release line (`labstack/echo/v5`, v5.2.x since early 2026). **v4** (latest `v4.15.4`, Jun 2026, `echo.Version` constant) is now the **maintenance** line — security + bug fixes only, through 2026-12-31. This file teaches v4 (still fully supported); import `github.com/labstack/echo/v4` and `github.com/labstack/echo/v4/middleware`.

**v5 status:** v5 is the current GA release line (v5.2.x, tagged Latest) — choose it for new projects; v4 remains supported through 2026-12-31 for existing apps. v5 is a breaking rewrite: handler becomes `func(c *echo.Context) error` (pointer) vs v4's `func(c echo.Context) error` (interface); shutdown moves to `echo.StartConfig{}.Start(ctx, e)`. **Everything below is v4.** The live docs site (echo.labstack.com) now documents v5 — cross-check the interface-vs-pointer signature when copying examples.

## When Echo earns its keep over stdlib

Since Go 1.22, `net/http.ServeMux` does method + `{wildcard}` routing. Reach for Echo for: route groups with shared middleware, the broad built-in middleware set (CORS/Gzip/Secure/Recover/RateLimiter), unified `c.Bind`+validate, and centralized error handling. For a handful of routes, stdlib is enough — don't add Echo for ceremony.

## Routing

DO
- `e := echo.New()` then register: `e.GET("/users/:id", getUser)`. Signature: `e.GET(path, HandlerFunc, ...MiddlewareFunc) *Route`. Handler: `func(c echo.Context) error`.
- Read params with `c.Param("id")`; query with `c.QueryParam("q")`.
- Wildcard: register `/static/*`, read the tail via the literal key `c.Param("*")`.
- Group shared-prefix routes + middleware: `g := e.Group("/api/v1", authMW)`; groups nest.
- Use `e.Any(path, h)` / `e.Match([]string{...}, path, h)` for multi-method.

```go
e := echo.New()
e.GET("/users/:id", func(c echo.Context) error {
    return c.JSON(http.StatusOK, map[string]string{"id": c.Param("id")})
})
e.GET("/files/*", func(c echo.Context) error {
    return c.String(http.StatusOK, c.Param("*")) // path tail
})
admin := e.Group("/admin", middleware.BasicAuth(check))
admin.GET("/metrics", metrics) // -> /admin/metrics
```

DON'T
- Don't expect param routes to shadow static: priority is **static → param → wildcard**; `/users/profile` always beats `/users/:id`. Read the wildcard tail only via `"*"`.

## Middleware

`type MiddlewareFunc func(next echo.HandlerFunc) echo.HandlerFunc`. Register globally with `e.Use(...)`, per-group/route by passing as trailing args. `e.Pre(...)` runs **before** routing (path rewrites, trailing-slash) — most middleware belongs in `e.Use`.

DO — order matters; put `Recover` early and logging outermost.
```go
e.Use(middleware.Recover())                 // panics -> HTTPErrorHandler, not a dead conn
e.Use(middleware.RequestLoggerWithConfig(middleware.RequestLoggerConfig{...})) // structured (slog)
e.Use(middleware.Gzip())
e.Use(middleware.Secure())                  // sane security headers (XFO, HSTS-ready, etc.)
e.Use(middleware.BodyLimit("1M"))           // cap request bodies
e.Use(middleware.CORSWithConfig(middleware.CORSConfig{
    AllowOrigins: []string{"https://app.example.com"},
    AllowMethods: []string{http.MethodGet, http.MethodPost},
}))
```
- Custom middleware: `func(next echo.HandlerFunc) echo.HandlerFunc { return func(c echo.Context) error { /* ... */ return next(c) } }`.

DON'T
- Don't pair `AllowCredentials: true` with `AllowOrigins: ["*"]` — CORS default is `*`; that combo is a credential leak. Set an explicit origin allowlist.
- Don't use bare `middleware.Logger()` (deprecated) — use `RequestLogger`. Don't use `middleware.Timeout()` (deprecated, data-race prone) — prefer `middleware.ContextTimeout(d)`.
- Don't look for built-in JWT — it moved to the separate module `github.com/labstack/echo-jwt`.
- Don't skip `Recover()` — without it a panic in a handler kills the request path.

## Binding + validation

`c.Bind(&dto)` fills from tags: `param` (path), `query`, `header`*, `form`, `json`, `xml`. `json`/`xml` fall back to field name if untagged; the rest need explicit tags. Body binding is content-type driven. *Headers are NOT bound by `Bind` — use `(&echo.DefaultBinder{}).BindHeaders(c, &h)`.

DO — bind into a DTO, then validate, then map into the domain type.
```go
type CreateUserDTO struct {
    Name  string `json:"name"  validate:"required"`
    Email string `json:"email" validate:"required,email"`
}
var dto CreateUserDTO
if err := c.Bind(&dto); err != nil {
    return echo.NewHTTPError(http.StatusBadRequest, "invalid request")
}
if err := c.Validate(&dto); err != nil { // requires e.Validator set (see below)
    return echo.NewHTTPError(http.StatusBadRequest, err.Error())
}
```

DON'T
- **Don't bind straight into business/domain structs** — mass-assignment: a client sending `{"isAdmin":true}` can flip fields you never meant to expose. Bind a DTO, copy explicit fields.
- **Don't skip the validator.** `c.Validate` is a no-op that errors (`ErrValidatorNotRegistered`) until you set `e.Validator`. Register a real one:
```go
type CustomValidator struct{ v *validator.Validate } // github.com/go-playground/validator/v10
func (cv *CustomValidator) Validate(i any) error {
    if err := cv.v.Struct(i); err != nil {
        return echo.NewHTTPError(http.StatusBadRequest, err.Error())
    }
    return nil
}
e.Validator = &CustomValidator{v: validator.New()}
```

## Responses & error handling

DO
- Return typed responses: `return c.JSON(http.StatusOK, payload)` (also `c.String`, `c.NoContent`, `c.Blob`).
- Return errors, don't write them: `return echo.NewHTTPError(http.StatusNotFound, "user not found")`. Handlers/middleware return `error`; Echo's centralized `HTTPErrorHandler` renders it (default: JSON `{"message": ...}`; a plain `error` → 500).
- Stash internals in `HTTPError.Internal` (via `.WithInternal(err)`) — it's logged, not sent to the client.

DON'T
- **Don't leak internals.** Never put SQL text, stack traces, or secrets in the client-facing message — send a generic message, log the detail. Override `e.HTTPErrorHandler` to normalize the client shape and log server-side.

## Server: timeouts & graceful shutdown

DO
- **Set server timeouts** — `e.Start(addr)` uses `e.Server` (an `*http.Server`) with NO timeouts by default (Slowloris exposure). Set them, or bring your own server:
```go
e.Server.ReadTimeout  = 5 * time.Second
e.Server.WriteTimeout = 10 * time.Second
```
- Graceful shutdown (v4): start in a goroutine, wait on a signal, `e.Shutdown(ctx)` with a bounded context so in-flight requests drain.
```go
go func() {
    if err := e.Start(":1323"); err != nil && !errors.Is(err, http.ErrServerClosed) {
        e.Logger.Fatal(err)
    }
}()
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
<-ctx.Done()
sctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()
_ = e.Shutdown(sctx)
```

DON'T
- Don't treat `http.ErrServerClosed` as a failure — it's the normal return after `Shutdown`.
- Don't `Close()` when you mean `Shutdown()` — `Close()` drops live connections; `Shutdown()` drains them.

## Sources

- Echo v4 API — https://pkg.go.dev/github.com/labstack/echo/v4
- Echo v4 middleware API — https://pkg.go.dev/github.com/labstack/echo/v4/middleware
- Echo guide: routing — https://echo.labstack.com/guide/routing/
- Echo guide: binding — https://echo.labstack.com/guide/binding/
- Echo guide: error handling — https://echo.labstack.com/guide/error-handling/
- Echo cookbook: graceful shutdown — https://echo.labstack.com/cookbook/graceful-shutdown/
- Echo request-validation cookbook (CustomValidator + go-playground/validator) — https://echo.labstack.com/docs/cookbook/validation
