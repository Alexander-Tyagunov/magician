# litestar — Patterns & DI

Litestar 2.x, ASGI, class-based (NestJS-inspired). Serializes via **msgspec** (fast). Latest **2.24.0** (Jun 2026), Python `>=3.8,<4.0`.

## Version reality (state it, don't guess)
- **1.x was named Starlite.** `pip install starlite` / `from starlite import ...` is the legacy line — dead. 2.0 renamed to `litestar`. Never mix imports.
- Everything here is **2.x**. Flag anything gated by a specific minor.
- `litestar.contrib.sqlalchemy` is **legacy**; current path is `litestar.plugins.sqlalchemy` (backed by `advanced-alchemy`).

## Route handlers
DO
- Use semantic decorators: `@get`, `@post`, `@put`, `@patch`, `@delete`, `@head` (from `litestar`). `@websocket`, `@asgi` for those protocols.
- **Type-annotate every param and the return** — unannotated raises `ImproperlyConfiguredException` at boot.
- Register explicitly: `Litestar(route_handlers=[...])`. Group with `Controller` (class) and `Router`.
- Set `sync_to_thread=True` on **blocking** sync handlers/deps; `False` on non-blocking sync. Omitting on a sync callable warns.
- Path params carry a type: `@get("/users/{user_id:int}")` → `user_id: int`.

DON'T
- Don't use `@route(http_method=[...])` for CRUD — each verb+path is its own OpenAPI op; semantic decorators are clearer.
- Don't return un-annotated `->` — no annotation, no schema, boot error.

## Dependency injection (layered)
Four layers, closest wins (deps **override**, unlike guards which are cumulative):

| Layer | Declared |
|---|---|
| App | `Litestar(dependencies={...})` |
| Router | `Router(dependencies={...})` |
| Controller | `dependencies = {...}` class attr |
| Handler | `@get(dependencies={...})` |

DO
- Wrap callables in `Provide` (from `litestar.di`) — or pass the bare callable in the dict.
- **Mark injected params with `NamedDependency[T]`** (from `litestar.di`). The param name matches the dict key; `T` validates the value.
- Use `Provide(fn, use_cache=True)` to memoize across requests (crude cache — no kwarg-aware LRU). Deps run **once per request** regardless.
- Nest deps freely (deps inject into deps). Deps receive the same injectables as handlers (path params, `state`, other deps).
- Missing provider for a marked, defaultless dep fails at **boot** (`ImproperlyConfiguredException`), not at request time — treat that as a feature.

DON'T
- Don't rely on **bare name-matching without a marker** — **deprecated since 2.24, removed in 3.0** (`LitestarDeprecationWarning`). On 2.24+ always use `NamedDependency`. Pre-2.24 code injects by name alone — recognize it, migrate it.
- Don't do blocking I/O in a sync dep without `Provide(fn, sync_to_thread=True)`.

```python
from litestar.di import NamedDependency, Provide  # both from litestar.di
@get("/", dependencies={"repo": Provide(repo)})
async def h(repo: NamedDependency[Repo]) -> None: ...
```

### `yield` deps (setup/teardown)
Generator dep = session/txn scope; cleanup runs **after handler returns, before response sends**. Always `try/finally`. A handler exception is thrown back in at the `yield` (rollback there) — don't re-raise it. Cleanup-phase errors surface in an `ExceptionGroup`.

## DTOs (in/out shaping + validation)
Factories subclass `AbstractDTO`, parameterized by your model: `DataclassDTO`, `MsgspecDTO` (from `litestar.dto`), `PydanticDTO` (from `litestar.plugins.pydantic`), `SQLAlchemyDTO` (from `litestar.plugins.sqlalchemy`). There is **no `AttrsDTO`** — attrs is supported via `AttrsSchemaPlugin`, not a DTO factory.

DO
- Attach with `dto=` (inbound + default outbound) and `return_dto=` (override outbound). `return_dto=None` skips output processing for natively-encodable returns.
- Configure via `DTOConfig`: `exclude`/`include` (dotted+indexed paths e.g. `"address.id"`, `"pets.0.id"`), `rename_fields={"name":"userName"}`, `rename_strategy="camel"|"pascal"|"upper"|"lower"|"kebab"`, `max_nested_depth` (default `1`, `0` = no nesting), `partial=True` (PATCH), `forbid_unknown_fields=True` (reject extras).
- For PATCH/partial, take `DTOData[Model]` and call `data.update_instance(obj)`; for create, `data.create_instance(id=uuid4())` (nested via `addr__id=...`).

