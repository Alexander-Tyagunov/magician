# FastAPI — core lore

Version cue: FastAPI 0.100+ ships Pydantic v2 by default. v2: `model_validate`/`model_dump`/`model_dump_json`, `model_config = ConfigDict(...)`, `from_attributes`. v1: `dict()`/`parse_obj()`/`Config`. Never mix. Annotated deps need >=0.95.1.

DO type every param/body with Pydantic models — FastAPI validates+coerces; untyped bodies skip validation.
DO declare deps as `Annotated[X, Depends(f)]` (reusable, mypy-safe); alias `Dep = Annotated[...]`.
DON'T use bare `x = Depends(f)` default — legacy; Annotated is preferred.
DO manage startup/shutdown with `lifespan=asynccontextmanager` (yield splits up/down).
DON'T use `@app.on_event(...)` — deprecated; ignored when `lifespan` is set.
DO set `response_model=`/`-> Model` so responses can't leak extra fields.
SECURITY DON'T set `allow_origins=["*"]` with `allow_credentials=True` in `CORSMiddleware` — invalid; list explicit origins. Ship prod with docs off, generic 500s (no stack traces), secrets via env, authz per-route via `Depends`/`Security(scopes)`.
DO `async def` only when awaiting async I/O; plain `def` runs in a threadpool — never block the loop inside `async def`.

Commands: `pip install "fastapi[standard]"`; `fastapi dev` (reload) / `fastapi run` (prod, uvicorn).

Deep dive when writing non-trivial fastapi — read lore/fastapi/{async-and-di,pydantic-v1-vs-v2}.md

Sources: fastapi.tiangolo.com (dependencies, events, cors, /); pydantic.dev migration guide.
