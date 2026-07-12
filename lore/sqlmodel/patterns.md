# sqlmodel — Models, session & pitfalls

SQLModel (by FastAPI's author) = SQLAlchemy + Pydantic v2 fused into one class. A `table=True`
class is *simultaneously* a SQLAlchemy ORM model and a Pydantic model — a thin layer; real work is
SQLAlchemy 2.0 underneath. Assume python + web-framework lore live elsewhere.

**Version reality (verify before asserting).** Latest is **0.0.39** — still **0.x, pre-1.0; API
can shift, so pin it** (`sqlmodel==0.0.x`). Requires **Python >=3.10**, **SQLAlchemy
>=2.0.14,<2.1**, **Pydantic >=2.11**. Pydantic **v1 dropped in 0.0.31** (v2-only now).
`sqlmodel_update()` landed in **0.0.16**. Rides SQLAlchemy 2.0, so 2.0-style lore applies:
`select()` + `session.exec`, no legacy `Query`.

## Models: table vs plain

DO make exactly one model per table carry `table=True`; keep input/output schemas as plain
`SQLModel` (or Pydantic) classes. DO put the primary key as `int | None` with a default so it can
be unset before insert.

```python
from sqlmodel import Field, SQLModel

class HeroBase(SQLModel):          # plain — shared fields, no table
    name: str = Field(index=True)
    secret_name: str
    age: int | None = Field(default=None, index=True)

class Hero(HeroBase, table=True):  # the ONLY table model
    id: int | None = Field(default=None, primary_key=True)

class HeroCreate(HeroBase): pass                 # input
class HeroPublic(HeroBase): id: int              # output: id required, not Optional
class HeroUpdate(SQLModel):                       # PATCH: every field optional
    name: str | None = None
    secret_name: str | None = None
    age: int | None = None
```

DON'T reuse the table model as your API body. It over-exposes columns (hashed passwords, internal
flags) and makes `id` look optional on output. Separate models = explicit contract; FastAPI's
`response_model=HeroPublic` strips anything undeclared (a real security filter). DON'T declare two
`table=True` models for one table. DON'T use mutable defaults (`list`/`dict`) — use
`Field(default_factory=list)`.

## Field: keys, index, columns

