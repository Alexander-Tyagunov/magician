# fiber — Routing, middleware & v2 vs v3

Verified against Fiber **v3.4.0** (2026-07-02; v3.0.0 GA 2026-02-02) and **v2.52.14**.
v3 imports `github.com/gofiber/fiber/v3` and needs **Go 1.25+**; v2 imports
`github.com/gofiber/fiber/v2`. **Both v2 and v3 are built on `valyala/fasthttp`,
NOT `net/http`** — v3 is a major rewrite of the API, not a switch of engine. Assumes
Go / `net/http` lore lives elsewhere; this covers Fiber-specifics. Express-style API
(`app.Get`, `c.Params`, `c.JSON`), but the request/response objects are fasthttp's.

## fasthttp is the load-bearing fact — read first

- **DON'T** plug `net/http` middleware/handlers in directly — fasthttp has its own
  `RequestCtx`, so the stdlib ecosystem (`http.Handler`, `func(http.Handler) http.Handler`)
  is **incompatible without an adapter**. In v3 `Ctx` satisfies `context.Context`;
  in v2 use `c.UserContext()`.
- **DO** bridge via the `adaptor` middleware:
  `adaptor.HTTPMiddleware(mw)`, `adaptor.HTTPHandler(h)`, `adaptor.HTTPHandlerFunc(fn)`
  to run stdlib code inside Fiber; `adaptor.FiberHandler`, `adaptor.FiberApp` for the
  reverse. Conversion copies buffers — measure before hot-pathing it.
- **DO** treat `Ctx` values as request-scoped and reused: `c.Params`, `c.Query`,
  `c.Body()` point at buffers valid **only within the handler**. Copy (or set
  `Immutable: true`) before stashing across goroutines/requests.

## When Fiber earns its keep (Go 1.22+ raised the bar)

Since Go 1.22 `net/http.ServeMux` does method + wildcard routing
(`mux.HandleFunc("GET /items/{id}", h)`, `r.PathValue("id")`).

- **DON'T** adopt Fiber for a few `METHOD /path/{id}` routes — stdlib or chi keeps
  you on the `net/http` ecosystem (middleware, `httptest`, otel, etc.).
- **DO** reach for Fiber when you want fasthttp throughput + Express ergonomics and
  accept the ecosystem tax. Prefer chi/gin/echo if you need `net/http` compatibility.

## DO — routing

```go
app := fiber.New()                         // v3: fiber.New(fiber.Config{...})
app.Get("/users/:id", getUser)             // Get/Post/Put/Patch/Delete/Head/Options
app.Get("/files/*", serveFile)             // wildcard → c.Params("*")
app.Add([]string{"GET","POST"}, "/x", h)   // v3 Add takes []string of methods
api := app.Group("/api", authMW)           // prefix group + group middleware
log.Fatal(app.Listen(":3000"))
```

- **DO** read params: `c.Params("id")`, optional `/:name?`, constraints
  `/:id<int>`, `/:date<datetime(2006-01-02)>`. Typed: v3 `fiber.Params[int](c,"id")`;
  v2 `c.ParamsInt("id")`.
- **DO** know v3 auto-registers `HEAD` for every `GET` (disable with
  `DisableHeadAutoRegister`). Route matching is case-sensitive/insensitive per config.
- **DON'T** use v2-isms removed in v3: `app.Mount` → use `app.Use`; `app.Static(...)`
  → the **static middleware**; `app.Route` prefix helper changed (v3 adds `RouteChain`).

## DO — context, binding & validation

```go
// v3 — unified Bind replaces the *Parser family
type In struct{ ID int `uri:"id"`; Name string `json:"name" validate:"required"` }
func h(c fiber.Ctx) error {
    in := new(In)
    if err := c.Bind().URI(in); err != nil { return err } // .Body .Query .Header .Cookie .All
    return c.Status(fiber.StatusCreated).JSON(fiber.Map{"id": in.ID})
}
```

- **v2 → v3 rename** (all v2 names are gone in v3):
  `BodyParser` → `c.Bind().Body()`; `QueryParser` → `.Query()`;
  `ParamsParser` → `.URI()` (**struct tag `params` → `uri`**);
  `CookieParser` → `.Cookie()`; `ReqHeaderParser` → `.Header()`.
  v3 `Bind()` binds request data; **view data is now `c.ViewBind()`**.
- **DO** always validate after binding — binding only decodes, it does not enforce
  rules. Wire a validator (e.g. `go-playground/validator`) on the struct tags above;
  return `400` on failure. Never trust `Bind` output as safe input.
