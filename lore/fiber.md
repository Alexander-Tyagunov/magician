# Fiber — core

Fiber is a fasthttp-based (NOT net/http) Express-style framework. BOTH v2 and v3 run on fasthttp; v3 only adds net/http handler adaptors. Earns its keep over stdlib for raw throughput + Express ergonomics; if you need the net/http ecosystem, prefer chi/stdlib (Go 1.22+ ServeMux already does method+wildcard routing).

DO
- Return errors from handlers; centralize via fiber.Config{ErrorHandler} — map to status, log server-side.
- Set fiber.Config{ReadTimeout,WriteTimeout,IdleTimeout}; defaults are unlimited.
- Chain: recover.New() (panic→500), cors.New() with explicit AllowOrigins (never "*" with AllowCredentials), helmet.New(), limiter.New(), requestid.New().
- Bind+validate: v3 c.Bind().Body(&s)/.Query()/.URI(&s); v2 c.BodyParser(&s). Always run a validator; never trust bound input.

DON'T
- Don't retain c, c.Body() or c.Params() bytes past the handler; fasthttp pools/reuses buffers. Copy before goroutines (utils.CopyString).
- Don't leak stack traces; keep ErrorHandler generic in prod.
- Don't mix v2/v3 API: v3 handler is func(c fiber.Ctx) error (value iface, not *fiber.Ctx); Mount→Use; app.Static→static middleware; Add(methods []string,...).

Version: v3.0.0 GA Feb 2025 (needs Go 1.25+); v2 (v2.52.x) still maintained — pick per go.mod import path.

Commands: go get github.com/gofiber/fiber/v3 ; upgrade v2→v3 with the fiber CLI migration tool.

Deep dive when writing non-trivial fiber — read lore/fiber/{routing-and-v2-vs-v3}.md

## Sources
docs.gofiber.io (v3 What's New / config / middleware); github.com/gofiber/fiber/releases
