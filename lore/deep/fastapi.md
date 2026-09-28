# fastapi — deep dive

> On-demand companion to `lore/fastapi.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Async & dependency injection](#async-and-di) · [Pydantic v1 vs v2](#pydantic-v1-vs-v2)

## Async & dependency injection <a id="async-and-di"></a>

FastAPI-specifics for concurrency + DI (Python-foundation lore assumed separate).
Baseline: FastAPI **0.115+** (latest 0.139.0), **Pydantic v2**, Python **3.10+** (`X | None`).
`Annotated`-Depends needs **≥0.95.1**. Lifespan is stable; `@app.on_event` is deprecated.

### async vs sync path operations

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

### Dependency injection (Depends)

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

### Dependencies with `yield` (setup/teardown)

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

### Lifespan (startup/shutdown)

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

### BackgroundTasks (after-response work)

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

### Routers (APIRouter)

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

### Pydantic v2 vs v1 (the big split)

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

### Security (FastAPI-specific)

- Validate **all** input via Pydantic models / typed params — never trust raw request data.
- CORS: `CORSMiddleware` with explicit `allow_origins`; never `["*"]` + `allow_credentials=True`.
- Don't leak internals: no stack traces to clients; debug/reload off in prod.
- AuthN/AuthZ as dependencies (`OAuth2PasswordBearer`, `Security(...)`); attach at router/app level.
- Parameterize DB access / use the ORM safely (defer ORM specifics to ORM lore).

### Sources
- https://fastapi.tiangolo.com/async/
- https://fastapi.tiangolo.com/tutorial/dependencies/
- https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- https://fastapi.tiangolo.com/advanced/events/
- https://fastapi.tiangolo.com/tutorial/background-tasks/
- https://fastapi.tiangolo.com/tutorial/bigger-applications/
- https://fastapi.tiangolo.com/release-notes/
- https://pydantic.dev/docs/validation/latest/get-started/migration/
- https://pypi.org/pypi/fastapi/json

## Pydantic v1 vs v2 <a id="pydantic-v1-vs-v2"></a>

Scope: FastAPI's use of Pydantic. **Pydantic v2 is the default and standard** (Rust core, `pydantic-core`; ~5–50x faster validation). FastAPI has supported v2 since **FastAPI 0.100.0**. FastAPI still supports v1 (and v1 shims), but write new code for v2. Assume Python foundation lore exists separately.

Detect the version before touching model code:
```python
import pydantic
pydantic.VERSION  # "2.x" → v2 APIs; "1.x" → legacy
```

### v1 → v2 mapping (memorize this table)

| Concern | v1 | v2 |
|---|---|---|
| dict from instance | `m.dict()` | `m.model_dump()` |
| JSON from instance | `m.json()` | `m.model_dump_json()` |
| parse dict/obj | `Model.parse_obj(x)` | `Model.model_validate(x)` |
| parse JSON/bytes | `Model.parse_raw(s)` | `Model.model_validate_json(s)` |
| from ORM object | `Model.from_orm(o)` | `Model.model_validate(o)` (+ `from_attributes=True`) |
| no-validation build | `Model.construct()` | `Model.model_construct()` |
| copy | `m.copy()` | `m.model_copy()` |
| JSON schema | `Model.schema()` / `.schema_json()` | `Model.model_json_schema()` |
| rebuild refs | `update_forward_refs()` | `Model.model_rebuild()` |
| config | `class Config:` | `model_config = ConfigDict(...)` |
| field validator | `@validator` | `@field_validator` |
| root validator | `@root_validator` | `@model_validator` |
| validate func args | `@validate_arguments` | `@validate_call` |
| fields introspection | `Model.__fields__` | `Model.model_fields` |

Config key renames: `orm_mode`→`from_attributes`, `allow_population_by_field_name`→`populate_by_name`, `schema_extra`→`json_schema_extra`, `min_anystr_length`→`str_min_length`, `anystr_strip_whitespace`→`str_strip_whitespace`, `validate_all`→`validate_default`, `keep_untouched`→`ignored_types`.

v1 names still work in v2 but emit `DeprecationWarning`. Don't rely on them.

### DO — model definition (v2)

```python
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, computed_field

class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")  # ORM read + reject unknown keys

    name: str = Field(min_length=1, max_length=100)
    price: Annotated[float, Field(gt=0)]           # Annotated constraints (preferred)
    tags: list[str] = Field(default_factory=list)  # never mutable default literal
    alias_id: int = Field(alias="id")

    @field_validator("name")
    @classmethod
    def strip(cls, v: str) -> str:                 # @classmethod is required in v2
        return v.strip()

    @model_validator(mode="after")
    def check(self) -> "Item":                     # mode="after" gets the built instance
        if self.price > 1000 and not self.tags:
            raise ValueError("expensive items need tags")
        return self

    @computed_field  # serialized like a field, read-only
    @property
    def price_with_tax(self) -> float:
        return round(self.price * 1.2, 2)
