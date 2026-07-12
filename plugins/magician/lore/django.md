# Django — core

Versions: 6.0 latest stable; **5.2 LTS** (use for prod), 4.2 prior LTS. Verify `django.__version__`.

DO
- Run `manage.py check --deploy` before shipping; set `DEBUG=False`, real `ALLOWED_HOSTS`, secret `SECRET_KEY` (env, never in code/VCS).
- Prod HTTPS: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`.
- Validate input via Forms/DRF serializers before touching the ORM. Enforce authz per-view (`LoginRequired`/permissions), not just auth.
- Async views since 3.1, async ORM (`aget`/`acreate`/`async for`) since 4.1 — use for I/O-bound; keep sync ORM in sync views.
- CORS: install `django-cors-headers`, set explicit `CORS_ALLOWED_ORIGINS`.

DON'T
- Don't `mark_safe`/`|safe`/`autoescape off` on untrusted data (XSS). Templates auto-escape by default.
- Don't build SQL with f-strings/`.extra()`/`RawSQL`; ORM params are escaped — see ORM lore.
- Don't `@csrf_exempt` a state-changing view. Don't call sync ORM inside async without `sync_to_async`.
- Don't ship unrun migrations; don't commit `SECRET_KEY`/`.env`.

Commands: `manage.py runserver|migrate|makemigrations|createsuperuser|check --deploy|test`; `django-admin startproject`.

Deep dive when writing non-trivial django — read lore/django/{orm-and-migrations,views-drf-and-async}.md

## Sources
docs.djangoproject.com/en/stable/{releases,topics/security,topics/async}; django-rest-framework.org
