# sqlalchemy — Sessions, queries & pitfalls

Scope: SQLAlchemy 2.0 (current). Assumes Python + web-framework lore live elsewhere.
2.0 style = `select()` + `session.execute()`/`scalars()`, `Mapped[]`/`mapped_column`,
`DeclarativeBase`, async via `sqlalchemy.ext.asyncio`. The 1.4 legacy `Query` API
(`session.query(...)`) still works but is undocumented long-term legacy — don't write new code in it.

## Session lifecycle (unit of work)

Session tracks changes to mapped objects and flushes them as one unit of work; an identity map keeps
one object per PK per Session. It is ONE database transaction — mutable, stateful.

DO
- Scope a Session to a single logical operation (one web request, one task). Short-lived.
- Use it as a context manager so it always closes:
  ```python
  with Session(engine) as session:
      session.add(obj)
      session.commit()
  ```
- Wrap the transaction with `session.begin()` for auto commit/rollback:
  ```python
  with Session(engine) as session, session.begin():
      session.add(obj)   # commits on success, rolls back on exception
  ```
- Create one module-level `sessionmaker` (like the Engine) and call it per operation:
  ```python
  Session = sessionmaker(engine)
  ```
- After a failed `flush()`/`commit()`, call `session.rollback()` before reusing the Session — it goes
  "inactive" until you do.

DON'T
- DON'T share a Session across threads or asyncio tasks. Model is Session-per-thread,
  AsyncSession-per-task. For a global-ish handle use `scoped_session` / `async_scoped_session`.
- DON'T keep a long-lived/global Session for the whole app.
- DON'T expect old attribute values after `commit()` — objects are expired (see expire_on_commit).

### commit / rollback / close / expire_on_commit
- `commit()` flushes first, then COMMITs, releases the connection to the pool, and **expires all
  objects** — next attribute access emits a fresh SELECT.
- `rollback()` reverts the transaction; pending objects are expunged, objects expired regardless of
  `expire_on_commit`.
- `close()` runs `expunge_all()` and releases resources.
- `expire_on_commit=True` is default. Set `sessionmaker(engine, expire_on_commit=False)` when you read
  attributes after commit (e.g. serializing in a web view) — avoids `DetachedInstanceError` / surprise
  SELECTs.

## Querying (2.0 style)

- `session.execute(stmt)` → `Result` of `Row` tuples. Selecting one ORM entity gives 1-element rows;
  selecting columns gives one column each per row (NOT entities).
- `session.scalars(stmt)` → `ScalarResult` of entities directly (== `execute(...).scalars()`).

DO
- Fetch entities with `scalars()`; unpack with the right terminator:
  ```python
  users = session.scalars(select(User).where(User.active)).all()
  user  = session.scalars(select(User).where(User.id == 5)).one()          # exactly 1, else raises
  user  = session.execute(select(User).filter_by(id=5)).scalar_one()       # 1-col row → 1 value
  maybe = session.execute(select(User).filter_by(email=e)).scalar_one_or_none()
  ```
- Use `session.get(User, pk)` for PK lookup — may skip the query if already in the identity map.
- Terminators: `.all()` `.first()` `.one()` `.one_or_none()`; scalar forms `.scalar_one()`
  `.scalar_one_or_none()` `.scalar()`.

DON'T
- DON'T forget `.unique()` on results that use `joinedload` for collections (see below).

## relationship() loading — kill N+1

Default is `lazy="select"`: related objects load lazily on attribute access → for N parents, N+1
SELECTs. Set loader strategy per-query with `.options(...)`.

DO
- **Collections (one-to-many / many-to-many): `selectinload()`** — generally the best strategy. Emits
  one extra SELECT with `IN (parent PKs)`:
  ```python
  session.scalars(select(User).options(selectinload(User.addresses))).all()
  ```
- **Many-to-one / scalar: `joinedload()`** — most general there; add `innerjoin=True` for NOT NULL FKs:
  ```python
  select(Address).options(joinedload(Address.user, innerjoin=True))
  ```
- With `joinedload()` on a COLLECTION, call `.unique()` on the result (JOIN duplicates parent rows).
- Already JOINed in your query? Route rows into the collection with `contains_eager()`:
  ```python
  select(User).join(User.addresses).options(contains_eager(User.addresses))
  ```
- Guard against accidental lazy loads (e.g. detached objects) with `raiseload()` /
  `lazy="raise"` / `lazy="raise_on_sql"`.

