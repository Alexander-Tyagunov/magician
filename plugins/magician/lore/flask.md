Common AI mistakes: using global state without application context; not using blueprints for large apps; returning raw strings instead of `jsonify`; forgetting to set `SECRET_KEY` for sessions.
Commands: dev: `flask run`, test: `pytest`.
Gotchas: `g` object is request-scoped; `current_app` proxy requires app context; Flask-SQLAlchemy `db.session.commit()` must be explicit.
