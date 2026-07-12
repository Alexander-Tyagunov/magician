# Apache Cassandra — core digest
Version: 5.0.8 stable; span 3.11/4.0/4.1/5.0. Gates: 5.0 adds SAI storage-attached indexes, VECTOR type + ANN search, Unified Compaction (UCS), trie SSTables. No feature before its major. ScyllaDB = CQL-compatible, shard-per-core alt.

DO model per query: one table per access pattern, denormalize on write — no JOINs.
DO size the partition key for even spread + bounded rows: high-cardinality, no hot/unbounded partitions.
DO put filter cols in the PRIMARY KEY (partition + clustering); order rows via CLUSTERING ORDER.
DO tune consistency per query: LOCAL_QUORUM r+w for strong (W+R>RF); LOCAL_ONE for latency.
DO use NetworkTopologyStrategy with per-DC RF in prod (even single-DC).
DO index with SAI (5.0) over legacy 2i/SASI; query only PK or indexed cols.
DO paginate via driver paging state; batch only same-partition writes.

DON'T use ALLOW FILTERING in prod — it's a cluster-wide scan.
DON'T use multi-partition or UNLOGGED batches for throughput; batches aren't transactions.
DON'T lean on LWT (Paxos/SERIAL) or delete-heavy queue patterns (tombstones) on hot paths.
DON'T run SimpleStrategy in production.

Deep dive when writing non-trivial Cassandra — read lore/cassandra/{data-modeling-and-partitions,consistency-and-replication,queries-and-secondary-indexes,compaction-and-storage,performance}.md

## Sources
cassandra.apache.org/doc/latest · architecture/dynamo · operating/compaction
