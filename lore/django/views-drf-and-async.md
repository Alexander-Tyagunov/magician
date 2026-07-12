# django — Views, DRF & async

Framework-specifics only; assume Python + ORM lore live elsewhere. Version facts verified against docs.djangoproject.com (5.1/5.2) and django-rest-framework.org (3.16, Mar 2025). Django 5.2 is the current LTS (Apr 2025, Python 3.10–3.14). DRF 3.16 supports Django 4.2–6.0, Python 3.9+.

## Views: FBV vs CBV

DO
- Default to function-based views (FBV) for simple, one-off endpoints; reach for class-based views (CBV) / generic views when reusing behavior (list/detail/CRUD) or composing mixins.
- Use `@require_http_methods(["GET", "POST"])` / `@require_POST` on FBVs to reject wrong verbs (405) instead of hand-checking `request.method`.
- Return `HttpResponse`/`JsonResponse`; raise `Http404` (or `get_object_or_404`) rather than returning ad-hoc 404s.
- Keep view logic thin: validate → delegate to service/ORM → serialize. Push queries into the ORM lore's patterns.

DON'T
- Don't put business logic in `urls.py` or templates.
- Don't mutate state in GET handlers.
- Don't forget `JsonResponse(data, safe=False)` when the top-level payload is a list.

## DRF: serializers, viewsets, routers

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

## DRF: permissions, pagination, throttling

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

## Async views + async ORM (Django 4.1+ / 5.x)

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

## ASGI & middleware

DO
- Deploy async apps via `asgi.py` behind Uvicorn/Daphne/Hypercorn (not `runserver` in prod).
- Write middleware to support both stacks; Django adapts mismatched middleware but logs `django.request` "Asynchronous handler adapted…" and pays a thread-hop cost.
- Order middleware correctly: `SecurityMiddleware` first, then `SessionMiddleware`, `CommonMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`.

DON'T
- Don't mix sync-only middleware into a fully-async stack without knowing the adaptation cost.

## CSRF

DO
- Keep `CsrfViewMiddleware` enabled for session-cookie-authenticated browser POST/PUT/PATCH/DELETE.
- Send the token via `{% csrf_token %}` (forms) or the `X-CSRFToken` header (JS) read from the `csrftoken` cookie.
- Set `CSRF_TRUSTED_ORIGINS` (scheme required, e.g. `https://app.example.com`) when serving cross-subdomain or behind a proxy.

DON'T
- Don't scatter `@csrf_exempt`. For token-authenticated APIs (DRF `TokenAuthentication`/JWT), CSRF doesn't apply — but `SessionAuthentication` DOES enforce it.

## Settings hygiene (prod)

DO
- `DEBUG = False` in prod — non-negotiable; `DEBUG=True` leaks stack traces, settings, and SQL.
- Set an explicit `ALLOWED_HOSTS`; load `SECRET_KEY` and all secrets from env (`os.environ`), never commit them.
- Enable HTTPS hardening: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_PROXY_SSL_HEADER` (if behind a proxy).
- Configure CORS deliberately with `django-cors-headers`: enumerate `CORS_ALLOWED_ORIGINS`. Run `manage.py check --deploy` before shipping.

DON'T
- Don't use `ALLOWED_HOSTS = ["*"]` or `CORS_ALLOW_ALL_ORIGINS = True` in prod.
- Don't hardcode `SECRET_KEY`; rotating it invalidates sessions/tokens — plan for it.
- Don't return raw exception detail to clients; log server-side.

## Sources
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
