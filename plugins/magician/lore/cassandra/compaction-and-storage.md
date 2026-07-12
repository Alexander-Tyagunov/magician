# Apache Cassandra — Compaction & Storage

LSM-tree engine: writes append-only; deletes/updates are new writes reconciled at read/compaction by write-timestamp (last-write-wins). Current stable 5.0.8; 4.1.x/4.0.x still maintained — verify gates.

## Write path & SSTable anatomy
- Write → **commit log** (durability; `commitlog_sync` `periodic`=default fsync ~10s / `batch`=ack after fsync; `commitlog_segment_size` 32MiB) → **memtable** (sorted, in-mem) → **flush** → immutable **SSTable**. Commit-log segments purge after their memtables flush.
- SSTable components (Big format): `Data.db`, `Index.db`, `Summary.db` (every 128th index entry), `Filter.db` (partition-key bloom filter), `Statistics.db`, `CompressionInfo.db`, `Digest.crc32`; `SAI_*.db` when a storage-attached index (SAI, new in 5.0) exists.
- **BTI (trie-indexed) format**, new in 5.0 (CEP-25): replaces `Index.db`+`Summary.db` with `Partitions.db`+`Rows.db` tries — smaller, faster lookups, better for large partitions. Enable via `cassandra.yaml`: `sstable: {selected_format: bti}` (default stays `big`/`oa`, whose 5.0 rev widened `deletionTime` to a long, fixing the 2038 TTL overflow). Run `nodetool upgradesstables` after a format/major-version change.

## Compaction fundamentals
Compaction merge-sorts SSTables into fewer, purging shadowed cells, expired TTL rows, and droppable **tombstones**. Fewer SSTables per read = fewer bloom/index probes = faster reads. Two costs: **write amplification** (data rewritten repeatedly) and transient **space amplification** (old + new SSTables coexist mid-compaction — keep free disk ≥ the largest compaction's output).
- Tombstones survive `gc_grace_seconds` (default 864000 = 10 days) so deletes reach all replicas. DON'T let repair lapse past gc_grace or deleted data resurrects. `tombstone_threshold` 0.2 / `tombstone_compaction_interval` 86400s trigger single-SSTable purges.

## Strategies (pick by access pattern — the NoSQL storage-modeling lever)
- **UCS (UnifiedCompactionStrategy)** — 5.0 default recommendation; stateless, params change in-flight, shards for parallel compaction on dense nodes. `scaling_parameters` `w`: `T4`≈STCS (tiered, low WA/high RA), `L10`≈LCS (leveled, high WA/low RA), `N`=middle; per-level lists allowed. `target_sstable_size` 1GiB, `base_shard_count` 4, `min_sstable_size` 100MiB, `sstable_growth` 0.333.
- **STCS** — buckets similar-sized SSTables (`min_threshold` 4/`max_threshold` 32, `bucket_low` 0.5/`bucket_high` 1.5). Write-cheap but high space amplification; rows spread across many SSTables.
- **LCS** — levels each ~10× prior (`sstable_size_in_mb` 160, `fanout_size` 10); non-overlapping within a level ⇒ ~1 SSTable/level per read. Read-heavy; ~10% extra disk but IO/CPU-heavy. Falls back to STCS-in-L0 above 32 SSTables.
- **TWCS** — time-series + TTL. `compaction_window_unit` DAYS/`compaction_window_size` (aim 20–30 windows); once a window fully expires, the whole SSTable drops — no tombstone scan. DON'T `DELETE`, `USING TIMESTAMP`, or skip repair: comingled old/new data (read-repair/hints) defeats whole-SSTable expiry. `unsafe_aggressive_sstable_expiration` risks data resurrection.

```sql
ALTER TABLE ks.t WITH compaction =
  {'class':'UnifiedCompactionStrategy','scaling_parameters':'L10','target_sstable_size':'256MiB'};
```

DON'T run `nodetool compact` (major) on STCS/LCS — one giant SSTable results that never re-compacts. ScyllaDB is C*-CQL-compatible; adds ICS to cut STCS space-amp.

## Sources
- cassandra.apache.org/doc/latest/cassandra/managing/operating/compaction/ (ucs, stcs, lcs, twcs, overview)
- cassandra.apache.org/doc/latest/cassandra/architecture/storage-engine.html
- cwiki.apache.org/confluence/display/CASSANDRA/CEP-25%3A+Trie-indexed+SSTable+format
