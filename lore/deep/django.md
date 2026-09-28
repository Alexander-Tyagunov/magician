# django — deep dive

> On-demand companion to `lore/django.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [ORM & migrations](#orm-and-migrations) · [Views, DRF & async](#views-drf-and-async)

## ORM & migrations <a id="orm-and-migrations"></a>

Deep-dive. Assumes Python + `lore/django.md` base lore. Verify version facts against docs.djangoproject.com. Confirmed against current stable docs (Django 5.2 LTS / 6.0). Async ORM matured 4.1→5.x; state your target.

### Models & QuerySets (lazy)

DO
- Treat QuerySets as **lazy** — chaining `.filter().exclude()` fires **zero** queries. DB is hit only on evaluation: iteration, `list()`, `bool()`, `len()`, `in`, pickling, shell `repr()`.
- Reuse one evaluated QuerySet's **result cache**: assign `qs = Model.objects.all()` once, then iterate/`len()`/`in` against `qs` — no re-query.
- `get()` for exactly one row (raises `DoesNotExist` / `MultipleObjectsReturned`); `filter()` for zero-or-more; `get_object_or_404()` in views.

DON'T
- DON'T re-index expecting cache — `qs[5]` then `qs[5]` hits the DB **twice** (slicing/indexing doesn't populate the cache unless the whole set is already evaluated).
- DON'T call `exists()`/`count()`/`contains(obj)` when you'll *also* consume the rows — extra queries on top of evaluation; use `if qs:` / `len(qs)` / `obj in qs`. Inverse: if you *only* need the bool/count, DO use them (cheaper than pulling rows).

### Kill N+1 — the cardinal sin

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

### Trim columns — `.only()` / `.defer()`

DO
- `.only("title", "pk")` to load *only* those columns; `.defer("body")` to load all *but* those. Best for wide text/blob columns you rarely touch. Profile first.

DON'T
- DON'T `.only()`/`.defer()` then access a deferred field in a loop — each access fires a **separate** query (a pessimization). PK is always fetched.

### `F()` and `Q()` expressions

DO
- **`F("field")`** references a column in-DB — atomic updates without read-modify-write races, and field-to-field compares:
  `Product.objects.filter(pk=1).update(views=F("views") + 1)` (no race).
  `Entry.objects.filter(comments__gt=F("pingbacks") * 2)`.
- **`Q(...)`** for OR / complex boolean logic: combine with `&`, `|`, `^` (XOR), negate with `~`.
  `Model.objects.filter(Q(a=1) | Q(b=2))`.

DON'T
- DON'T place a keyword arg **before** a `Q` object in a call — `Q` args must come first, else `SyntaxError`/`TypeError`.
- DON'T span joins in `F()` inside `.update()` — raises `FieldError` (update refs must be local fields). Note `F()` values are stale on the Python instance after save; `refresh_from_db()`.

### Transactions — `transaction.atomic`

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

### Bulk operations

DO
- `Model.objects.bulk_create([...])` / `bulk_update(objs, ["field"])` collapse N INSERTs/UPDATEs into few queries. Tune `batch_size=`; `ignore_conflicts=True` / `update_conflicts=` for upserts.

DON'T
- DON'T expect `save()`/`pre_save`/`post_save` signals to fire (nor PKs populated on some backends) — read the caveats. Loop-`save()` for a handful of rows is fine; bulk is for volume.

### Migrations

DO
- `makemigrations [app]` to author from model changes; `migrate` to apply. Read `makemigrations` output — "it's not perfect." Inspect with `sqlmigrate app 0003` (SQL) and `showmigrations` (status).
- Data migrations: `makemigrations --empty app`, then `migrations.RunPython(forward, backward)`. Inside, use **historical models** via `apps.get_model("app", "Model")` — never import the live model.
- Give `RunPython`/`RunSQL` a reverse callable or `migrate app 0002` (reverse) raises `IrreversibleError`. Cross-app `RunPython`: list every involved app's latest migration in `dependencies`.
- DDL-transactional DBs (PostgreSQL, SQLite) wrap each migration in one transaction by default; set `atomic = False` on the `Migration` for long/batched data ops (MySQL/Oracle lack DDL transactions). Squash sprawl with `squashmigrations app 0004`.

DON'T
- **DON'T edit a migration already applied anywhere** (shared/CI/prod). Migrations are an append-only ledger — editing an applied one desyncs recorded state from schema. Add a **new** migration. Editing is fine only for still-unapplied local files.
- DON'T import live models in `RunPython` — historical models pin the schema at that migration; direct imports break when the model later changes. Custom `save()`/methods are **not** on historical models.
- DON'T change a custom field's positional-arg count once it's in a migration — old migrations call the old signature → `TypeError`. DON'T let migration files leave version control.

### Raw SQL — parameterize, always

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

### Async ORM (Django 4.1+ / matured in 5.x)

DO
- Use `a`-prefixed variants for blocking ops: `aget()`, `acreate()`, `asave()`, `adelete()`, `afirst()`, `aget_or_create()`, `abulk_create()`. Iterate with `async for`, and `await` the coroutine.
  `user = await User.objects.filter(username=n).afirst()`

DON'T
- DON'T forget `await` (symptom: `<coroutine ...>` where a model should be). Query-returning methods (`filter`, `exclude`) stay sync — no `afilter`. No `list(qs)` on async — use an `async for` comprehension. No transactions in async paths yet.

### Sources
- https://docs.djangoproject.com/en/stable/topics/db/queries/
- https://docs.djangoproject.com/en/stable/topics/db/optimization/
- https://docs.djangoproject.com/en/stable/topics/db/transactions/
- https://docs.djangoproject.com/en/stable/topics/migrations/
- https://docs.djangoproject.com/en/stable/topics/db/sql/
- https://docs.djangoproject.com/en/stable/ref/models/querysets/
- https://docs.djangoproject.com/en/stable/ref/models/expressions/

## Views, DRF & async <a id="views-drf-and-async"></a>

Framework-specifics only; assume Python + ORM lore live elsewhere. Version facts verified against docs.djangoproject.com (5.1/5.2) and django-rest-framework.org (3.16, Mar 2025). Django 5.2 is the current LTS (Apr 2025, Python 3.10–3.14). DRF 3.16 supports Django 4.2–6.0, Python 3.9+.

### Views: FBV vs CBV

DO
- Default to function-based views (FBV) for simple, one-off endpoints; reach for class-based views (CBV) / generic views when reusing behavior (list/detail/CRUD) or composing mixins.
- Use `@require_http_methods(["GET", "POST"])` / `@require_POST` on FBVs to reject wrong verbs (405) instead of hand-checking `request.method`.
- Return `HttpResponse`/`JsonResponse`; raise `Http404` (or `get_object_or_404`) rather than returning ad-hoc 404s.
- Keep view logic thin: validate → delegate to service/ORM → serialize. Push queries into the ORM lore's patterns.

DON'T
- Don't put business logic in `urls.py` or templates.
- Don't mutate state in GET handlers.
- Don't forget `JsonResponse(data, safe=False)` when the top-level payload is a list.

### DRF: serializers, viewsets, routers

DO
- Use `ModelSerializer` with an explicit `fields = [...]` allowlist. Never `fields = "__all__"` on models with sensitive columns.
- Validate in the serializer: `validate_<field>()` for one field, `validate()` for cross-field. Trust only `serializer.validated_data`, never `request.data`.
- Use `ModelViewSet` + `DefaultRouter` for standard CRUD; `ReadOnlyModelViewSet` when writes aren't allowed. Override `get_queryset()`/`get_serializer_class()` for per-action behavior.
- Set `read_only`/`write_only` deliberately; mark server-owned fields (`owner`, timestamps) read-only and set them in `perform_create(self, serializer)`.
- Add `@action(detail=True, methods=["post"])` for non-CRUD routes so the router wires URLs.

DON'T
- Don't expose password/token/hash fields; don't accept `is_staff`/`owner` from the client.
- Don't do N+1 in list endpoints — set `queryset` with `select_related`/`prefetch_related`.
- Don't skip pagination on collection endpoints.

```python
class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["id", "title", "status", "owner"]
        read_only_fields = ["owner"]

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    def get_queryset(self):
        return Ticket.objects.filter(owner=self.request.user)
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
```

### DRF: permissions, pagination, throttling

DO
- Set project defaults in `settings.REST_FRAMEWORK`; override per-view with `permission_classes` / `throttle_classes`.
- Default to `IsAuthenticated` globally; loosen per-view, not the reverse. Use `IsAuthenticatedOrReadOnly` for public reads.
- Enforce object-level ownership with a custom `has_object_permission`; `get_object()` runs the check for you.
- Set `DEFAULT_PAGINATION_CLASS` + `PAGE_SIZE`; use `CursorPagination` for large/append-heavy tables (stable, no deep-offset scans).
- Throttle with `AnonRateThrottle`/`UserRateThrottle` + `DEFAULT_THROTTLE_RATES`; add `ScopedRateThrottle` for expensive endpoints.

DON'T
- Don't rely on `has_permission` alone for row ownership — it can't see the object.
- Don't ship `AllowAny` defaults to prod.

```python
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": "1000/day", "anon": "100/day"},
}
```

Note: DRF 3.16 has **no native async view support** — its views/permissions/throttles run sync. For async, use plain Django async views (below) or `sync_to_async`.

### Async views + async ORM (Django 4.1+ / 5.x)

Async views landed in Django 3.1; async ORM query methods (`a`-prefixed variants, `async for`) in Django 4.1.

DO
- Write `async def` views (FBV) or `async def get/post` handlers (CBV). Serve under ASGI to get the real benefit.
- Use `a`-prefixed ORM methods that hit the DB: `aget`, `acreate`, `asave`, `adelete`, `afirst`, `acount`, `aget_or_create`, `aset`; iterate with `async for`.
- Use `sync_to_async(fn, thread_sensitive=True)` to call sync-only code (incl. transactions) from async; `async_to_sync` for the reverse.
- Disable persistent DB connections (`CONN_MAX_AGE`) under async; use a real connection pool instead.
- Await async-native I/O (httpx, aioredis) concurrently with `asyncio.gather`.

DON'T
- Don't call the sync ORM inside an async view — raises `SynchronousOnlyOperation`. Don't reach for `DJANGO_ALLOW_ASYNC_UNSAFE` to silence it (data-corruption risk).
- Don't wrap the ORM in a transaction inside async code — transactions aren't async-safe yet; move them into a `sync_to_async` sync function.
- Don't block the event loop with sync HTTP/sleep/CPU work.

```python
async def dashboard(request):
    tickets = [t async for t in Ticket.objects.filter(owner=request.user)]
    latest = await Ticket.objects.filter(owner=request.user).afirst()
    return JsonResponse({"count": len(tickets), "latest": latest and latest.id})
