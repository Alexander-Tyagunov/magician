# gin — Routing, middleware & binding

Verified against Gin **v1.12.0** (2026-02-28): needs **Go 1.25+**, ships
`go-playground/validator/v10 v10.30.3`. Import `github.com/gin-gonic/gin`. Assumes the Go `net/http`
foundation lore exists separately — this covers Gin-specifics only.

**When Gin earns its keep over stdlib:** since **Go 1.22**, `net/http.ServeMux` does method + wildcard
routing (`POST /items/{id}`, `/files/{path...}`, exact `/x/{$}`, `r.PathValue("id")`). Reach for Gin
for route groups, an ordered middleware chain, `c.Param`/query/form ergonomics, and struct
binding+validation in one package. For a few routes with no binding, stdlib suffices.

## Engine & mode

DO create the engine with `gin.Default()` — it attaches Logger + Recovery middleware. Recovery
turns a panic into `500` instead of crashing the process.
DO set release mode in prod: `gin.SetMode(gin.ReleaseMode)` (or env `GIN_MODE=release`). Modes:
`DebugMode` / `ReleaseMode` / `TestMode`.

```go
gin.SetMode(gin.ReleaseMode) // before gin.Default()/gin.New()
r := gin.Default()
r.GET("/ping", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"message": "pong"}) })
```

DON'T ship debug mode. Debug prints route tables, warnings, and verbose logs — noisy and
information-leaking. Gin itself warns "Running in \"debug\" mode" at startup; treat that as a bug.
DO call `gin.New()` (no default middleware) only when you attach your own logger/recovery via
`r.Use(...)`. If you use `New()`, you MUST add `gin.Recovery()` yourself or a panic kills the server.

## Routing

DO use `:param` for one segment and `*param` for a catch-all (rest of path, includes leading `/`).

```go
r.GET("/user/:name", func(c *gin.Context) { c.String(200, c.Param("name")) })
r.GET("/user/:name/*action", func(c *gin.Context) { /* c.Param("action") == "/run" */ })
```

DO group related routes; groups compose and nest, and middleware attached to a group applies to
all its routes.

```go
v1 := r.Group("/v1")
auth := v1.Group("/", AuthRequired()) // middleware scoped to this group
auth.POST("/login", loginHandler)
```

DON'T create routes that conflict on the same path (e.g. `:id` and a static segment at the same
position) — Gin panics at registration. Fail fast is intended; fix the route shape.

## Middleware (`c.Next` / `c.Abort`)

A middleware is a `gin.HandlerFunc`. `c.Next()` runs the remaining chain, so code before it is
"pre" and code after it is "post". `c.Abort()` stops *pending* handlers (it does NOT return from the
current function — you must `return` yourself).

```go
func AuthRequired() gin.HandlerFunc {
    return func(c *gin.Context) {
        if c.GetHeader("Authorization") == "" {
            c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
            return // MUST return; Abort alone doesn't stop this handler
        }
        c.Next() // downstream handlers run here
        // post-processing (status, latency) available after Next()
    }
}
```

DO use `c.AbortWithStatusJSON` / `c.AbortWithStatus` to short-circuit with a response.
DON'T forget the `return` after `Abort*` — omitting it lets the current handler keep executing.

## Binding & validation

DO use `ShouldBind*` and handle the error yourself — this is the safe default.
`ShouldBindJSON` forces JSON; `ShouldBind` picks the binder from method + `Content-Type`
(JSON/form/query). Validation tags come from `go-playground/validator/v10` via `binding:"..."`.

```go
type CreateUser struct {
    Email string `json:"email" binding:"required,email"`
    Age   int    `json:"age"   binding:"required,gte=0,lte=130"`
}

func handler(c *gin.Context) {
    var in CreateUser
    if err := c.ShouldBindJSON(&in); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    // ... in is validated
}
```

DON'T ignore the bind error — an unchecked `ShouldBind` means unvalidated, possibly zero-value data
flows downstream. Always branch on `err` and return 400.
DON'T rely on `c.Bind*` (no "Should") unless you want Gin to auto-write `400 + text/plain` and set
the `Content-Type` error; it removes your control over the error body. `ShouldBind*` is preferred for
APIs. `MustBindWith` lets you pin a specific binder (e.g. `binding.Query`).
NOTE `binding:"required"` rejects the field's zero value. For "present but may be zero" use a pointer
field (`*int`) so `nil` vs `0` are distinguishable. Combine with
`gin.EnableJsonDecoderDisallowUnknownFields()` to reject unexpected keys.

## Custom validators

DO register once at startup against the shared validator engine, then reference the tag by name.

```go
var bookableDate validator.Func = func(fl validator.FieldLevel) bool {
    t, ok := fl.Field().Interface().(time.Time)
    return ok && t.After(time.Now())
}
func init() {
    if v, ok := binding.Validator.Engine().(*validator.Validate); ok {
        v.RegisterValidation("bookabledate", bookableDate)
    }
}
// field: CheckIn time.Time `binding:"required,bookabledate"`
```

DON'T register inside a request handler — the type assertion + registration is a startup concern and
is not goroutine-safe under load.

## Server config & graceful shutdown

DON'T use `r.Run()` in production — it gives you no timeouts and no clean shutdown. Wrap the engine
in an explicit `http.Server` so you can set timeouts and drain in-flight requests.

```go
srv := &http.Server{
    Addr:              ":8080",
    Handler:           r,
    ReadHeaderTimeout: 5 * time.Second, // mitigate Slowloris
    ReadTimeout:       15 * time.Second,
    WriteTimeout:      15 * time.Second,
    IdleTimeout:       60 * time.Second,
}
go func() {
    if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
        log.Fatalf("listen: %v", err)
    }
}()

ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
<-ctx.Done() // block until SIGINT/SIGTERM

shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
if err := srv.Shutdown(shutdownCtx); err != nil {
    log.Fatal("forced shutdown:", err)
}
```

DO always set server timeouts (stdlib defaults are none — a hung client can pin a connection).
DO call `srv.Shutdown(ctx)` with a bounded context so drain can't hang forever.

## Security checklist

- DO run `gin.ReleaseMode` in prod so stack traces / debug output never reach clients; verify your
  error handler doesn't echo the panic to the response (Recovery returns a bare `500`).
- DO validate+bind every external input with `ShouldBind*` + `binding` tags; reject on error.
- DO set the `srv` read/write/idle timeouts deliberately.
- DO configure trusted proxies explicitly — `r.SetTrustedProxies([]string{...})` so `c.ClientIP()`
  can't be spoofed via `X-Forwarded-For`. Default trusts all; narrow it.
- DO add security headers and CORS deliberately (e.g. `gin-contrib/cors`) — explicit allowed
  origins, never reflect `*` with credentials.
- DON'T leak internal errors in `c.JSON` bodies; log detail server-side, return a generic message.

## Sources

- https://pkg.go.dev/github.com/gin-gonic/gin — v1.12.0 API, Go 1.25 requirement, Default/New/SetMode/modes, Context binding & flow methods
- https://raw.githubusercontent.com/gin-gonic/gin/master/go.mod — go 1.25.0, go-playground/validator/v10 v10.30.3
- https://gin-gonic.com/en/docs/ — docs index (routing, binding, middleware, server-config topics)
- https://raw.githubusercontent.com/gin-gonic/gin/master/docs/doc.md — verbatim examples: params, groups, middleware, ShouldBind/MustBindWith, custom validators, graceful shutdown
- https://go.dev/doc/go1.22 — net/http ServeMux method + wildcard routing baseline
