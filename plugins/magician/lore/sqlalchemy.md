# SQLAlchemy — core lore

Version: default to **2.0 style**. `select()`+`session.execute()`/`session.scalars()`; `DeclarativeBase`+`Mapped[]`/`mapped_column()`; async via `sqlalchemy.ext.asyncio`. The `select()` paradigm landed in 1.4, finalized in 2.0. Legacy `Query`/`session.query()`/`declarative_base()` still work but are legacy — don't write new.

DO
- Model: `class Base(DeclarativeBase): pass`; `id: Mapped[int] = mapped_column(primary_key=True)`; `Optional[]`→nullable.
- Query: `session.scalars(select(User).where(User.name==x)).all()`; single `.one()`/`.one_or_none()`; PK fetch `session.get(User, pk)`.
- Session as ctx mgr: `with Session(engine) as s: ...; s.commit()`. Async: `AsyncSession`+`async_sessionmaker`, `await s.scalars(...)`.
- Raw SQL: `text("... WHERE id=:x")` + params `{"x": v}`. Bind ALL user input.

DON'T
- ❌ `text(f"...{v}")` or string-concat SQL — injection. Never interpolate user input into SQL; use bound params.
- ❌ New code on legacy `Query` API, or `autocommit` (removed in 2.0) — use `engine.begin()` / commit-as-you-go.
- ❌ Mapped attrs without a `Mapped[...]` annotation in 2.0 declarative.

Commands: `pip install "sqlalchemy>=2"`; migrate via Alembic — `alembic revision --autogenerate -m msg`, `alembic upgrade head`.

Deep dive when writing non-trivial sqlalchemy — read lore/sqlalchemy/{orm-2.0-vs-1.4,sessions-and-queries}.md

Sources: docs.sqlalchemy.org/en/20 (quickstart, migration_20, core/connections); alembic.sqlalchemy.org
