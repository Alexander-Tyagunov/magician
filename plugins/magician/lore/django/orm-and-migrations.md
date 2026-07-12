# django — ORM & migrations

Deep-dive. Assumes Python + `django.md` base lore. Verify version facts against docs.djangoproject.com. Confirmed against current stable docs (Django 5.2 LTS / 6.0). Async ORM matured 4.1→5.x; state your target.

## Models & QuerySets (lazy)

DO
- Treat QuerySets as **lazy** — chaining `.filter().exclude()` fires **zero** queries. DB is hit only on evaluation: iteration, `list()`, `bool()`, `len()`, `in`, pickling, shell `repr()`.
- Reuse one evaluated QuerySet's **result cache**: assign `qs = Model.objects.all()` once, then iterate/`len()`/`in` against `qs` — no re-query.
- `get()` for exactly one row (raises `DoesNotExist` / `MultipleObjectsReturned`); `filter()` for zero-or-more; `get_object_or_404()` in views.

DON'T
- DON'T re-index expecting cache — `qs[5]` then `qs[5]` hits the DB **twice** (slicing/indexing doesn't populate the cache unless the whole set is already evaluated).
- DON'T call `exists()`/`count()`/`contains(obj)` when you'll *also* consume the rows — extra queries on top of evaluation; use `if qs:` / `len(qs)` / `obj in qs`. Inverse: if you *only* need the bool/count, DO use them (cheaper than pulling rows).

## Kill N+1 — the cardinal sin

DO
- **`select_related(*fields)`** for forward `ForeignKey` / `OneToOne` — one **SQL JOIN**, single query.
- **`prefetch_related(*fields)`** for `ManyToMany` and **reverse FK** — separate query per relation, joined in Python.
- Combine: `Book.objects.select_related("publisher").prefetch_related("authors")`.
- Shape prefetches: `Prefetch("authors", queryset=Author.objects.filter(active=True))`. Prefetch onto an existing list: `prefetch_related_objects(objs, "authors")`.

DON'T
- DON'T loop over parents touching `.related` / `.set.all()` — 1 + N queries. Push into `select_related`/`prefetch_related`.
- DON'T `select_related` a M2M or reverse-FK (can't JOIN one-to-many cleanly) → use `prefetch_related`.

```python
# N+1: one query for books, one per book for publisher
for b in Book.objects.all(): print(b.publisher.name)
# Fixed: single JOIN
for b in Book.objects.select_related("publisher"): print(b.publisher.name)
```

## Trim columns — `.only()` / `.defer()`

DO
- `.only("title", "pk")` to load *only* those columns; `.defer("body")` to load all *but* those. Best for wide text/blob columns you rarely touch. Profile first.

DON'T
- DON'T `.only()`/`.defer()` then access a deferred field in a loop — each access fires a **separate** query (a pessimization). PK is always fetched.

## `F()` and `Q()` expressions

DO
- **`F("field")`** references a column in-DB — atomic updates without read-modify-write races, and field-to-field compares:
  `Product.objects.filter(pk=1).update(views=F("views") + 1)` (no race).
  `Entry.objects.filter(comments__gt=F("pingbacks") * 2)`.
- **`Q(...)`** for OR / complex boolean logic: combine with `&`, `|`, `^` (XOR), negate with `~`.
  `Model.objects.filter(Q(a=1) | Q(b=2))`.

DON'T
- DON'T place a keyword arg **before** a `Q` object in a call — `Q` args must come first, else `SyntaxError`/`TypeError`.
- DON'T span joins in `F()` inside `.update()` — raises `FieldError` (update refs must be local fields). Note `F()` values are stale on the Python instance after save; `refresh_from_db()`.

## Transactions — `transaction.atomic`

DO
- Wrap multi-write units: `@transaction.atomic` or `with transaction.atomic():`. Commit on clean exit, rollback on exception.
- Nest freely — inner blocks use **savepoints**. `atomic(durable=True)` asserts a block is outermost (raises `RuntimeError` if nested).
- Catch DB errors **around** the atomic block, not inside:
  ```python
  try:
      with transaction.atomic():
          generate_relationships()
  except IntegrityError:
      handle()
  ```
- Defer side effects (email, tasks, cache bust) with `transaction.on_commit(fn)` — runs only after commit; discarded on rollback.
- Lock rows inside atomic: `Model.objects.select_for_update().get(pk=...)` (blocks concurrent writers).
- `ATOMIC_REQUESTS=True` per-DB wraps each view in a transaction (heavier under load; wraps only the view, not middleware/streaming).

