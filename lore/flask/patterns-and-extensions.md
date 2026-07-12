# flask — Patterns & extensions

Scope: Flask 3.x (current stable **3.1.x**, latest 3.1.3, 2026‑02‑18). Requires **Python 3.9+**. Flask is a **WSGI** framework: sync, one worker handles one request/response cycle. Assumes separate Python-foundation lore; this file is Flask-specific.

Version facts:
- **Flask 3.0.0** (2023‑09‑30) removed all previously-deprecated code, deprecated `flask.__version__` (use `importlib.metadata.version("flask")`), requires **Werkzeug >= 3.0**.
- Removed pre-3.0: `JSON_AS_ASCII`/`JSON_SORT_KEYS`/`JSONIFY_*` config (use `app.json` provider attrs), the `ENV` key + `FLASK_ENV` (use `--debug`), `PRESERVE_CONTEXT_ON_EXCEPTION`.
- **3.1** added `SECRET_KEY_FALLBACKS` (key rotation), `TRUSTED_HOSTS`, `MAX_FORM_MEMORY_SIZE`, `MAX_FORM_PARTS`, `SESSION_COOKIE_PARTITIONED`.

## App factory + blueprints

DO
- Build the app in a `create_app()` factory so config is injectable (tests, multiple instances). `flask --app module run` auto-detects a factory named `create_app` or `make_app`.
```python
# app/__init__.py
from flask import Flask
from .extensions import db, migrate, login
from .blog import bp as blog_bp

def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object("app.config.Default")
    app.config.from_prefixed_env()          # FLASK_* env overrides
    if config:                               # dict/obj for tests
        app.config.from_mapping(config)
    db.init_app(app)                         # bind extensions here
    migrate.init_app(app, db)
    login.init_app(app)
    app.register_blueprint(blog_bp, url_prefix="/blog")
    return app
```
- Split features into `Blueprint`s; register with `url_prefix`. Endpoints are namespaced `blueprint.view`; link with `url_for("blog.index")` or relative `url_for(".index")` from within the same blueprint.
- Nest blueprints via `parent.register_blueprint(child)` → endpoint `parent.child.view`, URL prefixes compose.

DON'T
- DON'T create the app or bind extensions at import time / module top-level — breaks the factory and multi-instance/testing.
- DON'T rely on blueprint 404/405 handlers for bad URLs — routing errors happen before a blueprint is chosen; register 404/405 at the **app** level and branch on `request.path`.

## Extensions (init_app pattern)

DO
- Instantiate extension objects **unbound** at module scope, bind them inside the factory with `init_app(app)`. No app-specific state lives on the extension, so one object serves many apps.
```python
# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_migrate import Migrate
from flask_login import LoginManager

class Base(DeclarativeBase): pass
db = SQLAlchemy(model_class=Base)   # Flask-SQLAlchemy 3.x + SQLAlchemy 2.x
migrate = Migrate()
login = LoginManager()
```
- Flask-SQLAlchemy 3.x: pass a `DeclarativeBase`/`DeclarativeBaseNoMeta` subclass via `model_class=`; set `SQLALCHEMY_DATABASE_URI`; `db.init_app(app)`. (Defer ORM/query specifics to SQLAlchemy lore.)
- Flask-Migrate: `migrate.init_app(app, db)`; run `flask db init/migrate/upgrade` (Alembic).
- Flask-Login: `login.init_app(app)`, set `login.login_view`, provide `@login.user_loader`, guard views with `@login_required`, read `current_user`.
- Flask-WTF: `FlaskForm` + `form.validate_on_submit()`; enable CSRF (`CSRFProtect(app)` or per-form) — CSRF token needs `SECRET_KEY`.

DON'T
- DON'T do `SQLAlchemy(app)` in the factory (binds state to one app). DON'T call `init_app` before config is loaded — extensions read config at init.
- DON'T assume old extension decorators work on `async def` views (see async).

## Application & request context