```

Django 5.1 added async session/auth helpers (`aget`, `login_required` wrapping async views); Django 5.2 added async auth methods (`aauthenticate`, `acreate_user`, `ahas_perm`).

### ASGI & middleware

DO
- Deploy async apps via `asgi.py` behind Uvicorn/Daphne/Hypercorn (not `runserver` in prod).
- Write middleware to support both stacks; Django adapts mismatched middleware but logs `django.request` "Asynchronous handler adapted…" and pays a thread-hop cost.
- Order middleware correctly: `SecurityMiddleware` first, then `SessionMiddleware`, `CommonMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`.

DON'T
- Don't mix sync-only middleware into a fully-async stack without knowing the adaptation cost.

### CSRF

DO
- Keep `CsrfViewMiddleware` enabled for session-cookie-authenticated browser POST/PUT/PATCH/DELETE.
- Send the token via `{% csrf_token %}` (forms) or the `X-CSRFToken` header (JS) read from the `csrftoken` cookie.
- Set `CSRF_TRUSTED_ORIGINS` (scheme required, e.g. `https://app.example.com`) when serving cross-subdomain or behind a proxy.

DON'T
- Don't scatter `@csrf_exempt`. For token-authenticated APIs (DRF `TokenAuthentication`/JWT), CSRF doesn't apply — but `SessionAuthentication` DOES enforce it.

