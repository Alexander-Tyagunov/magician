# Databases — Migrations & schema changes

Engine-level DDL mechanics: how ALTER/CREATE execute, lock, rewrite, replicate. For migration-*tool* workflow (checksums, changesets, expand-contract sequencing) see lore/db-migrations/*. Verified against PostgreSQL 18, MySQL 8.0 / 8.4 LTS, SQLite 3.53 (see Sources).

## Transactional DDL — sizes your migrations
- **PostgreSQL: fully transactional.** CREATE/ALTER/DROP roll back atomically, so a multi-statement migration is all-or-nothing. Can't run in a txn block: `CREATE/DROP INDEX CONCURRENTLY`, `CREATE DATABASE`, `VACUUM`, `ALTER SYSTEM`.
- **MySQL / MariaDB: not transactional.** MySQL 8 "atomic DDL" makes a *single* statement crash-safe (InnoDB data dictionary) but "is not transactional DDL" — DDL "implicitly end[s] any transaction … as if you had done a COMMIT." One DDL per migration; a mid-migration failure leaves earlier statements committed. InnoDB only.
- **SQLite: transactional**, but `ALTER` is minimal (below).

## PostgreSQL lock levels — the real footgun
Most `ALTER TABLE` forms take `ACCESS EXCLUSIVE`; with multiple subcommands "the lock acquired will be the strictest one required by any subcommand." The danger is the queue: a blocked ALTER waits behind one long query, then every *new* query queues behind the ALTER — a sub-ms lock request freezes the whole table. Guard each session: `SET lock_timeout='3s';` (+ `statement_timeout`) so contended DDL fails fast, then retry. Cheaper locks (writes continue): `VALIDATE CONSTRAINT`, `SET STATISTICS` = `SHARE UPDATE EXCLUSIVE`; `ADD FOREIGN KEY` = `SHARE ROW EXCLUSIVE`.

## PostgreSQL — dodge rewrites & full scans (version-gated)
- **ADD COLUMN with a non-volatile DEFAULT is metadata-only** — value stored in the catalog, "very fast even on large tables" (PG11+). A *volatile* default, stored generated column, or identity column rewrites the whole table + indexes.
- **SET NOT NULL scans the table**, but the scan "is skipped" "if a valid CHECK constraint exists … which proves no NULL can exist" (PG12+): `ADD CONSTRAINT c CHECK (col IS NOT NULL) NOT VALID` → `VALIDATE CONSTRAINT c` → `SET NOT NULL`.
- **Constraints: `ADD … NOT VALID` then `VALIDATE`.** NOT VALID commits immediately without scanning (enforced on new rows); VALIDATE takes only `SHARE UPDATE EXCLUSIVE`. Allowed for FK, CHECK, not-null.
- **`ALTER COLUMN … TYPE` rewrites** table + indexes *unless* the old type is binary-coercible (e.g. `text`↔`varchar`, no collation change). Bundle subcommands in one `ALTER TABLE` to make a single pass. Rewriting forms "are not MVCC-safe": the table "will appear empty" to snapshots taken before the rewrite.

## PostgreSQL — indexes without blocking writes
`CREATE INDEX CONCURRENTLY` builds without blocking DML (plain `CREATE INDEX` "locks out writes … until it's done"). Cost: can't run in a txn block, does *two* scans and "must wait for all existing transactions … to terminate," and on failure "leave[s] behind an 'invalid' index" that still adds write overhead — `DROP` and retry, or `REINDEX INDEX CONCURRENTLY` (PG12+). A failed *unique* index keeps enforcing uniqueness. On partitioned tables build per-partition then create the parent index (metadata only). Remove with `DROP INDEX CONCURRENTLY`.

## MySQL — online DDL (ALGORITHM / LOCK)
Name both so the server *errors* rather than silently doing a copy.
- **`ALGORITHM=INSTANT`** (metadata only): default for `ADD COLUMN` since 8.0.12, `DROP COLUMN` since 8.0.29 (any position since 8.0.29). Caps: max **64** row versions before INSTANT add/drop is rejected (a table rebuild / `OPTIMIZE TABLE` resets it); ≤1022 internal columns; unavailable on `ROW_FORMAT=COMPRESSED` or FULLTEXT tables.
- **`ALGORITHM=INPLACE, LOCK=NONE`**: rebuilds in place with concurrent read+write (add secondary index, NULL/NOT NULL).
- **Falls to `ALGORITHM=COPY`** (blocks writes) for: changing a column's data type, shrinking a VARCHAR or crossing the 256-byte boundary, dropping a PK alone, adding a STORED generated column.
- **Metadata locks (MDL)** are held until the surrounding transaction ends — one long/idle-in-transaction session blocks *all* DDL on that table. Kill blockers; set `lock_wait_timeout` low.

## Replication & tables too big to lock
DDL replicates; a long copying `ALTER` on the primary serializes on each replica's apply → replication lag. For tables too big to lock, use a shadow-copy+swap tool: **gh-ost** / **pt-online-schema-change** (MySQL), **pg_repack** (Postgres). PostgreSQL logical replication does NOT ship DDL — apply the change on each side yourself, or a new column breaks the apply.

## SQLite — minimal ALTER
Supported: `RENAME TABLE`, `RENAME COLUMN` (3.25+), `ADD COLUMN` (appended; NOT NULL needs a non-NULL default), `DROP COLUMN` (3.35+; fails if PK/UNIQUE/indexed/in a CHECK/FK/generated/trigger/view), `ALTER COLUMN SET/DROP NOT NULL` (3.53+). Anything else (reorder, retype, add/drop PK or UNIQUE) needs the recreate procedure: `PRAGMA foreign_keys=OFF` → `BEGIN` → CREATE new table → `INSERT…SELECT` → DROP old → RENAME new *into* place → recreate indexes/triggers/views → `PRAGMA foreign_key_check` → `COMMIT` → `PRAGMA foreign_keys=ON`. Build under a temp name and rename into the final name; renaming the *old* table first "might corrupt references … in triggers, views, and foreign key constraints."

## Sources
- PostgreSQL 18 ALTER TABLE (locks, rewrite rules, NOT VALID, fast default, MVCC): https://www.postgresql.org/docs/current/sql-altertable.html
- PostgreSQL 18 CREATE INDEX (CONCURRENTLY, invalid index): https://www.postgresql.org/docs/current/sql-createindex.html
- PostgreSQL versioning (18 current; 14–18 supported): https://www.postgresql.org/support/versioning/
- MySQL 8.4 Atomic DDL (atomic ≠ transactional; implicit commit): https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html
- MySQL 8.0 InnoDB online DDL (ALGORITHM/LOCK, INSTANT limits/versions): https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html
- SQLite ALTER TABLE (supported forms, versions, recreate procedure): https://www.sqlite.org/lang_altertable.html