DO
- Use `current_app` and `g` instead of importing the app object (avoids circular imports; there's no global app under the factory). Flask auto-pushes an app context + request context per request, and an app context for `@app.cli.command()`.
- Store per-request/per-context resources on `g` with lazy get + teardown:
```python
from flask import g
def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db
@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()
```
- Outside a request (scripts, init, some tests) push manually: `with app.app_context(): ...` (fixes `RuntimeError: Working outside of application context`). Use `with app.test_request_context(): ...` for request-scoped code.

DON'T
- DON'T store per-request data on module globals or on the extension/app object — it leaks across requests and isn't thread/worker safe. `g` is per-context and cleared at context teardown; it is **not** cross-request storage — use `session` or a DB for that.
- DON'T keep `current_app`/`request`/`g` references after the context pops (e.g. in spawned threads).

## Config (env / object / files)

DO
- Layer config: base object → env overrides → per-deploy secrets. Only UPPERCASE names are stored.
  - `app.config.from_object("app.config.Prod")` (class or import path; not instantiated — instantiate first if you need `@property`).
  - `app.config.from_prefixed_env()` — loads `FLASK_*` env vars, JSON-parsed (nested via `__`).
  - `app.config.from_pyfile("app.cfg", silent=True)` / `from_envvar("APP_SETTINGS")`.
  - `app.config.from_file("config.toml", load=tomllib.load, text=False)` / JSON via `json.load`.
- Generate `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex())"`; load it from env/secret store. Rotate with `SECRET_KEY_FALLBACKS` (3.1).
- Prod session cookie hardening: `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True` (default), `SESSION_COOKIE_SAMESITE="Lax"`. Cap uploads with `MAX_CONTENT_LENGTH`. Set `TRUSTED_HOSTS` (3.1) to reject Host-header spoofing.

DON'T
- **DON'T ship `debug=True`** or `FLASK_DEBUG=1` in production — the interactive debugger executes arbitrary code (RCE) and leaks stack traces. Set debug only via `flask run --debug` in dev; setting `DEBUG` in code is unreliable (read too late).
- DON'T commit `SECRET_KEY`/DSNs/DB URLs. DON'T put secrets or PII in URLs. DON'T read config at import time — read it inside views/`init_app` so it stays reconfigurable.

## Error handlers

DO
- Register with `@app.errorhandler(code_or_exc)` or `app.register_error_handler(...)`; set the status code yourself in the return (the handler's code is not applied automatically).
- For JSON APIs, convert HTTP errors and raise a custom exception:
```python
from werkzeug.exceptions import HTTPException
from flask import jsonify

@app.errorhandler(HTTPException)
def json_http_error(e):
    return jsonify(code=e.code, name=e.name, description=e.description), e.code

class ApiError(Exception):
    def __init__(self, message, status=400): self.message, self.status = message, status
@app.errorhandler(ApiError)
def handle_api_error(e):
    return jsonify(error=e.message), e.status
```
- Use `abort(404, description=...)` for control-flow HTTP errors. Handlers respect the class hierarchy (most specific wins); blueprint handlers take precedence for that blueprint.
- Unhandled exceptions → 500; a registered `InternalServerError`/500 handler receives an `InternalServerError` with the cause at `e.original_exception`.

DON'T
- DON'T register a broad `Exception`/`HTTPException` handler without re-passing HTTP errors — you'll swallow 404/405 and lose status/headers. Pass through: `if isinstance(e, HTTPException): return e`.
- DON'T leak tracebacks in prod responses (keep `DEBUG=False`, `TESTING=False`); ship errors to Sentry (`sentry-sdk[flask]`) instead.

## Async views (sync framework)

DO
- Install the extra for `async def` views/handlers: `pip install "flask[async]"` (Flask 2.0+, asyncio only). Flask runs the coroutine in an event loop on the worker thread.
- Use async only for concurrent IO **within** one request (e.g. `asyncio.gather` of API/DB calls).

DON'T
- DON'T expect more throughput: each request still ties up one worker; async is **not** faster for CPU-bound work and doesn't raise concurrency.
- DON'T spawn background tasks with `asyncio.create_task` in a view — they're cancelled when the view returns. Use a task queue (Celery/RQ) or run under an ASGI server via `asgiref.WsgiToAsgi`.
- If the codebase is mostly async or needs websockets/long-lived connections, prefer **Quart** (ASGI reimplementation of the Flask API) rather than forcing async into WSGI Flask.

## Security quick-checks
- Jinja autoescaping is on for `.html`/`.xml` — DON'T disable it or mark untrusted data `| safe`.
- Parameterize DB access via the ORM (defer to ORM lore); never string-format SQL.
- CSRF-protect state-changing forms (Flask-WTF); requires `SECRET_KEY`.
- Configure CORS deliberately (e.g. Flask-Cors) — don't blanket `*` with credentials.
- Enforce authn/authz per view (`@login_required` + role checks), not just by hiding links.

## Sources
- https://flask.palletsprojects.com/en/stable/
- https://flask.palletsprojects.com/en/stable/installation/
- https://flask.palletsprojects.com/en/stable/patterns/appfactories/
- https://flask.palletsprojects.com/en/stable/blueprints/
- https://flask.palletsprojects.com/en/stable/appcontext/
- https://flask.palletsprojects.com/en/stable/config/
- https://flask.palletsprojects.com/en/stable/errorhandling/
- https://flask.palletsprojects.com/en/stable/async-await/
- https://flask.palletsprojects.com/en/stable/extensions/
- https://flask.palletsprojects.com/en/stable/changes/
- https://flask-sqlalchemy.palletsprojects.com/en/stable/quickstart/
