# fastapi — Async & dependency injection

FastAPI-specifics for concurrency + DI (Python-foundation lore assumed separate).
Baseline: FastAPI **0.115+** (latest 0.139.0), **Pydantic v2**, Python **3.10+** (`X | None`).
`Annotated`-Depends needs **≥0.95.1**. Lifespan is stable; `@app.on_event` is deprecated.

## async vs sync path operations

FastAPI runs a single event loop. `def` (sync) path ops + `def` dependencies are auto-offloaded
to an **external threadpool** and awaited. `async def` runs directly on the loop.

DO
- Use `async def` when you `await` async libs (httpx, asyncpg, SQLAlchemy async, aioredis).
- Use plain `def` when your I/O client is blocking (sync DB driver, `requests`, filesystem, sync SDK) —
  FastAPI moves it to the threadpool so it can't stall the loop. If unsure, plain `def` is safe.
- Offload unavoidable blocking calls inside an `async def` with `run_in_threadpool`:
  `from fastapi.concurrency import run_in_threadpool; data = await run_in_threadpool(sync_fn, arg)`.

DON'T
- ❌ Never call blocking I/O directly inside `async def` — it freezes the loop for every client
  (`requests.get(...)`, `time.sleep(...)`, sync DB calls). Use async clients or `run_in_threadpool`;
  use `asyncio.sleep` not `time.sleep`.
- ❌ Don't put `async def` on a handler then call sync drivers "for speed" — you lose the threadpool
  safety net. Either go fully async (async driver) or keep it plain `def`.

## Dependency injection (Depends)

DO
- Declare dependencies with the **`Annotated[X, Depends(...)]`** style (recommended since 0.95). It
  preserves types for editors/mypy and is reusable.
```python
from typing import Annotated
from fastapi import Depends

async def common(q: str | None = None, skip: int = 0, limit: int = 100):
    return {"q": q, "skip": skip, "limit": limit}

CommonsDep = Annotated[dict, Depends(common)]   # alias → reuse everywhere
@app.get("/items/")
async def read_items(commons: CommonsDep): return commons
```
- Pass the **callable, not a call**: `Depends(common)` — never `Depends(common())`.
- Mix freely: `def` deps in `async` handlers and vice-versa; FastAPI resolves each correctly.
- Nest sub-dependencies (a dep can declare its own `Depends(...)`); results cached per-request.
- Side-effect-only deps (auth/rate-limit) go on the decorator:
  `@app.get("/x", dependencies=[Depends(verify_token)])`.

DON'T
- ❌ Don't hand-roll validation in the handler when a dependency or Pydantic model can declare it —
  dependency requirements auto-appear in OpenAPI.

## Dependencies with `yield` (setup/teardown)

Use `yield` for resources needing cleanup (DB session, file, client). Before `yield` = setup; after
= teardown. FastAPI wraps it as a context manager; run **exactly one** `yield`.

DO
```python
async def get_db():
    db = SessionLocal()
    try:
        yield db            # injected value
    finally:
        db.close()          # teardown runs after response; guaranteed on error too
```
- Put teardown in `finally`. In trees, outer dep's exit runs before inner's, so inner values stay valid.
- To handle handler errors, wrap `yield` in `try/except` and **re-`raise`** (bare `raise`) — swallowing
  gives a silent HTTP 500 with no server log.

DON'T
- ❌ Don't raise `HTTPException` in exit code (**after** `yield`) to change the response — since 0.106
  the response is already being sent; validate/raise **before** `yield`.

Newer: `Depends(dep, scope="function")` runs teardown *before* the response is sent (default
`scope="request"` = after). Verify against current docs — recent addition.

## Lifespan (startup/shutdown)

DO — use an `asynccontextmanager` passed as `lifespan=`; startup before `yield`, shutdown after.
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()   # startup: pools, models
    yield
    await app.state.pool.close()           # shutdown: release