DON'T
- DON'T swallow `IntegrityError`/`DatabaseError` *inside* atomic — transaction is already broken; further queries raise `TransactionManagementError`.
- DON'T assume model attributes revert on rollback — **only the DB rolls back**; restore Python field values yourself.
- DON'T mix transactions with async ORM — raises `SynchronousOnlyOperation`; wrap sync ORM in `sync_to_async`.

## Bulk operations

DO
- `Model.objects.bulk_create([...])` / `bulk_update(objs, ["field"])` collapse N INSERTs/UPDATEs into few queries. Tune `batch_size=`; `ignore_conflicts=True` / `update_conflicts=` for upserts.

DON'T
- DON'T expect `save()`/`pre_save`/`post_save` signals to fire (nor PKs populated on some backends) — read the caveats. Loop-`save()` for a handful of rows is fine; bulk is for volume.

## Migrations

DO
- `makemigrations [app]` to author from model changes; `migrate` to apply. Read `makemigrations` output — "it's not perfect." Inspect with `sqlmigrate app 0003` (SQL) and `showmigrations` (status).
- Data migrations: `makemigrations --empty app`, then `migrations.RunPython(forward, backward)`. Inside, use **historical models** via `apps.get_model("app", "Model")` — never import the live model.
- Give `RunPython`/`RunSQL` a reverse callable or `migrate app 0002` (reverse) raises `IrreversibleError`. Cross-app `RunPython`: list every involved app's latest migration in `dependencies`.
- DDL-transactional DBs (PostgreSQL, SQLite) wrap each migration in one transaction by default; set `atomic = False` on the `Migration` for long/batched data ops (MySQL/Oracle lack DDL transactions). Squash sprawl with `squashmigrations app 0004`.

DON'T
- **DON'T edit a migration already applied anywhere** (shared/CI/prod). Migrations are an append-only ledger — editing an applied one desyncs recorded state from schema. Add a **new** migration. Editing is fine only for still-unapplied local files.
- DON'T import live models in `RunPython` — historical models pin the schema at that migration; direct imports break when the model later changes. Custom `save()`/methods are **not** on historical models.
- DON'T change a custom field's positional-arg count once it's in a migration — old migrations call the old signature → `TypeError`. DON'T let migration files leave version control.

## Raw SQL — parameterize, always

DO
- `Model.objects.raw("SELECT ... WHERE last_name = %s", [lname])` — returns a `RawQuerySet`; PK column **must** be selected.
- Low-level: `with connection.cursor() as c: c.execute("... WHERE id = %s", [uid])`.
- Placeholders: `%s` for a list, `%(key)s` for a dict — **regardless of backend** (SQLite: list only). Double literal `%` → `%%` when params are passed.
- Prefer ORM expressions (`Func`, `RawSQL(sql, params)`) over full raw queries when embedding a fragment into an ORM query.

DON'T
- **DON'T** string-format or f-string user input into SQL, and **DON'T** quote the placeholder (`'%s'`) — both reopen SQL injection. Pass values via `params` and leave `%s` bare; the driver escapes them.

```python
Person.objects.raw("SELECT * FROM app_person WHERE last = %s", [name])   # DO
Person.objects.raw(f"SELECT * FROM app_person WHERE last = '{name}'")     # DON'T (injection)
```

## Async ORM (Django 4.1+ / matured in 5.x)

DO
- Use `a`-prefixed variants for blocking ops: `aget()`, `acreate()`, `asave()`, `adelete()`, `afirst()`, `aget_or_create()`, `abulk_create()`. Iterate with `async for`, and `await` the coroutine.
  `user = await User.objects.filter(username=n).afirst()`

DON'T
- DON'T forget `await` (symptom: `<coroutine ...>` where a model should be). Query-returning methods (`filter`, `exclude`) stay sync — no `afilter`. No `list(qs)` on async — use an `async for` comprehension. No transactions in async paths yet.

## Sources
- https://docs.djangoproject.com/en/stable/topics/db/queries/
- https://docs.djangoproject.com/en/stable/topics/db/optimization/
- https://docs.djangoproject.com/en/stable/topics/db/transactions/
- https://docs.djangoproject.com/en/stable/topics/migrations/
- https://docs.djangoproject.com/en/stable/topics/db/sql/
- https://docs.djangoproject.com/en/stable/ref/models/querysets/
- https://docs.djangoproject.com/en/stable/ref/models/expressions/
