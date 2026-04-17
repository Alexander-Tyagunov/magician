Common AI mistakes: N+1 queries without `select_related`/`prefetch_related`; using `filter` when `get` is intended (raises MultipleObjectsReturned); not using Django's built-in auth; raw SQL without parameterization.
Commands: migrate: `python manage.py migrate`, test: `python manage.py test`, shell: `python manage.py shell`.
Gotchas: `get_object_or_404` is cleaner than manual try/except; `Q` objects for complex queries; always use `objects.filter()` not `objects.all()` for filtering.
