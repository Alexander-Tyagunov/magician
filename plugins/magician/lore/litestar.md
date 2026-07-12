# Litestar — core digest

Litestar 2.x ASGI (renamed from Starlite in 2.0). Latest 2.24; Python 3.8+.

DO annotate every handler arg AND return type — unannotated raises ImproperlyConfiguredException at boot.
DO set `sync_to_thread=True` on sync handlers/deps doing blocking I/O, `=False` if non-blocking (omitting warns).
DO inject via `dependencies={"k": Provide(fn)}` at app/router/controller/handler; receive as `NamedDependency[T]` (name = key).
DO give generator deps a `try/finally` cleanup (rollback on error); `Provide(use_cache=True)` only when request-safe.
DO validate/parse input via DTOs (msgspec = core encoder; pydantic/attrs/dataclasses/SQLAlchemyDTO supported).
DO authorize with `guards=[...]`; authenticate via AbstractAuthenticationMiddleware or JWT/session backends.
DON'T ship `CORSConfig(allow_origins=["*"])` or `allowed_hosts=["*"]` — disables it; scope to trusted domains.
DON'T omit `CSRFConfig(secret=...)` for cookie/session flows; never leak secrets/tracebacks (debug off in prod).
DON'T rely on name-based DI inference — deprecated 2.24, gone in 3.0; use NamedDependency.

`Litestar(...)` kwargs: `cors_config`, `csrf_config`, `allowed_hosts`, `compression_config`; RateLimit via `middleware=[RateLimitConfig(...).middleware]`.

Commands: `litestar run` (needs `litestar[standard]`); target app via `--app pkg.mod:app` or `LITESTAR_APP`; `litestar --help`.

Deep dive when writing non-trivial litestar — read lore/litestar/{patterns-and-di}.md

Sources: docs.litestar.dev/latest (di, handlers, middleware, security, cli, dto); pypi.org/project/litestar
