# SQLite — Types and limits

Dynamic-typing and hard-limit semantics for SQLite 3.5x (current stable ~3.53, 2026-06; back to 3.37). SQLite binds a datatype to each *value*, not the column — the biggest surprise from statically typed engines.

## Storage classes vs. affinity

- Every value is one of **five storage classes**: NULL, INTEGER (0/1/2/3/4/6/8 bytes on disk, loaded as 64-bit signed), REAL (8-byte IEEE double), TEXT, BLOB (verbatim). There is **no BOOLEAN, DATE, DATETIME, or DECIMAL class** — `TRUE`/`FALSE` (keywords since 3.23.0) are literally `1`/`0`.
- A declared type only sets an **affinity** (a recommendation, not a constraint), derived from substrings in order: contains `INT`→INTEGER; else `CHAR`/`CLOB`/`TEXT`→TEXT; else `BLOB`/no type→BLOB; else `REAL`/`FLOA`/`DOUB`→REAL; else→NUMERIC.
- **Gotchas:** `FLOATING POINT`→INTEGER (matches "INT"); `STRING`→NUMERIC (no "CHAR"); `VARCHAR(255)`→TEXT but `(255)` is *ignored* — SQLite enforces **no length limits** on any declared type. A no-type column gets BLOB affinity and coerces nothing.
- NUMERIC/INTEGER/REAL affinity coerce a text literal to a number only when it round-trips losslessly; hex literals (`0x…`) stay TEXT. `CAST(4.0 AS INT)`→`4` but `CAST(4.0 AS NUMERIC)`→`4.0` — the only difference between the two affinities.

## Comparison, sort, and coercion order

- Cross-class ordering is fixed: **NULL < integers/reals (numeric) < TEXT (collation) < BLOB (memcmp)**, so one column holding both `'5'` (text) and `5` (int) sorts them apart. `ORDER BY` does no coercion; `GROUP BY` keeps classes distinct except numerically-equal INTEGER/REAL; set ops apply **no** affinity.
- Before a comparison, affinity applies to the *other* operand only if lossless. Any operator strips a column's affinity — `WHERE x='5'` uses it, `WHERE +x='5'` does not (a classic index-defeating footgun).

## STRICT tables (3.37.0+) — opt into rigidity

- `CREATE TABLE t(a INT, b TEXT, c ANY) STRICT;` — every column **must** name a type, and only `INT INTEGER REAL TEXT BLOB ANY` are allowed. Bad content raises `SQLITE_CONSTRAINT_DATATYPE` rather than silently storing the wrong class; use it for schema-critical data.
- In a STRICT table `ANY` preserves values exactly (`'000123'` stays text); an ordinary `ANY`/no-type column coerces it to integer `123`.
- `INTEGER PRIMARY KEY` is still a rowid alias (NULL auto-assigns a rowid); `INT PRIMARY KEY` is **not** — STRICT does not change this. Combine with `WITHOUT ROWID` in any order.

## Implementation limits (defaults; many settable via `sqlite3_limit`/PRAGMA/compile flags)

- **Bound params** `SQLITE_MAX_VARIABLE_NUMBER`: **999** before 3.32.0, **32766** since — oversized `IN (?,?,…)`/bulk inserts throw "too many SQL variables"; batch or use `carray`/JSON.
- **Columns** 2000 (max 32767); **join tables** hard-capped at **64** (bitmask); **compound SELECT** 500; **expr depth** 1000; **function args** 100→**1000 since 3.48.0**.
- **String/BLOB length** `SQLITE_MAX_LENGTH` 1 GB (max 2³¹−3); a row is encoded as one BLOB, so this also caps row size.
- **DB size**: `SQLITE_MAX_PAGE_COUNT` default became **2³²−2 pages** in 3.45.0; page 512–65536 B → ~17.5 TB at 4 KiB. **Attached DBs** default 10 (ceiling 125).

## Sources
- Datatypes / affinity / comparison: https://www.sqlite.org/datatype3.html
- STRICT tables: https://www.sqlite.org/stricttables.html
- Implementation limits: https://www.sqlite.org/limits.html
