# alembic — Migration patterns

Schema migration tool for SQLAlchemy. Pairs with the SQLAlchemy lore. Latest line: **1.18.x** (1.18.6). Assume a working SQLAlchemy `Base`/`metadata` exists.

## Setup & env.py

DO
- `alembic init alembic` — scaffolds the migration env (generic template). Templates: `generic`, `pyproject`, `async`, `multidb` (`alembic list_templates`).
- Point autogenerate at your models in `env.py`:
  ```python
  from myapp.models import Base
  target_metadata = Base.metadata   # 2.0 DeclarativeBase or 1.4 declarative — both expose .metadata
  ```
- Set the URL: `sqlalchemy.url` in `alembic.ini`, or override in `env.py` (`config.set_main_option`) to read from env vars / app settings. Keep secrets out of the ini.
- SQLAlchemy 2.0 **async** engines → use the `async` template: it runs the (sync) migration body via `connection.run_sync(do_run_migrations)` inside `async def run_async_migrations()`.

DON'T
- Don't leave `target_metadata = None` and expect autogenerate to work.
- Don't import a partial model tree; autogen diffs only what's imported → spurious `drop_table` for models it never saw.

## revision + autogenerate (REVIEW EVERY DIFF)

DO
- Empty scripted migration: `alembic revision -m "add account table"` → fill `upgrade()`/`downgrade()` with `op.*`.
- Autogenerate: `alembic revision --autogenerate -m "add account table"`. Then **read the generated file before applying** — autogenerate is explicitly "not intended to be perfect."
- Enable the comparisons autogen doesn't do by default in `context.configure(...)`:
  ```python
  context.configure(
      connection=connection,
      target_metadata=target_metadata,
      compare_type=True,             # default True since 1.12.0
      compare_server_default=True,   # OFF by default — opt in
      render_as_batch=True,          # SQLite-safe, see batch section
  )
  ```

Autogenerate **detects reliably**: table add/drop, column add/drop, nullable changes, basic index & explicitly-named unique constraint changes, basic FK changes.

Autogenerate **MISSES / needs care** — hand-write these:
- **Table renames** → emitted as drop + create (data loss). Replace with `op.rename_table('old','new')`.
- **Column renames** → emitted as add + drop (data loss). Replace with `op.alter_column('t','old', new_column_name='new')`.
- **Server default changes** → only seen if `compare_server_default=True`, and "cannot always produce accurate results."
- **Type changes** → only if `compare_type=True`; compares shared args only (length/precision); args present on one side but not the other aren't compared.
- **Anonymous constraints** → can't be detected or dropped; give every constraint a name (via `naming_convention` on `MetaData`).
- Not yet detected: standalone PK/CHECK/EXCLUDE adds-drops, sequence add/drop.

DON'T
- Don't blindly `upgrade head` an autogen script — a mistaken rename destroys a column's data.
- Don't rely on Enum diffs on backends without native ENUM.

## upgrade / downgrade

DO
- `alembic upgrade head` (latest), `alembic upgrade +2`, `alembic upgrade ae1027a6` (partial id).
- `alembic downgrade -1` (one step), `alembic downgrade base` (unversion).
- Inspect: `alembic current`, `alembic history --verbose`, `alembic heads`.
- Write a real `downgrade()` — the inverse of `upgrade()`. It's your rollback.

DON'T
- Don't hand-edit the `alembic_version` table; use `alembic stamp <rev>` to set state without running SQL.

## Never edit applied migrations in shared history

DO
- Once a revision is merged/shared (teammates or prod have run it), treat it as immutable. Fix mistakes with a **new** revision on top.
- Amend freely only while a revision is still local and unapplied.

DON'T
- Don't change the logic, `revision`, or `down_revision` of an already-applied script — collaborators' DBs and the revision graph reference that stable id; editing it desyncs `alembic_version` and breaks merges/`depends_on`.

## Branching & merge

DO
- Branches arise when two revisions share the same `down_revision` (e.g. two feature branches merged) → **multiple heads**; `upgrade head` then errors on ambiguity.
- Diagnose: `alembic heads`, `alembic branches --verbose`.
- Reconcile: `alembic merge -m "merge heads" heads` (or name the two: `alembic merge -m "merge" ae1027 27c6a`). Generates a script with `down_revision = ('ae1027a6acf','27c6a30d7c24')`.
- Target explicitly when needed: `alembic upgrade heads` (all), `alembic upgrade <label>@head` (one branch).
- Long-lived parallel lineages: `branch_labels`, multiple `version_locations`, and `depends_on=` to reference another stream without merging.

DON'T
- Don't put schema work in a merge revision beyond reconciliation between branches.
- Don't leave multiple heads unmerged in a repo others deploy — CI `alembic upgrade head` will break.

## Offline / SQL mode (`--sql`)

DO
- Emit SQL for a DBA instead of executing: `alembic upgrade ae1027a6 --sql > migration.sql` (SQL → stdout, logs → stderr).
- Give a start when there's no DB to read `alembic_version` from: `alembic upgrade 1975ea83:ae1027a6 --sql` (the `start:end` syntax is offline-only).
- Branch offline behavior in `env.py`: `if context.is_offline_mode(): run_migrations_offline() else: run_migrations_online()`.

DON'T
- Don't use data-dependent migrations in `--sql` mode — a migration that `SELECT`s rows into memory "will not work in --sql mode." Use Alembic op directives, which run both online and offline.
- Autogenerate (`copy_from`/batch) does not support offline mode.

## Batch mode (SQLite ALTER)

SQLite "has almost no support for ALTER" → Alembic does move-and-copy (create new table, `INSERT..SELECT`, drop, rename).

DO
- Wrap SQLite alters in a batch block; omit table/schema names inside:
  ```python
  with op.batch_alter_table("account") as batch_op:
      batch_op.add_column(sa.Column("foo", sa.Integer))
      batch_op.alter_column("bar", nullable=False)
      batch_op.drop_column("baz")
  ```
- Turn on `render_as_batch=True` in `context.configure` so autogen emits batch blocks — safe everywhere (only activates on SQLite).
- Give constraints names via `naming_convention` (requires SQLAlchemy ≥ 0.9.4) so `batch_op.drop_constraint("fk_...", type_="foreignkey")` can target them — SQLite allows unnamed constraints that can't otherwise be dropped.
- Force move-and-copy on any backend with `recreate="always"` when needed.

DON'T
- Don't batch-alter a table that other FKs reference with enforced referential integrity (Postgres/MySQL InnoDB) without manually dropping/recreating those FKs — the target table is dropped mid-operation.
- Don't assume unnamed CHECK constraints survive recreate; named CHECKs auto-include (Alembic 1.7+), unnamed ones are dropped unless passed explicitly.

## Raw SQL safety (via SQLAlchemy)

DO
- Data migrations run raw via `op.execute()` / `op.get_bind()`. Bind parameters — never interpolate user/runtime input:
  ```python
  from sqlalchemy import text
  op.get_bind().execute(text("UPDATE t SET x=:v WHERE id=:i"), {"v": v, "i": i})
  ```

DON'T
- Don't f-string / concat values into `text()` or `op.execute("..." + val)` — injection. Bind `:params`, pass a dict.

## Sources
- https://alembic.sqlalchemy.org/en/latest/
- https://alembic.sqlalchemy.org/en/latest/tutorial.html
- https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- https://alembic.sqlalchemy.org/en/latest/batch.html
- https://alembic.sqlalchemy.org/en/latest/offline.html
- https://alembic.sqlalchemy.org/en/latest/branches.html