### Settings hygiene (prod)

DO
- `DEBUG = False` in prod — non-negotiable; `DEBUG=True` leaks stack traces, settings, and SQL.
- Set an explicit `ALLOWED_HOSTS`; load `SECRET_KEY` and all secrets from env (`os.environ`), never commit them.
- Enable HTTPS hardening: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_PROXY_SSL_HEADER` (if behind a proxy).
- Configure CORS deliberately with `django-cors-headers`: enumerate `CORS_ALLOWED_ORIGINS`. Run `manage.py check --deploy` before shipping.

DON'T
- Don't use `ALLOWED_HOSTS = ["*"]` or `CORS_ALLOW_ALL_ORIGINS = True` in prod.
- Don't hardcode `SECRET_KEY`; rotating it invalidates sessions/tokens — plan for it.
- Don't return raw exception detail to clients; log server-side.

### Sources
- https://docs.djangoproject.com/en/stable/topics/async/
- https://docs.djangoproject.com/en/5.2/releases/5.2/
- https://docs.djangoproject.com/en/5.1/releases/5.1/
- https://docs.djangoproject.com/en/stable/ref/csrf/
- https://docs.djangoproject.com/en/stable/topics/http/middleware/
- https://docs.djangoproject.com/en/stable/howto/deployment/checklist/
- https://www.django-rest-framework.org/
- https://www.django-rest-framework.org/community/3.16-announcement/
- https://www.django-rest-framework.org/api-guide/viewsets/
- https://www.django-rest-framework.org/api-guide/permissions/
- https://www.django-rest-framework.org/api-guide/pagination/
- https://www.django-rest-framework.org/api-guide/throttling/
