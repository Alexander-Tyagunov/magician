# Flask — core

Version cue: Flask 3.1.x (stable, Py 3.9+). 3.0 dropped 2.x-era deprecated APIs; async views (`async def`) need `flask[async]` (2.0+). `TRUSTED_HOSTS`/`MAX_FORM_MEMORY_SIZE`/`MAX_FORM_PARTS` are 3.1+. Prefer 3.x.

DO use the app-factory `def create_app()` + `Blueprint` for anything non-trivial; wire extensions via `ext.init_app(app)`, not at import.
DO return `jsonify(...)` / a dict (auto-JSON) / `(body, status, headers)` tuples; never hand-build JSON strings.
DO read input via `request.args/form/json` in a request; use `g` (request-scoped) and `current_app` (needs app context) — never module globals for per-request state.
DO set a strong `SECRET_KEY` from env (not a literal) — required to sign `session`/flash.
DO validate/sanitize all input; parameterize DB queries (never string-concat SQL).
SECURITY: `SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE='Lax'`; set `TRUSTED_HOSTS` (block Host spoofing) + `MAX_CONTENT_LENGTH` (uploads); add CSP/HSTS/`X-Frame-Options` headers. Flask has NO CSRF — use Flask-WTF `CSRFProtect`.

DON'T trust Jinja autoescape alone: quote HTML attributes, never `Markup`/`|safe` on user input, block `javascript:` hrefs.
DON'T run DEBUG in prod (debugger = RCE) or serve via `app.run()` — use gunicorn/uwsgi. `db.session.commit()` is explicit.

Commands: `flask --app app run --debug` (dev) · `flask routes` · `flask shell` · `pytest` w/ `app.test_client()`

Deep dive when writing non-trivial flask — read lore/flask/{patterns-and-extensions}.md

## Sources
flask.palletsprojects.com/en/stable/{,web-security/,patterns/,config/,cli/}
