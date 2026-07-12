# fastapi — Pydantic v1 vs v2

Scope: FastAPI's use of Pydantic. **Pydantic v2 is the default and standard** (Rust core, `pydantic-core`; ~5–50x faster validation). FastAPI has supported v2 since **FastAPI 0.100.0**. FastAPI still supports v1 (and v1 shims), but write new code for v2. Assume Python foundation lore exists separately.

Detect the version before touching model code:
```python
import pydantic
pydantic.VERSION  # "2.x" → v2 APIs; "1.x" → legacy
```

## v1 → v2 mapping (memorize this table)

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

## DO — model definition (v2)

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

## DON'T

- DON'T call `.dict()`/`.json()`/`.parse_obj()` in new code — deprecated (see table).
- DON'T use `class Config:` in v2 — use `model_config = ConfigDict(...)`.
- DON'T assume `TypeError` inside a validator becomes `ValidationError` — v2 does **not** convert it; raise `ValueError`/`AssertionError`.
- DON'T mix v1 and v2 models in one schema graph; FastAPI can generate broken OpenAPI. Pick one.

## DO — FastAPI request/response with v2

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

## DO — dependencies & lifespan (current style)

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

## Security checklist

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

## Version fallbacks

- Pydantic **v1** project: `class Config: orm_mode = True`, `.dict()`, `parse_obj`, `@validator`, `@root_validator`. Migrate with `bump-pydantic` if possible.
- FastAPI **< 0.95**: `Annotated` unsupported → use `x: X = Depends(...)`.
- FastAPI **< 0.100**: Pydantic v2 unsupported → stay on v1.
- Old FastAPI relying on `on_event`: still works, but migrate to `lifespan`.

## Sources

- Pydantic v2 migration guide — https://docs.pydantic.dev/latest/migration/
- Pydantic models (validate/serialize methods) — https://docs.pydantic.dev/latest/concepts/models/
- Pydantic fields (Field, Annotated, computed_field) — https://docs.pydantic.dev/latest/concepts/fields/
- FastAPI dependencies (Annotated/Depends) — https://fastapi.tiangolo.com/tutorial/dependencies/
- FastAPI lifespan events — https://fastapi.tiangolo.com/advanced/events/
- FastAPI Pydantic v2 support (release notes, 0.100.0) — https://fastapi.tiangolo.com/release-notes/
