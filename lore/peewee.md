# Peewee — core lore

Version: current **4.x** (4.1.2). No deps. Sync API stable 3.x→4.x. asyncio added in 4.0 (`playhouse.pwasyncio`, stable 4.0.8); 4.0 dropped Python 2.

DO
- Model: `class User(Model): name=CharField()`; `Meta.database=db`.
- Query binds params via operators: `User.select().where(User.name==x)`; `&` `|` `~`, `.in_([...])`.
- Read: `.get()` raises `DoesNotExist`; `.get_or_none()`; PK `User[pk]`/`get_by_id`.
- Write: `create(**k)`, `save(only=[...])`; bulk `insert_many(rows).execute()`, `bulk_create(objs, batch_size=N)`. Wrap multi-writes in `with db.atomic():`.
- N+1: `Tweet.select(Tweet,User).join(User)` or `prefetch(q, sub)`.
- Raw (parameterized): `User.raw('...id=?', pk)`; `db.execute_sql('...=?', (v,))`. Placeholder `db.param` (`?` sqlite, `%s` mysql/pg); driver binds.
- Async (4.0+): `playhouse.pwasyncio`; `await User.acreate()`, `await db.list(q)`.

DON'T
- ❌ f-string/`%`/concat into `raw()`, `execute_sql()`, `SQL('...')` — injection. Pass values as params, never interpolate.
- ❌ `and`/`or`/`not` or Python `in` in `.where()` — use `&`/`|`/`~`, `.in_()`.
- ❌ `create()`/`save()` in a loop — N queries; use `insert_many`/`atomic`.
- ❌ blind `save()` rewrites all fields — use `only=[...]` or Meta `only_save_dirty=True`.

Commands: `pip install peewee`; introspect → `python -m pwiz -e sqlite app.db`; migrate via `playhouse.migrate`.

Deep dive when writing non-trivial peewee — read lore/peewee/{patterns}.md

Sources: docs.peewee-orm.com/en/latest (querying, writing, query_operators, api, pwasyncio); pypi.org/project/peewee
