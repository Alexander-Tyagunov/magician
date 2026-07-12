# Tortoise ORM — core digest

Async-only ORM. v1.1.7 (Python 3.10+). Every query is `await`ed.

DO await `Tortoise.init(db_url=..., modules={"models":[...]})`; `generate_schemas()` is dev-only — use migrations in prod.
DO fetch relations eagerly: `select_related` (FK) and `prefetch_related` (M2M/reverse FK) to kill N+1.
DO use `get_or_none()` when a row may be missing; `get()` raises `DoesNotExist`/`MultipleObjectsReturned`.
DO batch with `bulk_create`/`bulk_update`; compose with `Q`, `F`, `annotate`, `values`/`values_list`.
DO wrap multi-write in `@atomic()` or `async with in_transaction():` (nestable).
DON'T call sync-blocking code in the event loop; don't mutate objects without `await obj.save()`.

SECURITY — raw SQL is the injection hole. `RawSQL(...)` (in `filter`/`annotate`) and `.raw(sql)` take a raw string.
DON'T f-string/`.format`/concat user input into `RawSQL`/`.raw`. Prefer ORM filters (`name=x`) — they bind params. If raw is unavoidable, never embed untrusted values.

VERSION CUE: v1.0 shipped the built-in migration CLI `tortoise`; **aerich is now legacy** — prefer the built-in tool.

Commands: `tortoise init` · `tortoise makemigrations` · `tortoise migrate` (alias `upgrade`) · `tortoise downgrade` · `tortoise history` · `tortoise heads` · `tortoise sqlmigrate`.

Deep dive when writing non-trivial tortoise — read lore/tortoise/{patterns}.md

## Sources
tortoise.github.io (index, getting_started, query, expressions, transactions, migration); pypi.org/project/tortoise-orm 1.1.7
