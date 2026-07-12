# MySQL — Engines, types, and charset

Engine-level storage, type, and encoding semantics for MySQL 8.0/8.4 LTS (spanning 5.7→8.4). For EXPLAIN, sargability, and composite-index order see lore/databases/indexing-and-query-plans.md — this file is storage/type behavior, not the planner.

## Pick the engine deliberately

- **InnoDB is the default and the only sane OLTP choice.** Only InnoDB (and NDB Cluster) give **transactions, row-level locking, MVCC, crash recovery, and enforced `FOREIGN KEY`s**. MyISAM and MEMORY are table-lock-only, non-transactional, and lose data on crash. MyISAM *parses* FK syntax but silently ignores it — a table full of dangling refs looks fine until you migrate to InnoDB.
- **DON'T** mix engines in one transactional workflow: a write touching a MyISAM table is not rolled back when the surrounding InnoDB tx aborts. Verify with `SHOW TABLE STATUS` / `SHOW ENGINES`.

## Row format governs off-page storage AND index limits

- Default `ROW_FORMAT` is **`DYNAMIC`** (since 5.7.9; set by `innodb_default_row_format`). Legacy `COMPACT`/`REDUNDANT` store a **768-byte prefix of every `VARCHAR`/`BLOB`/`TEXT` inline** in the clustered leaf plus a 20-byte pointer — bloating B-tree nodes and cutting rows/page. `DYNAMIC` pushes long columns fully off-page (20-byte pointer only).
- The max **index key prefix is 3072 bytes on DYNAMIC/COMPRESSED but only 767 on COMPACT/REDUNDANT** (`innodb_large_prefix` was removed in 8.0 — the large limit is now unconditional). This applies to full-column keys too, and scales *down* with a smaller `innodb_page_size`.
- **GOTCHA:** a rebuild (`OPTIMIZE TABLE`, copy `ALTER`) on a table with no explicit `ROW_FORMAT` silently adopts the current default — pin it explicitly if it matters.

## Numeric & date/time traps

- `DECIMAL(M,D)` is exact — use it for money. `FLOAT`/`DOUBLE` are approximate; never `=`-compare them. `FLOAT(M,D)` fixed-precision syntax is **deprecated (8.0.17)**.
- Integer **display width (`INT(11)`) and `ZEROFILL` are deprecated (8.0.17)** and never affected stored range — drop them; size by value (`UNSIGNED` doubles the positive range). `BIGINT UNSIGNED` in arithmetic can overflow/wrap silently.
- `TIMESTAMP` is 4 bytes, range **`1970-01-01 00:00:01`→`2038-01-19 03:14:07` UTC** (the 2038 cliff) — it is stored as UTC and converted to the session `time_zone` both ways, so the same row reads back differently under a different session tz. `DATETIME` (range to 9999) does **no** conversion. Rule: store UTC; use `DATETIME` for far-future/tz-agnostic values, `TIMESTAMP` only when you want session-tz conversion.
- Both support `DEFAULT CURRENT_TIMESTAMP` / `ON UPDATE CURRENT_TIMESTAMP`. `explicit_defaults_for_timestamp` is **ON by default since 8.0**, removing the legacy implicit `NOT NULL`/auto-init on the first `TIMESTAMP` column — declare defaults yourself. `fsp` (fractional seconds) defaults to **0**, not the SQL-standard 6.

## String types & JSON

- `CHAR` is right-padded and trailing spaces are stripped on read; `VARCHAR` carries a 1–2 byte length prefix. The **row size limit is 65,535 bytes across all columns** (charset-inflated: `utf8mb4` counts 4 bytes/char) — `BLOB`/`TEXT` only count ~9–12 bytes toward it, so wide tables force those types.
- `ENUM`/`SET` store a compact integer/bitmask, but `ENUM` **sorts by internal index, not by label** — an easy silent bug. `''`/index 0 is the error value.
- `JSON` is a **native binary type (5.7.8+)**, validated on insert; 8.0 does partial in-place updates (`JSON_SET`) with optimized binlog. It can't be indexed directly or have a literal default — index a `GENERATED` column, or use a **multi-valued index (8.0.17)** for `JSON` arrays.

## Charset & collation: utf8mb4 or nothing

- Server default is **`utf8mb4` / `utf8mb4_0900_ai_ci` since 8.0** (was `latin1`/`latin1_swedish_ci` in 5.7). **`utf8` is a deprecated alias for `utf8mb3`** (BMP-only, 3 bytes) — it cannot store emoji/supplementary chars. Always use `utf8mb4`.
- `_0900` collations are UCA-9.0.0-based, **faster**, and **`NO PAD`** — trailing spaces are significant, unlike older `PAD SPACE` collations (`'a' <> 'a '`), a real behavior change on upgrade. `_ai_ci` = accent/case-insensitive; `_as_cs` = accent+case-sensitive; `_bin` = codepoint.
- **Set the connection charset in the driver/DSN** (or `SET NAMES utf8mb4`, which sets `character_set_client`/`_connection`/`_results`). A latin1 connection writing to utf8mb4 columns produces double-encoded mojibake. Comparing/joining columns of **different charset or collation** triggers "illegal mix of collations" or a forced conversion that **disables the index** — keep joined keys identical.

## MariaDB divergence

- MariaDB is **not** charset-compatible with MySQL 8: `utf8` still aliases `utf8mb3` (flip via `old_mode`), historic default collation is `utf8mb4_general_ci`, `uca1400` collations arrived in 10.10, and MySQL's `_0900` collations only in 11.4.5.
- MariaDB **`JSON` is an alias for `LONGTEXT COLLATE utf8mb4_bin`** with an auto-added `JSON_VALID()` CHECK — not a binary type; this **breaks row-based replication of JSON from MySQL → MariaDB**. MariaDB also lacks NDB and adds the Aria engine and native `SEQUENCE`s.

## Sources

- MySQL 8.4 — Storage Engines: https://dev.mysql.com/doc/refman/8.4/en/storage-engines.html
- MySQL 8.4 — InnoDB Row Formats & Limits: https://dev.mysql.com/doc/refman/8.4/en/innodb-row-format.html , https://dev.mysql.com/doc/refman/8.4/en/innodb-limits.html
- MySQL 8.4 — Data Types, DATETIME/TIMESTAMP: https://dev.mysql.com/doc/refman/8.4/en/data-types.html , https://dev.mysql.com/doc/refman/8.4/en/datetime.html
- MySQL 8.4 — Character Sets & Unicode collations: https://dev.mysql.com/doc/refman/8.4/en/charset.html , https://dev.mysql.com/doc/refman/8.4/en/charset-unicode-sets.html
- MariaDB — Unicode & JSON: https://mariadb.com/kb/en/unicode/ , https://mariadb.com/kb/en/json-data-type/
