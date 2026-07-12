# tortoise — Async models & pitfalls

Async-native ORM (asyncio, Django-inspired). Fits FastAPI/Sanic/async stacks.
Current line: **1.x** (latest 1.1.7). **1.0 was a breaking major** — assume 1.0+ unless
pinned. Requires **Python 3.10+** (raised in 1.0.0). Everything is `await`-ed; there is
no sync API. Assume python + web-framework lore live elsewhere.

Drivers: PostgreSQL→`asyncpg`, SQLite→`aiosqlite`, MySQL/MariaDB→`asyncmy`, MSSQL/Oracle→`asyncodbc`.

## Version splits you MUST branch on
- **`primary_key=` / `db_index=`** replaced `pk=` / `index=` in **0.21.0**. Old `pk=True`
  still works with a warning — DON'T write it in new code.
- **`use_tz` defaults `True` in 1.0.0** (was `False`). Naive datetimes now get coerced —
  verify tz handling on upgrade.
- **`Tortoise.init()` returns a `TortoiseContext` in 1.0** (context-first architecture).
- **`from tortoise import connections` deprecated in 1.0** → use `get_connection(alias)` /
  `get_connections()`.
- **pytz dropped in 1.0** → stdlib `zoneinfo`.
- Package rename **0.24.0**: `pypika` → `pypika_tortoise`.

## Models & fields
DO declare a PK explicitly; DON'T rely on the implicit auto `IntField` `id` for anything
you care about (use `BigIntField`/`UUIDField` for real keys).

```python
from tortoise import fields
from tortoise.models import Model

class Event(Model):
    id = fields.BigIntField(primary_key=True)
    name = fields.CharField(max_length=255)          # CharField REQUIRES max_length
    rating = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    created = fields.DatetimeField(auto_now_add=True)  # Python-side, no DB DEFAULT
    tournament = fields.ForeignKeyField("models.Tournament", related_name="events")
    teams = fields.ManyToManyField("models.Team", related_name="events")

    class Meta:
        table = "event"
        # constraints = [...]  # preferred in new code
        # unique_together = (("name", "tournament"),)  # legacy compound unique
```

- DON'T assume `auto_now`/`auto_now_add` set a DB default — they're **purely Python**. For
  a DB-level default use `db_default=Now()`.
- `pk` is an alias to whatever field is primary — `.filter(pk=...)` always works.
- Meta: prefer `constraints` (UniqueConstraint/CheckConstraint) over legacy
  `unique_together`; `indexes` for compound non-unique.

## Init & FastAPI wiring
Standalone / scripts:
```python
from tortoise import Tortoise, run_async

async def main():
    await Tortoise.init(db_url="sqlite://db.sqlite3", modules={"models": ["app.models"]})
    await Tortoise.generate_schemas()   # DEV ONLY — not a migration tool

run_async(main())
```
- DON'T ship `generate_schemas()` as your prod schema strategy — it's for dev/`:memory:`.
  Use migrations (below).

FastAPI — DO use the **lifespan class** `RegisterTortoise` (current), not the older
`register_tortoise` function:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(
        app,
        config=TORTOISE_ORM,          # one of: config | config_file | (db_url, modules)
        add_exception_handlers=True,   # DEV convenience — see warning
    ):
        yield

app = FastAPI(lifespan=lifespan)
```
- Supply **exactly one** of `config` / `config_file` / `(db_url, modules)` — mixing raises
  `ConfigurationError`.
- DON'T enable `add_exception_handlers=True` in production — the auto handlers for
  `DoesNotExist`/`IntegrityError` **may leak data**.

## Queries — kill N+1
Everything returns a lazy QuerySet; `await` to execute.
```python
await Event.filter(rating__gt=5).first()      # None if none
await Event.get(id=1)                          # raises DoesNotExist / MultipleObjectsReturned
await Event.get_or_none(id=1)                  # None instead of raising
await Event.all().values("id", "name")         # dicts
obj, created = await Event.get_or_create(defaults={"rating": 0}, name="x")
await Event.bulk_create([Event(name=n) for n in names])  # ~1 query
```
- **DO `select_related("tournament")` for FK / one-to-one** (single JOIN, one query).
- **DO `prefetch_related("teams", "tournament__events")` for M2M / reverse FK** (one extra
  query per relation level — still bounded, not N+1).
- **DON'T loop `await obj.tournament` per row** — that IS the N+1. Prefetch up front.
- Complex filters: pass `Q(...) | Q(...)` objects; column refs via `F("field")`.

## Transactions
```python
from tortoise.transactions import in_transaction, atomic

async with in_transaction():           # commits on clean exit, rolls back on exception
    await Event.create(name="a")

@atomic()                              # same, as a decorator
async def move(): ...
```
- Pass a connection name (`in_transaction("replica")`) only with multiple DBs.
- Nesting uses **savepoints** (PG/MySQL/MSSQL/SQLite). DON'T nest transaction blocks inside
  `asyncio.gather` concurrent tasks — transaction state is sequential, not concurrent.

## Migrations
1.0 ships a **built-in framework** (Aerich is now the legacy alternative). Add
`"migrations": "app.migrations"` per app in config, then:
```
tortoise init            # create migration packages
tortoise makemigrations  # --name / --empty
tortoise migrate         # alias: upgrade  (apply)
tortoise downgrade       # unapply
tortoise history | heads # applied (DB) vs on-disk heads
tortoise sqlmigrate      # print SQL, don't run  (--backward)
```
- Legacy path (pre-1.0 projects / Aerich): `aerich init`, `init-db`, `migrate`, `upgrade`,
  `downgrade`. DON'T mix the two systems in one project.

## SECURITY — raw SQL escape hatches (non-negotiable)
Normal QuerySet filters bind parameters — safe. The raw paths are injection-prone.

- **DO parameterize** via the connection API. `values` is a **sequence of positional
  params**; `query` must be pre-parametrized for the dialect (placeholder style is
  driver-specific — `$1…` asyncpg, `?` aiosqlite/asyncmy):
```python
from tortoise import connections
conn = connections.get("default")
# PostgreSQL / asyncpg:
await conn.execute_query("SELECT * FROM event WHERE rating > $1", [min_rating])
rows = await conn.execute_query_dict("SELECT * FROM event WHERE name = $1", [name])
```
- **DON'T** f-string / `%` / `+` user input into SQL — the cardinal injection sin:
```python
# NEVER:
await conn.execute_query(f"SELECT * FROM event WHERE name = '{name}'")
await Event.raw(f"SELECT * FROM event WHERE name = '{name}'")
```
- `Model.raw(sql)` and the `RawSQL` expression bypass filter binding — only use with
  constant/whitelisted SQL, never with request data.
- `execute_script(query)` takes **no `values`** and runs verbatim — never feed it user input.
- Prefer ORM filters over raw entirely; reach for raw only for DB features the ORM can't
  express, and keep every dynamic value in the `values` list.

## Sources
- https://tortoise.github.io/
- https://tortoise.github.io/getting_started.html
- https://tortoise.github.io/models.html
- https://tortoise.github.io/query.html
- https://tortoise.github.io/transactions.html
- https://tortoise.github.io/databases.html
- https://tortoise.github.io/contrib/fastapi.html
- https://tortoise.github.io/migration.html
- https://tortoise.github.io/CHANGELOG.html
