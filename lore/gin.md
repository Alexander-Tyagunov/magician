# Gin (Go) — core

Gin v1.x (v1.12.0; go.mod requires Go 1.25+). Router+middleware over net/http. Since Go 1.22 net/http.ServeMux does method+wildcard routing — earn Gin for radix routing, middleware chains, bind+validate, and Context helpers; stay stdlib for trivial services.

DO set `gin.SetMode(gin.ReleaseMode)` (or GIN_MODE=release) in prod — debug mode leaks routes and verbose output.
DO keep `Recovery()` (in `gin.Default()`) so panics → 500 not a crash; use `gin.New()`+explicit middleware for custom stacks.
DO use `ShouldBindJSON`/`ShouldBind` + struct `binding:"required"` tags and handle the returned error yourself.
DON'T use `BindJSON`/`MustBindWith` in request paths — they auto-write 400 text/plain and abort, breaking your error contract.
SECURITY: run behind `http.Server{Handler:r, ReadTimeout, WriteTimeout, IdleTimeout}` — `r.Run()` sets NO timeouts (slowloris). Call `r.SetTrustedProxies(...)` (or nil): default trusts X-Forwarded-For, so clients can spoof `ClientIP()`. Return generic errors, never bind-error/stack detail; set CORS + secure headers via middleware deliberately.

Commands: `go get github.com/gin-gonic/gin@latest`; `GIN_MODE=release go run .`; `go test ./...`.

Deep dive when writing non-trivial gin — read lore/gin/{routing-middleware-binding}.md

Sources: gin-gonic.com/docs · pkg.go.dev/github.com/gin-gonic/gin · github.com/gin-gonic/gin/releases
