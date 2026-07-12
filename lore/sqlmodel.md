# SQLModel — core

SQLModel = thin layer over Pydantic v2 + SQLAlchemy 2.0. Latest 0.0.x (0.0.39); pins SQLAlchemy >=2.0.14,<2.1 and Pydantic >=2.11; Python >=3.10. Assume 2.0 style, not the legacy 1.4 Query API.

DO define tables `class Hero(SQLModel, table=True):` with `id: int | None = Field(default=None, primary_key=True)`; `table=True` is required or it's a plain Pydantic model.
DO query with `select(Hero).where(Hero.name == name)` then `session.exec(stmt)` — SQLModel's `exec` returns typed model rows; SQLAlchemy's `session.execute` returns Row tuples (use `.scalars()`). Don't mix them up.
DO bind params — `.where(col == value)` emits `?`/`:p` placeholders; user input never touches SQL text. Always `session.commit()`; `session.refresh(obj)` after commit to read DB-generated ids.
DO async via `from sqlmodel.ext.asyncio.session import AsyncSession` + SQLAlchemy `create_async_engine`; `await session.exec(...)`.
DON'T build raw SQL from f-strings/concat — injection. `text()` MUST use bound params: `session.exec(text("... WHERE name=:n"), params={"n": n})`, never `text(f"...{n}")`.
DON'T reuse a `table=True` model as request body (mass-assignment); make separate non-table `SQLModel` schemas.
DON'T forget `SQLModel.metadata.create_all(engine)` (or use Alembic for migrations — create_all won't ALTER).

Commands: `pip install sqlmodel` · `alembic init/revision --autogenerate/upgrade head`.

Deep dive when writing non-trivial sqlmodel — read lore/sqlmodel/{patterns}.md

Sources: sqlmodel.tiangolo.com · docs.sqlalchemy.org · pypi.org/project/sqlmodel
