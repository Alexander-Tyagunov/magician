# Oracle Database — PL/SQL & Types

Current: **26ai** GA (successor to the **23ai** LTS); **19c** is still the widely-deployed long-term release, **21c** the innovation release. Feature gates noted inline — never claim a type/feature before its release.

## Type traps that bite through every driver
- **Empty string is NULL.** Oracle "treats a character value with a length of zero as null" — `'' = NULL`, and any driver that sends `''` for an empty field stores NULL. Comparisons with NULL yield UNKNOWN, so test only with `IS [NOT] NULL`. Arithmetic with NULL → NULL, but `||` **ignores** NULL operands. Oracle now recommends *not* relying on `''`≡NULL (may change).
- **NUMBER is exact decimal** (p 1–38, s −84–127) — use it for money. `BINARY_FLOAT`/`BINARY_DOUBLE` are IEEE-754 (inexact, but support Inf/NaN); `FLOAT(p)` is a NUMBER subtype (binary precision), not a C float.
- **Use `VARCHAR2`, never `VARCHAR`** (reserved; Oracle may redefine it). `size` is required. Max **4000 bytes** default, **32767** only if `MAX_STRING_SIZE=EXTENDED` (irreversible; extended cols stored out-of-line as LOBs). Length is `BYTE` vs `CHAR` per `NLS_LENGTH_SEMANTICS` (SYS defaults BYTE) — a multibyte value can overflow a byte-sized column. `CHAR(n)` is blank-padded (padded-comparison semantics) — avoid.
- **`DATE` carries a time-of-day** (to the second, no fractional, no zone) — it is *not* a date-only type; midnight-only assumptions and `=` matches silently fail. `TIMESTAMP` adds fractional seconds; `WITH TIME ZONE` stores the offset; `WITH LOCAL TIME ZONE` normalizes to the DB zone on store and renders in the session zone. Datetime `+ n` adds **days**.
- **Selecting a LOB returns a locator**, not bytes — stream via `DBMS_LOB`; free temporary LOBs or leak PGA. `LONG`/`LONG RAW` deprecated since 8.1.6 → use `CLOB`/`BLOB`.

## SQL-visible types added recently
- **JSON** native binary type since **21c** (`compatible>=20`); before that store as `VARCHAR2`/`CLOB`/`BLOB` + `IS JSON` check. **BOOLEAN** as a SQL/column type and **VECTOR** (similarity search) are **23ai**. Before 23ai, `BOOLEAN` was **PL/SQL-only** — not a column type and not bindable from clients; 23ai lets PL/SQL BOOLEAN cross into SQL.

## PL/SQL ↔ SQL engine: context switches
Procedural code runs in the PL/SQL engine; each SQL statement is handed to the SQL engine — a **context switch**. A row-by-row cursor loop pays one switch *per row*.
- `SELECT ... BULK COLLECT INTO coll [LIMIT n]` fetches a set in one switch — **always `LIMIT`** (e.g. 100–1000) from an unbounded source, or a large table OOMs the PGA.
- `FORALL i IN .. ` batches set DML in one switch; add `SAVE EXCEPTIONS` and read `SQL%BULK_EXCEPTIONS` to survive per-row errors.
- Loop counters: `PLS_INTEGER`/`BINARY_INTEGER` (hardware arithmetic, −2147483648..2147483647, overflow → ORA-01426) beat `NUMBER`. `SIMPLE_INTEGER` is `NOT NULL` and **wraps silently** on overflow — fastest, but only when overflow is impossible/intended.

## Compilation & function reuse
- `PLSQL_OPTIMIZE_LEVEL` default **2**; level **3** auto-inlines subprograms (`PRAGMA INLINE(f,'YES'|'NO')` to force/suppress). `PLSQL_CODE_TYPE` default **INTERPRETED**; `NATIVE` speeds compute-heavy code but not SQL (still switches).
- `NOCOPY` passes big `IN OUT` collections/records by reference — caveat: on an unhandled exception the actual argument may be left partially mutated.
- `DETERMINISTIC` marks pure functions (needed for function-based indexes/MVs). `RESULT_CACHE` caches results by argument, auto-invalidated when a dependency changes. `PRAGMA UDF` cuts SQL→PL/SQL call overhead for functions used inside SQL.

## Dynamic SQL, rights, transactions
- `EXECUTE IMMEDIATE stmt USING v1, v2` binds **values** — "the most effective way to make your PL/SQL code invulnerable to SQL injection attacks is to use bind variables"; the engine uses them as data, never parses them. Identifiers can't bind: validate against the data dictionary (`ALL_TAB_COLS`, `ALL_TABLES`) and wrap with `DBMS_ASSERT` (`ENQUOTE_NAME`/`ENQUOTE_LITERAL`/`SIMPLE_SQL_NAME`) — a *supplement*, not a replacement for validation. Convert datetime/number with explicit locale-independent format models (blocks NLS-based injection).
- `AUTHID DEFINER` is the **default** (runs as owner, only role PUBLIC); `AUTHID CURRENT_USER` (invoker's rights) is preferred for shared code but requires the owner hold `INHERIT PRIVILEGES` on the invoker or it raises ORA-06598. Triggers are DR units; anonymous blocks are IR.
- `PRAGMA AUTONOMOUS_TRANSACTION` runs an **independent** transaction that must `COMMIT`/`ROLLBACK` before returning (else ORA-06519) — ideal for audit rows that survive a caller rollback, but it can self-deadlock against the parent tx's locks.
- `WHEN OTHERS` without `RAISE` silently swallows errors — re-raise or log `SQLERRM` + `DBMS_UTILITY.FORMAT_ERROR_BACKTRACE`. `RAISE_APPLICATION_ERROR` codes live in −20000..−20999 only.
- **Mutating table (ORA-04091):** a row-level trigger can't query/modify its own table — use a compound trigger to buffer rows.

## Sources
- https://docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/Data-Types.html
- https://docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/Nulls.html
- https://docs.oracle.com/en/database/oracle/oracle-database/23/lnpls/plsql-optimization-and-tuning.html
- https://docs.oracle.com/en/database/oracle/oracle-database/23/lnpls/sql-injection.html
- https://docs.oracle.com/en/database/oracle/oracle-database/23/lnpls/invokers-rights-and-definers-rights-authid-property.html
