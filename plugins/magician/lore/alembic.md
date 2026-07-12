# Alembic — core digest

Migrations for SQLAlchemy. Version cue: `alembic check` since 1.9.0; `compare_type=True` default since 1.12.0; latest 1.18.x.

DO
- Set `target_metadata = Base.metadata` in `env.py`; regen via `revision --autogenerate`.
- ALWAYS review autogen output — it's imperfect; table/column renames emit drop+add (fix by hand).
- Name every constraint (`name="uq_..."`); anonymous ones aren't detected.
- Bound params for raw SQL: `op.execute(sa.text("update t set x=:x").bindparams(x=v))`.
- Data migrations: lightweight `table()/column()` + `op.bulk_insert()`, not string SQL.
- Always write `downgrade()`. Enable `compare_server_default=True` if needed (off by default).
- SQLite alters: `with op.batch_alter_table("t") as b:` and `render_as_batch=True`.

DON'T
- Never f-string/concat/%-format user or dynamic input into `op.execute()`/`sa.text()` — SQL injection; parameterize.
- Don't edit applied migrations — add a new revision.
- Don't import app ORM models into migrations (schema drifts); redefine minimal `table()`.
- Don't trust autogen for CHECK/PK/EXCLUDE, sequences, or non-native Enum — add by hand.
- Don't leave extraneous DB tables unfiltered (`include_object`) — they emit drops.

Commands: `alembic init`, `revision --autogenerate -m "msg"`, `upgrade head`, `downgrade -1`, `current`, `history`, `heads`, `merge`, `stamp head`, `check`, `upgrade --sql` (offline).

Deep dive when writing non-trivial alembic — read lore/alembic/{migration-patterns}.md

## Sources
alembic.sqlalchemy.org/en/latest/ (autogenerate, batch, cookbook, api/commands)
