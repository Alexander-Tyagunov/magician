# MySQL — core digest
Version: LTS 8.4 & 9.7 (5+3yr); 9.0–9.6 Innovation (EOL); 8.0 EOL Apr 2026; 5.7 EOL. 8.0 adds CTEs, window fns, utf8mb4 defaults vs 5.7.

DO use InnoDB, not MyISAM — ACID, row-locked, crash-safe.
DO pool app-side — thread-per-connection (max_connections 151); conn < wait_timeout (8h).
DO default utf8mb4/utf8mb4_0900_ai_ci; utf8=utf8mb3 (deprecated 3-byte, no emoji).
DO keep the PK small + monotonic — InnoDB clusters + indexes carry it; UUID PKs fragment.
DO read plans via EXPLAIN ANALYZE; index join/filter/sort cols; InnoDB idx BTREE.
DO default REPEATABLE READ, not READ COMMITTED: snapshot + next-key/gap locks; retry 1213/1205.
DO bind ? placeholders; caching_sha2_password over TLS; least-privilege, no runtime DDL.

DON'T use FLOAT/DOUBLE for money (use DECIMAL) or implicit coercion — WHERE code=1 on a VARCHAR col skips the index (per-row convert); quote it (code='1').
DON'T treat MariaDB as drop-in: JSON=LONGTEXT, GTID/auth differ, engines Aria/ColumnStore.
DON'T run huge single-stmt DML/blocking ALTER — batch; ALGORITHM=INSTANT/INPLACE + lock_wait_timeout.
DON'T hold a tx across app/network calls — locks + history-list bloat.

Deep dive when writing non-trivial MySQL — read lore/mysql/{connection-and-pooling,engines-types-and-charset,indexing-and-explain,transactions-and-isolation,replication-and-scale,performance}.md

## Sources
dev.mysql.com/doc/refman/8.4/en/ · mariadb.com/kb (vs-mysql)