DON'T
- Don't hand-write serialization for SQLAlchemy rows — use `SQLAlchemyDTO` + `exclude` to drop internal columns (never leak password/hash fields).
- Don't set `underscore_fields_private=False` unless you intend to expose `_`-prefixed fields.
- Type mismatch between handler annotation and DTO generic raises `InvalidAnnotationException` at registration.

```python
from litestar.dto import DataclassDTO, DTOConfig
class UserDTO(DataclassDTO[User]):
    config = DTOConfig(exclude={"password"}, rename_strategy="camel")
@post("/users", dto=UserDTO, sync_to_thread=False)
def create(data: User) -> User: ...
```

## Plugins (SQLAlchemy)
DO
- `SQLAlchemyPlugin` (full), `SQLAlchemyInitPlugin` (engine/session + DI), `SQLAlchemySerializationPlugin` (row serialization). Register via `Litestar(plugins=[...])`.
- Config: `SQLAlchemyAsyncConfig(connection_string=..., engine_config=..., session_config=..., before_send_handler=...)` (or `...SyncConfig`).
- Inject the session: `db_session: NamedDependency[AsyncSession]` (and `db_engine`). Rename via `session_dependency_key` / `engine_dependency_key`.
- For commit-on-2xx / rollback-on-error use `async_autocommit_before_send_handler` (or `sync_*`). Default handler just closes the session.

DON'T
- Don't build engines/sessions by hand per request — let the plugin own lifecycle.
- Table creation isn't a config flag — run migrations (Alembic) or `Base.metadata.create_all` in a startup hook; don't `create_all` in prod.

## Guards (authz)
DO
- Guard signature `(connection: ASGIConnection, route_handler: BaseRouteHandler) -> None`; raise `PermissionDeniedException` (403) on failure.
- Attach `guards=[...]` at any layer — **cumulative**, all run (not overridden).
- Stash per-handler metadata in `opt={...}`, read via `route_handler.opt`.

DON'T
- Don't return truthy/falsy — guards signal via **raising**, return `None`.
- Remember controller/app guards also fire on `OPTIONS` — scope auth checks accordingly.

```python
def admin_only(conn: ASGIConnection, _: BaseRouteHandler) -> None:
    if not conn.user.is_admin:
        raise PermissionDeniedException()
```

## Lifespan, state, security
DO
- Prefer `lifespan=[asynccontextmanager_fn]` for resources needing setup+teardown (yield once). `on_startup=[...]`/`on_shutdown=[...]` remain valid for simple hooks. Lifespan CMs unwind in **inverse order**, before shutdown hooks.
- Share cross-request objects on `app.state` / `State`; read via reserved `state: State` kwarg. Use `ImmutableState` to forbid mutation.
- Configure `CORSConfig` deliberately (explicit origins, never `*` with credentials). Validate all input through DTOs/typed params.

DON'T
- Don't ship `debug=True` in prod — leaks stack traces. Keep secrets in env, out of `opt`/responses.
- Don't stuff request-scoped data into `app.state` (it's app-global) — use DI/`request.state`.

## Contrast with FastAPI
- **DI:** Litestar = name-keyed `dependencies` dict + `NamedDependency[T]` (2.24+). FastAPI = inline `Annotated[T, Depends(fn)]` (v2 era; the old `= Depends()` default is discouraged).
- **Serialization:** Litestar = msgspec (faster; msgspec `Struct`/dataclass/attrs/Pydantic all work). FastAPI = Pydantic (`model_validate`/`model_dump`/`ConfigDict` in v2; `dict()`/`parse_obj` in legacy v1).
- **Shaping:** Litestar DTOs decouple wire shape from model; FastAPI uses `response_model` + separate schemas.
- **Structure:** Litestar leans class `Controller`/`Router` + explicit `route_handlers=[...]`; FastAPI leans `APIRouter` + decorator registration.
- **Lifespan:** both favor async-CM `lifespan`; FastAPI's `@app.on_event` is deprecated, Litestar keeps `on_startup`/`on_shutdown` first-class.

## Sources
- https://docs.litestar.dev/latest/
- https://docs.litestar.dev/latest/usage/dependency-injection.html
- https://docs.litestar.dev/latest/usage/routing/handlers.html
- https://docs.litestar.dev/latest/usage/dto/index.html
- https://docs.litestar.dev/latest/usage/dto/1-abstract-dto.html
- https://docs.litestar.dev/latest/usage/security/guards.html
- https://docs.litestar.dev/latest/usage/databases/sqlalchemy/plugins/index.html
- https://docs.litestar.dev/latest/usage/databases/sqlalchemy/plugins/sqlalchemy_init_plugin.html
- https://docs.litestar.dev/latest/usage/lifecycle-hooks.html
- https://docs.litestar.dev/latest/usage/applications.html
- https://pypi.org/pypi/litestar/json
