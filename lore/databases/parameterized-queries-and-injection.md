# Databases — Parameterized queries & injection

A parameterized query compiles the SQL text (placeholders) once, then binds values as typed data
**never re-lexed as SQL** — quotes, `;`, comments stay inert. Separation, not escaping, is the
defense. Verified: PostgreSQL 18, MySQL 8.4 LTS, SQL Server 2022/2025, Oracle 23ai, SQLite 3.

## Placeholders (positional unless noted)
- **PostgreSQL:** `$1,$2` numbered.
- **MySQL/MariaDB:** `?` only — no wire-level named params.
- **SQLite:** `?`,`?NNN`,`:name`,`@name`,`$name`; bare `?` *discouraged* (miscount risk), don't
  mix named/numbered.
- **SQL Server:** `sp_executesql` uses `@p`; ODBC/TDS expose `?`.
- **Oracle:** `:name`/`:1`, but `EXECUTE IMMEDIATE ... USING` binds **by position** — name
  cosmetic; a repeated name consumes one arg each.

## Server-side vs client-side
Bind server-side; values ship apart from the text. Many drivers **emulate** params client-side,
interpolating escaped strings. OWASP: *"These libraries often just build queries with string
concatenation ... Please ensure that query parameterization is done server-side!"* Emulation
reopens charset/escaping edges — prefer server-side prepares for untrusted input.

## Stacked queries
Prepared/extended paths run **one command only** (two statements = syntax error). Paths that *do*
stack into `; DROP TABLE ...`: Postgres **simple protocol**/`PQexec` and MySQL multi-statement
mode — off by default, toggled per driver (JDBC/Connector-J `allowMultiQueries=true`, C API
`CLIENT_MULTI_STATEMENTS`). Never route untrusted text through those.

## Identifiers can't be bound
`?`/`$1` bind **values only**; table/column names and `ASC`/`DESC` can't be params (OWASP). Map
input to a fixed code-side allowlist, reject the rest. Quote a dynamic identifier with the
engine's quoter — Postgres `format('%I',x)`/`quote_ident()`, SQL Server `QUOTENAME()` — never
hand-built quotes.

## Dynamic SQL in procedures
Procedures aren't auto-safe: Oracle `EXECUTE IMMEDIATE ... USING` and SQL Server `sp_executesql`
bind, but `EXEC(@sql)` and Oracle string-built SQL don't. Beware **second-order injection** — a
value safely bound on insert, later concatenated into dynamic SQL, stays exploitable; bind again
at the second use.

## Gotchas (any driver)
- **LIKE:** binding stops injection, but `%`/`_` in the value stay wildcards — escape them,
  declare `ESCAPE '\'`.
- **NULL:** `col = $1` never matches NULL — use `IS NOT DISTINCT FROM`. Oracle `USING` rejects
  literal `NULL`; pass a typed variable.
- **Plan-cache cliffs:** Postgres `plan_cache_mode=auto` runs 5 custom plans then may lock a
  **generic** plan (bad for skewed data) — pin `force_custom_plan`; same class as Oracle bind
  peeking / SQL Server parameter sniffing.
- **IN-lists:** one placeholder ≠ a list — emit one marker per element or bind an array
  (`WHERE id = ANY($1)` on Postgres); one stable plan, dodges `max_prepared_stmt_count`.
- **Least privilege:** never run the app as DBA/owner (OWASP).

## Sources
- PostgreSQL 18 — libpq `PQexecParams`: https://www.postgresql.org/docs/current/libpq-exec.html
- MySQL Connector/J — Security props: https://dev.mysql.com/doc/connector-j/en/connector-j-connp-props-security.html
- OWASP — SQL Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- OWASP — Query Parameterization: https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html
