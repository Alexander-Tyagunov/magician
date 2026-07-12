# peewee — Models, queries & pitfalls

Verified against Peewee **4.1.2** (released 2026-07-09) official docs. Peewee is a small **synchronous** ORM (SQLite/Postgres/MySQL/MariaDB). 4.0 removed all Python 2 code and added psycopg3 + *preliminary* asyncio via a playhouse extension; treat core Peewee as sync. Assume python + web-framework lore live elsewhere.

## Detect the version first

```bash
python -c "import peewee; print(peewee.__version__)"
```

- `>= 4.1.1` → use the `Load()` eager-loading API; `prefetch()` still works but is superseded.
- `< 4.1.1` (incl. all 3.x) → use `prefetch()`; `Load`/`with_related` unavailable.
- `4.0.x` → psycopg2 preferred when both present; pass `prefer_psycopg3=True` to force psycopg3.

## Model + database binding

DO — bind via inner `Meta.database`; share a `BaseModel`:

```python
from peewee import *
db = PostgresqlDatabase('app', user='postgres', host='localhost', autoconnect=False)

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    username = CharField(unique=True)

class Tweet(BaseModel):
    user = ForeignKeyField(User, backref='tweets')  # creates User.tweets back-ref
    content = TextField()
    is_published = BooleanField(default=True)
```

- DO set `autoconnect=False` and manage connections explicitly — errors surface at connect time, not mid-query.
- DO defer config when the DSN isn't known at import: `db = DatabaseProxy()` then `db.initialize(real_db)`, or `PostgresqlDatabase(None)` then `db.init('name', ...)`.
- DON'T reference `user.user_id` blindly — the FK descriptor is `tweet.user` (lazy SELECT) vs `tweet.user_id` (raw int, no query). Set `lazy_load=False` on the FK to make attribute access return the id instead of querying.

## Querying

Queries are **lazy** — no SQL runs until you iterate, index, slice, or call a materializing method.

DO:

```python
u = User.get(User.username == 'charlie')          # raises DoesNotExist if absent
u = User.get_or_none(User.username == 'charlie')  # returns None instead
u = User.get_by_id(pk)                             # or User[pk]
q = Tweet.select().where(Tweet.is_published == True).order_by(Tweet.id.desc())
first = q.first()                                  # None-safe first row
n = q.count()
```

- DON'T use Python `and`/`or`/`in`/`not` in `where()` — they coerce to bool. Use bitwise `&`, `|`, `~` (parenthesize each term) and `.in_([...])` / `.not_in([...])`:

```python
q = Tweet.select().where((Tweet.is_published == True) & (Tweet.user.in_([1, 2])))
```

- DO chain: multiple `.where()` calls are ANDed. Call `fn.COUNT`, `fn.LOWER`, etc. via `fn`.
- DO use row-type shortcuts for read-heavy paths: `.dicts()`, `.tuples()`, `.namedtuples()`, and `.iterator()` (disables the result cache → flat memory on big sets).

## Writing

```python
u = User.create(username='huey')                      # INSERT + return instance
u, created = User.get_or_create(username='huey', defaults={'x': 1})  # (instance, bool)
User.insert_many(rows, fields=[User.username]).execute()   # bulk INSERT (dicts/tuples)
User.bulk_create(list_of_unsaved, batch_size=100)          # wrap in a transaction
Tweet.update(is_published=False).where(Tweet.user == u).execute()
Tweet.delete().where(Tweet.id == 5).execute()
```

- DON'T rely on `get_or_create` under a unique constraint — there's a lookup→insert race. Prefer create-first inside `atomic()`, catch `IntegrityError`, fall back to `get()`.

## N+1 — eager load

DON'T iterate and touch a relation per row (that's N+1). Two fixes by direction:

DO (many → one, e.g. tweet → author) — **join + select both models**; the FK is fully populated with no extra query:

```python
for t in Tweet.select(Tweet, User).join(User):
    print(t.user.username, t.content)   # no extra query
```

DO (one → many, e.g. user → tweets) — **eager load** (one query per table, joined in Python):

```python
# Peewee >= 4.1.1
from peewee import Load
for u in User.select().with_related(Load(User.tweets)):
    for t in u.tweets:  # a list, no extra query
        ...
# nest: Load(User.tweets).then(Load(Tweet.favorites)); limit: Load(User.tweets, per_parent=2)

# Peewee < 4.1.1 (or 3.x) — prefetch()
from peewee import prefetch
users = prefetch(User.select(), Tweet.select())
```

- `prefetch()` disambiguates a subquery relating to multiple parents with a `(query, target_model)` tuple.

## Transactions

DO — wrap multi-statement writes in `db.atomic()` (context manager or decorator). Nested `atomic()` blocks become **savepoints** automatically; unhandled exceptions roll back:

```python
with db.atomic():
    u = User.create(username='charlie')
    with db.atomic() as sp:      # savepoint
        Tweet.create(user=u, content='x')
        sp.rollback()            # rolls back inner only
```

- DON'T nest `db.transaction()` — it's flat; only the outermost is active, nesting is unpredictable. Use `atomic()`.

## Connections

DO manage lifetime explicitly (`autoconnect=False`); connections are **not** thread-safe to share:

```python
with db.connection_context():   # opens/closes connection, NO implicit transaction
    User.select()
```

- `with db:` opens a connection **and** a transaction (commit/rollback + close). `db.connect(reuse_if_open=True)` avoids "already open" `OperationalError`; `db.close()` is idempotent (returns False if already closed).
- DO pool for concurrent/web workloads: `from playhouse.pool import PooledPostgresqlDatabase(..., max_connections=20, stale_timeout=300)`. `connect()`/`close()` then acquire/release from the pool — still call both (per request).

## Security — parameterize raw SQL

Core query builder binds parameters automatically. The escape hatches do **not** sanitize — they only forward what you give them.

DON'T interpolate user input into SQL strings:

```python
# INJECTION — never do this
User.raw('SELECT * FROM users WHERE name = "%s"' % name)
db.execute_sql(f'SELECT * FROM users WHERE id = {uid}')
```

DO pass values as bound params (placeholder is driver-specific, `%s` for psycopg/MySQL, `?` for SQLite — `db.param`):

```python
User.raw('SELECT * FROM users WHERE username = %s', username)      # params after SQL
db.execute_sql('SELECT * FROM users WHERE status = %s', (ACTIVE,)) # params tuple
```

- `SQL('...')` is a **literal fragment** (used for aliases/ordering, e.g. `.order_by(SQL('num').desc())`). It accepts `SQL(sql, *params)` — never build its string from user input; pass values as params.
- DON'T concatenate identifiers/table names from user input either; whitelist them.

## Sources

- https://docs.peewee-orm.com/en/latest/peewee/querying.html
- https://docs.peewee-orm.com/en/latest/peewee/relationships.html
- https://docs.peewee-orm.com/en/latest/peewee/database.html
- https://docs.peewee-orm.com/en/latest/peewee/transactions.html
- https://docs.peewee-orm.com/en/latest/peewee/api.html
- https://github.com/coleifer/peewee/blob/master/CHANGELOG.md
- https://pypi.org/project/peewee/