- **DO** pass request-scoped values with `c.Locals(key, val)` / `c.Locals(key)`
  (v3 generic: `fiber.Locals[T](c, key)`). Keep keys unexported typed constants.
- **DON'T** hand-roll status codes — `c.Status(code).JSON(...)` is chainable; use
  `fiber.StatusXxx` constants.

## DO — middleware (import each as a subpackage)

```go
import (
  "github.com/gofiber/fiber/v3/middleware/logger"
  "github.com/gofiber/fiber/v3/middleware/recover"
  "github.com/gofiber/fiber/v3/middleware/cors"
)
app.Use(recover.New())   // catch panics → 500 (NOT installed by default)
app.Use(logger.New())
app.Use(cors.New(cors.Config{AllowOrigins: []string{"https://app.example.com"}}))
```

- **DO** register `recover.New()` explicitly — Fiber does **not** recover panics by
  default; without it a panicking handler kills the connection. In v2 the package is
  `.../v2/middleware/recover` (same API).
- **DON'T** leak stack traces in prod: `recover` keeps `EnableStackTrace: false` by
  default — leave it off (or gate on env). Don't return raw `err.Error()` to clients;
  map to a generic message via `fiber.Config{ErrorHandler: ...}`.
- **DO** order matters: `recover` first, then `requestid`/`logger`, then auth, then
  routes. `app.Use` runs top-down.

## Security checklist

- **CORS default is wide open:** an empty `AllowOrigins` reflects **any** origin. Set
  it explicitly. Fiber v3 **panics at startup** if `AllowCredentials: true` while
  origins are wildcard/empty — good; never work around it by dropping credentials
  handling. `AllowOrigins/AllowMethods/AllowHeaders/ExposeHeaders` are **`[]string`
  in v3** (were comma-separated strings in v2).
- **DO** set server timeouts on `fiber.New(fiber.Config{ReadTimeout, WriteTimeout,
  IdleTimeout})` — fasthttp has none by default; without them slow-loris is trivial.
- **DO** add the **helmet** middleware (`.../middleware/helmet`) for secure headers,
  and `limiter` for rate limiting. Put `csrf`/`encryptcookie` on cookie-auth flows.
- **DON'T** trust proxy headers blindly — v3 uses `fiber.Config{TrustProxy: true,
  TrustProxyConfig: fiber.TrustProxyConfig{Proxies: [...]}}` (v2: `EnableTrustedProxyCheck`
  + `TrustedProxies`). Required before believing `c.IP()`/`X-Forwarded-*`.
- **DON'T** ship a custom `ErrorHandler` that echoes internals; log server-side, return
  `fiber.NewError(code, safeMsg)`.

## v2 → v3 quick diff

- Handler: v2 `func(c *fiber.Ctx) error` (pointer) → v3 `func(c fiber.Ctx) error`
  (**`Ctx` is now an interface**; enables `app.NewWithCustomCtx`). Drop the `*`.
- `*Parser` methods → `c.Bind().X()` (see above); `params` tag → `uri`.
- `Mount`→`Use`; `Static`→static middleware; `Add` takes `[]string` methods;
  `Context()`→`RequestCtx()`; `UserContext` removed (`Ctx` is a `context.Context`).
- Listen/TLS/Prefork moved to `fiber.ListenConfig`; `Prefork`→`EnablePrefork`.
- Still fasthttp — but v3's router can also register adapted `net/http`/`fasthttp`
  handlers via `adaptor`.

## Sources

- https://docs.gofiber.io/ (v3 landing, install, Go 1.25 requirement, fasthttp)
- https://docs.gofiber.io/api/ctx (v3 Ctx: Params/JSON/Locals/Query/Bind/Status/Cookie)
- https://docs.gofiber.io/next/whats_new (v2→v3 breaking changes: Bind, routing, config)
- https://github.com/gofiber/fiber (releases: v3.4.0, v3.0.0 GA, v2.52.14; hello-world)
- https://github.com/gofiber/fiber/tree/main/middleware (recover, logger, cors, adaptor, helmet, timeout, static, limiter)
- https://github.com/gofiber/fiber/blob/main/middleware/cors/cors.go (AllowCredentials + wildcard panic; AllowOrigins slice)
- https://github.com/gofiber/fiber/blob/main/middleware/adaptor/adaptor.go (HTTPHandler/HTTPMiddleware/FiberHandler net/http bridge)