- `Field(primary_key=True)` — PK gets an implicit index; don't add `index=True` to it.
- `Field(index=True)` — creates `ix_<table>_<col>` automatically.
- `Field(foreign_key="team.id")` — string is `"<tablename>.<column>"`, lowercase table name.
- `Field(unique=True)` — unique constraint.
- Custom SQLAlchemy column/type: `Field(sa_column=Column(...))`. When you pass `sa_column`, set
  type/nullable/default *there*, not via other `Field` args (they'd conflict).

## Relationship: navigation, not columns

Relationship attrs are objects, not columns. Pair with `back_populates` on both sides.

```python
from sqlmodel import Relationship

class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    heroes: list["Hero"] = Relationship(back_populates="team", cascade_delete=True)

class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    team_id: int | None = Field(default=None, foreign_key="team.id", ondelete="CASCADE")
    team: Team | None = Relationship(back_populates="heroes")
```

Cascade delete has TWO independent knobs — use both:
- `cascade_delete=True` on `Relationship()` ("one" side) = **app-side**; deletes in-memory objects.
- `ondelete="CASCADE"|"SET NULL"|"RESTRICT"` on the FK `Field()` = **DB-side** `ON DELETE`;
  protects against direct SQL. `SET NULL` needs a nullable FK; `RESTRICT` needs
  `passive_deletes="all"` on the Relationship to actually raise.

DON'T forget SQLite ignores FKs unless `PRAGMA foreign_keys=ON`. Advanced SQLAlchemy relation
options go via `sa_relationship_kwargs={...}` (e.g. `lazy`, `order_by`).

## Engine, tables, migrations

```python
from sqlmodel import SQLModel, create_engine
engine = create_engine("sqlite:///db.sqlite", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)   # imports ALL table classes first
```

DO create **one** engine, module-level, reused everywhere. DO add
`connect_args={"check_same_thread": False}` for SQLite under FastAPI (multiple threads share the
connection). DON'T ship `echo=True` (dev-only SQL logging). DON'T rely on `create_all()` beyond
first boot — it only creates *missing* tables; it never alters existing ones. **For schema
changes use Alembic**; autogenerate reads `SQLModel.metadata`.

## Session & queries (2.0 style)

Import `select` from **sqlmodel**, not sqlalchemy — SQLModel's variant carries typing tricks and
auto-unwraps scalars.

```python
from sqlmodel import Session, select

with Session(engine) as session:
    heroes = session.exec(select(Hero).where(Hero.age > 30)).all()  # bound params, safe
    one    = session.exec(select(Hero).where(Hero.name == "X")).first()  # or None
    exact  = session.exec(select(Hero).where(Hero.id == 1)).one()         # errors if !=1
    hero   = session.get(Hero, 1)                                          # PK lookup
```

DO use `session.exec()` (SQLModel) — wraps `session.execute()`, returns model objects directly.
DON'T use bare SQLAlchemy `session.execute(select(Hero))` here — you'd get `Row` tuples needing
`.scalars()`. FastAPI: yield the session as a dependency
(`def get_session(): with Session(engine) as s: yield s`).

Write path: `session.add(obj)` → `commit()` → `refresh(obj)` (reload PK/defaults). Partial update:

```python
db_hero.sqlmodel_update(patch.model_dump(exclude_unset=True))  # 0.0.16+
```

`exclude_unset=True` sends only client-provided fields; explicit `null` still overwrites, omitted
stays untouched.

DON'T compare a nullable/optional column and let your type checker complain — wrap it:
`from sqlmodel import col; select(Hero).where(col(Hero.age) >= 35)`.

## Detached instances (the #1 relationship trap)

DON'T access a relationship attr after the session closes — lazy load fires against a dead session
→ `DetachedInstanceError`. In FastAPI, don't return a raw table object and expect relationships to
serialize later.

DO shape nested output with response models that mirror the graph; break recursion by nesting the
*plain* public model:

```python
class HeroPublicWithTeam(HeroPublic):
    team: TeamPublic | None = None    # NOT TeamPublicWithHeroes → avoids infinite recursion
```

Or eager-load while the session is open (`selectinload`/`joinedload`) before leaving the `with`.

## Async

Use SQLAlchemy's async engine (`create_async_engine`, driver `sqlite+aiosqlite` /
`postgresql+asyncpg`) with `from sqlmodel.ext.asyncio.session import AsyncSession`. Then
`await session.exec(...)`, `await session.commit()`. Relationship access isn't awaitable —
eager-load (`selectinload`) up front or you hit lazy-load errors under async.

## Raw SQL — SECURITY (non-negotiable)

Binding is automatic for `select()`/`where()` (compiles to `?`/`:param` placeholders). The escape
hatch is not. DON'T ever f-string or concat user input into SQL. DO use SQLAlchemy `text()` with
**bound params**:

```python
from sqlalchemy import text
session.exec(text("SELECT * FROM hero WHERE name = :n"), params={"n": user_input})  # ✅
# f"...WHERE name = '{user_input}'"  ← ❌ injection
```

## Sources

- https://sqlmodel.tiangolo.com/
- https://sqlmodel.tiangolo.com/tutorial/create-db-and-table/
- https://sqlmodel.tiangolo.com/tutorial/select/
- https://sqlmodel.tiangolo.com/tutorial/where/
- https://sqlmodel.tiangolo.com/tutorial/indexes/
- https://sqlmodel.tiangolo.com/tutorial/relationship-attributes/define-relationships-attributes/
- https://sqlmodel.tiangolo.com/tutorial/relationship-attributes/cascade-delete-relationships/
- https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/
- https://sqlmodel.tiangolo.com/tutorial/fastapi/update/
- https://sqlmodel.tiangolo.com/tutorial/fastapi/relationships/
- https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/
- https://pypi.org/project/sqlmodel/
- https://github.com/fastapi/sqlmodel/releases
- https://docs.sqlalchemy.org/en/20/
- https://alembic.sqlalchemy.org/