```

- DO put `@field_validator` **above** `@classmethod`, and always add `@classmethod` (v2 requires it).
- DO prefer `Annotated[T, Field(...)]` over `x: T = Field(...)` — reuses constraints, works with `Depends`.
- DO use `default_factory` for `list`/`dict`/`set` defaults.
- DO set `extra="forbid"` on request bodies to reject unexpected fields.
- DO use `model_validator(mode="before")` for raw-input reshaping, `mode="after"` for cross-field checks on the built model.

### DON'T

- DON'T call `.dict()`/`.json()`/`.parse_obj()` in new code — deprecated (see table).
- DON'T use `class Config:` in v2 — use `model_config = ConfigDict(...)`.
- DON'T assume `TypeError` inside a validator becomes `ValidationError` — v2 does **not** convert it; raise `ValueError`/`AssertionError`.
- DON'T mix v1 and v2 models in one schema graph; FastAPI can generate broken OpenAPI. Pick one.

### DO — FastAPI request/response with v2

```python
from fastapi import FastAPI
app = FastAPI()

@app.post("/items/", response_model=Item)   # response_model filters + validates output
async def create(item: Item) -> Item:         # body auto-validated by Pydantic
    return item
```

- DO declare a `response_model` (or return-type annotation) — validates and shapes output, and keeps secrets out.
- DO use `response_model_exclude_none=True` / `Field(exclude=True)` to drop sensitive/empty fields.
- DO serialize manually with `item.model_dump(mode="json")` when you need JSON-safe primitives (datetimes → strings) outside a response.

### DO — dependencies & lifespan (current style)

Use `Annotated[X, Depends(...)]` (FastAPI ≥ 0.95.1). Don't use the bare `x: X = Depends(...)` default style in new code.
```python
from typing import Annotated
from fastapi import Depends

def get_db(): ...
DB = Annotated[Session, Depends(get_db)]   # reusable alias

@app.get("/users/{uid}")
async def read(uid: int, db: DB): ...
```

Startup/shutdown: use the **`lifespan`** async context manager. `@app.on_event("startup"|"shutdown")` is **deprecated**; if you pass `lifespan`, `on_event` handlers never run.
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await open_pool()   # startup
    app.state.pool = pool
    yield
    await pool.close()          # shutdown

app = FastAPI(lifespan=lifespan)
```

### Security checklist

- DO validate/parse **all** external input through Pydantic models — never trust raw `request.json()`.
- DO set `extra="forbid"` on inbound models to block mass-assignment / smuggled fields.
- DO keep secrets out of responses: separate input/output models, `Field(exclude=True)`, or `response_model`.
- DON'T ship `debug=True` (FastAPI) or verbose tracebacks in prod — leaks stack traces. Return generic error bodies via exception handlers.
- DO configure CORS deliberately: explicit `allow_origins=[...]`; never `["*"]` together with `allow_credentials=True` (the browser rejects it and it's insecure).
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["https://app.example.com"], allow_credentials=True)
```
- DO enforce authn/authz in dependencies (`Depends(get_current_user)`); return `401`/`403`, not `200` with empty data.
- DO defer DB/ORM parameterization specifics to the ORM lore — but never string-format SQL from validated fields.

### Version fallbacks

- Pydantic **v1** project: `class Config: orm_mode = True`, `.dict()`, `parse_obj`, `@validator`, `@root_validator`. Migrate with `bump-pydantic` if possible.
- FastAPI **< 0.95**: `Annotated` unsupported → use `x: X = Depends(...)`.
- FastAPI **< 0.100**: Pydantic v2 unsupported → stay on v1.
- Old FastAPI relying on `on_event`: still works, but migrate to `lifespan`.

### Sources

- Pydantic v2 migration guide — https://docs.pydantic.dev/latest/migration/
- Pydantic models (validate/serialize methods) — https://docs.pydantic.dev/latest/concepts/models/
- Pydantic fields (Field, Annotated, computed_field) — https://docs.pydantic.dev/latest/concepts/fields/
- FastAPI dependencies (Annotated/Depends) — https://fastapi.tiangolo.com/tutorial/dependencies/
- FastAPI lifespan events — https://fastapi.tiangolo.com/advanced/events/
- FastAPI Pydantic v2 support (release notes, 0.100.0) — https://fastapi.tiangolo.com/release-notes/
