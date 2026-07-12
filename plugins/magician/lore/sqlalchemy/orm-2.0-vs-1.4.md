# sqlalchemy — ORM 2.0 vs 1.4

Verified against SQLAlchemy 2.0 docs (current release 2.0.51). The 1.4→2.0 split is the biggest fork: **2.0-style is the default in 2.0; 1.4 offered it opt-in via `future=True`.** Assume python + web-framework lore live elsewhere.

## Detect the version first

```bash
python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

- `2.x` → write 2.0 style unconditionally. `future=True` is the default; do not pass it.
- `1.4` → 2.0 style is available but opt-in; pass `future=True` on both engine and `Session`. Legacy `Query` still works.
- `< 1.4` → only legacy `Query`; `Mapped[]`/`mapped_column`/`DeclarativeBase`/`select()`-ORM-execution are unavailable. Recommend upgrade.
- `SQLModel` → 0.x, layered on SQLAlchemy 2.0 + Pydantic v2; models are `SQLModel` subclasses, but querying is SQLAlchemy `select()` via `session.exec()`. Version-check `sqlmodel.__version__` too.

## Model definition

DO — 2.0 typed declarative (`DeclarativeBase` + `Mapped[]` + `mapped_column`, both new in 2.0):

```python
from typing import Optional
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "user_account"
    id: Mapped[int] = mapped_column(primary_key=True)      # int -> INTEGER
    name: Mapped[str] = mapped_column(String(30))          # str -> VARCHAR, NOT NULL
    fullname: Mapped[Optional[str]]                        # Optional -> NULL, no mapped_column needed
    addresses: Mapped[list["Address"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")
```

- Datatype derives from the Python annotation; `Optional[...]` (or `| None`) controls nullability.
- DON'T use the pre-2.0 `Column` + untyped `declarative_base()` in new 2.0 code. It still runs, but you lose typing and it's the legacy path.
- DON'T mix styles: don't put `Column(Integer)` on the RHS of a `Mapped[int]` — use `mapped_column`.

## Engine + Session

DO:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

engine = create_engine("postgresql+psycopg://user:pw@host/db")  # future=True is DEFAULT in 2.0
SessionLocal = sessionmaker(engine, expire_on_commit=False)

with Session(engine) as session:      # context manager: closes; use session.begin() to auto-commit
    ...
    session.commit()
```

- DON'T pass `future=True` on 2.0 (redundant); DO pass it on 1.4 to get 2.0 behavior on engine **and** `Session`.
- DON'T rely on library-level `autocommit` — **removed** in 2.0. Use `with engine.begin()` (commit-on-exit) or `with engine.connect(): ... conn.commit()` (commit-as-you-go). A transaction autobegins on first statement.
- DON'T use removed connectionless execution: `engine.execute()`, `stmt.execute()`, `MetaData(bind=...)` are gone.

## Querying — `select()` + `execute`/`scalars`, not `Query`

DO:

```python
from sqlalchemy import select, func

stmt = select(User).where(User.name.in_(["a", "b"])).order_by(User.id)
users = session.scalars(stmt).all()                 # ORM objects
one   = session.scalars(select(User).where(User.name == "x")).one()
by_pk = session.get(User, 42)                        # PK lookup
count = session.scalar(select(func.count(User.id)))
```

- `select()` takes entities/columns **positionally** (not a list, not `whereclause=`).
- `Result` always yields **tuples** and does **not** dedupe. Use `.scalars()` for single-entity rows; use `.unique()` when joined-eager-loading (`joinedload`) — required or it raises.
- DON'T reach for the legacy `Query` (`session.query(...)`) in new code — discouraged in 2.0, kept only for legacy.

### 1.4/legacy → 2.0 mapping

| Legacy `Query` | 2.0 style |
|---|---|
| `session.query(User).get(42)` | `session.get(User, 42)` |
| `session.query(User).all()` | `session.scalars(select(User)).all()` |
| `.filter_by(name="x").one()` | `session.execute(select(User).filter_by(name="x")).scalar_one()` |
| `.filter(User.x==1).first()` | `session.scalars(select(User).where(User.x==1).limit(1)).first()` |
| `.join(Address).filter(...)` | `session.scalars(select(User).join(Address).where(...)).all()` |
| `.options(joinedload(...)).all()` | `session.scalars(select(User).options(joinedload(...))).unique().all()` |
| `.filter(...).update({...})` | `session.execute(update(User).where(...).values(...))` |
| `session.query(User).count()` | `session.scalar(select(func.count(User.id)))` |
| `.from_statement(text(...))` | `session.scalars(select(User).from_statement(text(...)))` |

Note: `select().join()` adds JOIN criteria (no implicit subquery); `in_()`/`not_in()` no longer accept a bare subquery.

## Async (`sqlalchemy.ext.asyncio`)

DO — async engine/session with an async driver:

```python
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

engine = create_async_engine("postgresql+asyncpg://user:pw@host/db")  # or sqlite+aiosqlite://
Session = async_sessionmaker(engine, expire_on_commit=False)

async with Session() as session:
    stmt = select(A).options(selectinload(A.bs))   # eager-load to avoid async lazy IO
    result = await session.execute(stmt)
    for a in result.scalars():
        ...
    await session.commit()
```

- DON'T trigger lazy loading under asyncio — implicit IO-on-attribute-access **fails**. Mitigate: eager-load (`selectinload`/`selectin`), set `expire_on_commit=False`, declare `lazy="raise"`, or use the `AsyncAttrs` mixin's `await obj.awaitable_attrs.rel` (added 2.0.13).
- DON'T share one `AsyncSession` across concurrent tasks (e.g. `asyncio.gather`) — not concurrency-safe; use one session per task.
- DO `await engine.dispose()` on shutdown to clean up the pool.

## Security — raw SQL escape hatches (NON-NEGOTIABLE)

The ORM binds parameters by default. The danger is `text()` and raw execution.

DO — always bind with named params:

```python
from sqlalchemy import text
session.execute(text("SELECT * FROM users WHERE name = :n"), {"n": user_input})
```

- DON'T ever f-string / `%` / `+`-concat user input into `text()` or any SQL string — that is SQL injection.

```python
# NEVER
session.execute(text(f"SELECT * FROM users WHERE name = '{user_input}'"))
```

- Identifiers (table/column names) can't be bound as params — never interpolate untrusted identifiers; validate against an allow-list.
- SQLModel: same rule — `session.exec(select(...))` is safe; any `text()` must use bound params.

## Sources
- https://docs.sqlalchemy.org/en/20/orm/quickstart.html
- https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- https://docs.sqlalchemy.org/en/20/changelog/