DON'T
- DON'T reach for `subqueryload()` — mostly legacy, superseded by `selectinload()`.
- DON'T lazy-load in a loop over a result set — that IS the N+1. Eager-load up front.
- DON'T iterate relationship attributes after the Session closed without eager loading first.

## Bulk operations (2.0 unified under session.execute)

DO
- Bulk INSERT: pass a `list[dict]` (keys = mapped attribute names) as params:
  ```python
  session.execute(insert(User), [{"name": "a"}, {"name": "b"}])
  ```
- Get rows back: `session.scalars(insert(User).returning(User), [...])` (RETURNING on all built-in
  backends except MySQL; MariaDB ok). Use `Insert.returning.sort_by_parameter_order` (2.0.10) to
  match input order.
- Bulk UPDATE by PK: `session.execute(update(User), [{"id":1,"name":"x"}, ...])` — each dict needs the
  full PK. No RETURNING in this mode.
- Set-based UPDATE/DELETE (no params list):
  ```python
  session.execute(update(User).where(User.active == False).values(archived=True))
  session.execute(delete(User).where(User.id.in_(ids)))
  ```

DON'T
- DON'T assume ORM cascades run on set-based UPDATE/DELETE — they don't. Rely on DB
  `ON UPDATE/DELETE CASCADE`.
- DON'T leave stale in-memory objects: `synchronize_session` defaults to `"auto"` (`"fetch"` where
  RETURNING exists, else `"evaluate"`). Use `"fetch"` for correctness, `False` only if no objects are
  loaded. `"evaluate"` can't handle complex WHEREs.

## Connection pooling

Default pool is `QueuePool` (async engines get `AsyncAdaptedQueuePool`). SQLite `:memory:` uses
`SingletonThreadPool`. Configure on `create_engine(...)`.

DO
- Size deliberately: `pool_size` (default **5**) persistent conns + `max_overflow` (default **10**)
  burst → max concurrent = `pool_size + max_overflow`. `pool_timeout` (default 30s) is the wait for a
  free conn.
- Enable `pool_pre_ping=True` (1.2+) behind connections that can drop (LB/DB restart). It tests
  liveness on checkout (dialect ping or `SELECT 1`), recycling dead conns. Does NOT rescue a conn
  dropped mid-transaction.
- Set `pool_recycle=<seconds>` under MySQL/proxies that kill idle conns (recycle checked at checkout;
  default -1 = off).
- Use `NullPool` when forking / multiprocessing (or to disable pooling); it's asyncio-compatible.
  Always `engine.dispose()` in a forked child before reuse.

DON'T
- DON'T set `pool_size` far above your DB's `max_connections` ÷ app instances.
- DON'T share one Engine's pooled connections across `fork()` without `dispose()`.

## Security — raw SQL

DO
- Use `text()` with bound params ONLY; pass values separately:
  ```python
  session.execute(text("SELECT * FROM users WHERE name = :n"), {"n": user_input})
  # or: text("... = :n").bindparams(n=user_input)
  ```

DON'T
- **NEVER** f-string / concatenate / `%`-format user input into SQL — direct SQL injection:
  ```python
  text(f"SELECT * FROM users WHERE name = '{user_input}'")   # WRONG
  ```
- Bound params are values, not identifiers — you can't parameterize table/column names; whitelist those
  against a fixed set instead.

## Version notes / fallbacks
- `Mapped[...]` + `mapped_column()` + `DeclarativeBase`: 2.0. In 1.4 use `Column` +
  `declarative_base()` (moved to `sqlalchemy.orm` in 2.0).
- `select()`+`execute()`/`scalars()`: canonical in 2.0; usable in 1.4 via
  `create_engine(..., future=True)`. Legacy `session.query()` runs but is deprecated-by-docs.
- Async: `sqlalchemy.ext.asyncio` — `create_async_engine`, `AsyncSession`, `async_sessionmaker`
  (1.4+). One `AsyncSession` per task; no concurrent `await`s on one session.
- SQLModel (0.x, Pydantic v2) wraps SQLAlchemy 2.0: same Session/select semantics, same threading and
  `text()` rules.

## Sources
- https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
- https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
- https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html
- https://docs.sqlalchemy.org/en/20/core/pooling.html
- https://docs.sqlalchemy.org/en/20/core/connections.html
- https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
