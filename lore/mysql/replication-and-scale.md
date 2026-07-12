# MySQL — Replication & Scale

8.4 LTS (5.7→8.4). Async by default; sync only via Group Replication or NDB Cluster. **8.4 removed legacy `master`/`slave` SQL** → syntax error; use `CHANGE REPLICATION SOURCE TO`, `START REPLICA`, `RESET BINARY LOGS AND GTIDS`, `SHOW BINARY LOG STATUS`, `SHOW REPLICA STATUS`.

## Format & GTID
`binlog_format=ROW` (default 5.7.7; deprecated 8.0.34). GTID needs ROW; SBR non-deterministic (`NOW()`, `UUID()`, unkeyed multi-row). Enable: `gtid_mode=ON` (set `enforce_gtid_consistency=ON` first) + `log_bin`. `SOURCE_AUTO_POSITION=1` negotiates missing txns — failover needs no file/pos. `enforce_gtid_consistency=ON` hard-rejects one statement/txn updating both transactional and non-transactional engines; `CREATE TABLE ... SELECT` OK on atomic-DDL engines (one txn); `CREATE/DROP TEMPORARY TABLE` in a txn OK under ROW/MIXED (not replicated), rejected under STATEMENT.

## Semisync
Plugin, both ends (`rpl_semi_sync_source`/`_replica`). Source blocks at commit until `rpl_semi_sync_source_wait_for_replica_count` replicas (default 1) ack — ack = in replica **relay log**, not applied. `..._wait_point=AFTER_SYNC` (default) waits *before* commit (lossless); `AFTER_COMMIT` after. On `..._timeout` (default 10000 ms), no acks → async — **not** hard durability. Failed-over source may hold un-acked txns — **discard, don't re-add**.

## Threads, applier, crash safety
Multithreaded: `replica_parallel_workers > 0` (0 = single thread) + `replica_preserve_commit_order=ON` for commit order. Don't set `replica_parallel_type` — whole variable deprecated (8.0.29); default `LOGICAL_CLOCK` since 8.0.27, so use the default. **8.4 removed `binlog_transaction_dependency_tracking`** — source *always* emits writeset deps (row-based), no knob. Crash-safe replica = `relay_log_recovery=ON` + `sync_binlog=1` + `innodb_flush_log_at_trx_commit=1`. `relay_log_info_repository`/`master_info_repository` deprecated 8.0, **removed 8.4** — metadata in crash-safe InnoDB tables.

## Read scale & routing
Reads → replicas, writes → source; **no native sharding**. Guard replicas: `super_read_only=ON` (blocks even `CONNECTION_ADMIN`/`SUPER`). Don't trust `Seconds_Behind_Source` (0 when idle, jumps on long txn); measure lag from `performance_schema.replication_applier_status_by_worker`. `log_replica_updates` (default ON) needed for chained topologies + a replica's own binlog.

## Group Replication / InnoDB Cluster
Virtually-synchronous Paxos groups; **single-primary default since 8.0**. Every table InnoDB+PK; GTIDs+ROW on; conflicts resolve by certification. `group_replication_consistency` (`EVENTUAL`→`BEFORE`/`AFTER`/`BEFORE_AND_AFTER`) default → `BEFORE_ON_PRIMARY_FAILOVER` (8.4). Wrap as **InnoDB Cluster** (Shell AdminAPI) + **MySQL Router** for R/W split, failover. HA, not write scale-out.

## MariaDB divergence
MariaDB GTIDs `domain-server-sequence` (`gtid_domain_id`), **not** MySQL's `uuid:seqno` — incompatible (replicates *from* MySQL, not reverse). Keeps `CHANGE MASTER TO ... MASTER_USE_GTID={slave_pos|current_pos|no}` and master/slave terms; parallel apply `slave_parallel_threads` + `slave_parallel_mode`; multi-master sync = Galera (`wsrep`), not Group Replication.

## Sources
- refman/8.4/en/ — gtids-restrictions, semisync, group-replication, options-replica, nutshell (8.4 removals)
- relnotes/8.0 news-8-0-29 (replica_parallel_type deprecated), 8-0-27 (LOGICAL_CLOCK default)
- mariadb.com/.../standard-replication/gtid