app = FastAPI(lifespan=lifespan)
```

DON'T
- ❌ Don't use `@app.on_event("startup")` / `@app.on_event("shutdown")` — **deprecated**. If you pass
  `lifespan`, event handlers are ignored (it's all-lifespan or all-events).
- ❌ Don't expect lifespan to fire for mounted sub-apps — it runs only for the main app.

## BackgroundTasks (after-response work)

DO — declare a `BackgroundTasks` param, register with `.add_task(fn, *args, **kwargs)`; runs after
the response is sent. Injectable in handler or dependency (same object reused across both).
```python
from fastapi import BackgroundTasks
@app.post("/notify/{email}")
async def notify(email: str, tasks: BackgroundTasks):
    tasks.add_task(send_email, email, subject="hi")
    return {"queued": True}
```
DON'T
- ❌ Don't use `BackgroundTasks` for heavy/long/cross-process work — it runs in-process and blocks
  shutdown until done. Use Celery/RQ/Arq with a broker instead.
- ❌ Don't import `BackgroundTask` (singular, Starlette) by mistake — use `fastapi.BackgroundTasks`.

## Routers (APIRouter)

DO — split path ops into `APIRouter`s; set shared `prefix`/`tags`/`dependencies` once, then include.
```python
from fastapi import APIRouter, Depends
router = APIRouter(prefix="/items", tags=["items"],
                   dependencies=[Depends(verify_token)])

@router.get("/")            # → GET /items/
async def list_items(): ...

# main.py
app.include_router(router)
app.include_router(admin.router, prefix="/admin", dependencies=[Depends(admin_only)])
```
- `prefix` has **no trailing slash**. Router `dependencies` run for every route (good for auth);
  app-wide deps go on `FastAPI(dependencies=[...])`.
- Import modules, not the `router` name, to avoid collisions: `from .routers import items, users`.

## Pydantic v2 vs v1 (the big split)

FastAPI 0.100+ targets Pydantic **v2**. Detect and adapt — v1 methods still emit deprecation warnings.

DO (v2) / ❌ DON'T (v1 legacy)
| Task | v2 | v1 (legacy) |
|---|---|---|
| to dict | `m.model_dump()` | `m.dict()` |
| to JSON | `m.model_dump_json()` | `m.json()` |
| from dict/obj | `M.model_validate(x)` | `M.parse_obj(x)` |
| from JSON | `M.model_validate_json(s)` | `M.parse_raw(s)` |
| config | `model_config = ConfigDict(...)` | `class Config:` |

- `Field`: use `pattern=` (not `regex`), `min_length`/`max_length` (not `min_items`/`max_items`).
- Config renames: `from_attributes` (was `orm_mode`), `populate_by_name` (was
  `allow_population_by_field_name`), `json_schema_extra` (was `schema_extra`).
```python
from pydantic import BaseModel, ConfigDict, Field
class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # was class Config: orm_mode
    name: str = Field(pattern=r"^[a-z]+$")             # was regex=
```

## Security (FastAPI-specific)

- Validate **all** input via Pydantic models / typed params — never trust raw request data.
- CORS: `CORSMiddleware` with explicit `allow_origins`; never `["*"]` + `allow_credentials=True`.
- Don't leak internals: no stack traces to clients; debug/reload off in prod.
- AuthN/AuthZ as dependencies (`OAuth2PasswordBearer`, `Security(...)`); attach at router/app level.
- Parameterize DB access / use the ORM safely (defer ORM specifics to ORM lore).

## Sources
- https://fastapi.tiangolo.com/async/
- https://fastapi.tiangolo.com/tutorial/dependencies/
- https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- https://fastapi.tiangolo.com/advanced/events/
- https://fastapi.tiangolo.com/tutorial/background-tasks/
- https://fastapi.tiangolo.com/tutorial/bigger-applications/
- https://fastapi.tiangolo.com/release-notes/
- https://pydantic.dev/docs/validation/latest/get-started/migration/
- https://pypi.org/pypi/fastapi/json
