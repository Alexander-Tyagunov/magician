# Milvus — Scaling & Architecture

Version: 2.5.x LTS / 2.6.x latest; docs track v3.0.x — confirm your build. Cloud-native, storage/compute **disaggregated** → compute scales independently. 2.6 splits stream vs batch across node types + adds **Woodpecker** (zero-disk WAL on object storage).

## Deployment modes — pick by scale
- **Milvus Lite** — `pip install pymilvus`, `MilvusClient("./x.db")`; embedded, prototyping/edge, a few M vectors. Same API, portable to Standalone.
- **Standalone** — all components in one Docker image; single machine, ~100M vectors. Full features but not HA.
- **Distributed** — Kubernetes; isolated ingest vs. query nodes, redundancy, 100M→tens of B. Production/HA. Resource groups here only.
- **Zilliz Cloud** — fully managed (serverless/dedicated); billed in compute units.

## Four layers (Distributed)
- **Access layer** — stateless **proxies**; validate, fan out, MPP-aggregate. Front with an LB. Scale for connection load.
- **Coordinator** — one active "brain": DDL/DCL, TSO/timestamp oracle, query routing, binds WAL to streaming nodes, dispatches compaction/index builds. **Cannot** be replica-scaled by node count — HA is active-standby.
- **Worker nodes** (stateless, scalable): **Streaming node** = shard mini-brain, serves *growing* data via WAL, seals it; **Query node** loads *sealed* data, serves search/query; **Data node** = compaction + index building (older builds had a separate index node).
- **Storage**: **etcd** (metadata/checkpoints), **object storage** (MinIO/S3 — indexes, snapshots), **WAL** (Kafka/Pulsar/Woodpecker).

## Shards & replicas
- **Shards** = DML channels, fixed at create (`shards_num`); parallelize *writes*. Over-sharding wastes resources — a few is usually enough.
- **In-memory replicas** load the same sealed segments onto multiple query nodes → higher QPS and instant failover (reroute, no reload). Set `replica_number` at load; a replica group holds one shard replica per shard (streaming + historical; shard leader serves growing). Search runs once ≥1 replica is up; costs RAM × replicas.

## Resource groups (Distributed only, declarative v2.4.1+)
Physically isolate query nodes per tenant. `__default_resource_group` holds all nodes at start (undeletable). Config `requests`/`limits`/`transfer_from`/`transfer_to`; Milvus keeps `requests.nodeNum < size < limits.nodeNum`. Match #groups to #replicas to isolate each.

## Scaling levers
Query nodes → read/QPS + replicas; data/index nodes → ingest & build speed; streaming nodes → writes; proxies → connections. Scale **out**, not up. Scale **in gradually** (one node at a time, verify) or use HPA.

## Compaction
Auto-merges small sealed segments, purges deletes/TTL-expired data. **Clustering compaction**: pick a scalar `clustering_key`; Milvus co-locates entities by key range and builds PartitionStats so filtered searches **prune** whole segments (big QPS wins on selective filters). Needs `dataCoord.compaction.clustering.enable` + `queryNode.enableSegmentPrune`. Best on >1M-row collections.

See lore/milvus/collections-and-index-types.md (segments, partitions), lore/milvus/search-and-consistency.md (consistency ↔ streaming/sealed), lore/milvus/performance.md, lore/databases/{connection-pooling,resilience-and-observability}.md.

## Sources
milvus.io/docs — architecture_overview · replica · resource_group · scaleout · install-overview · clustering-compaction · zilliz.com/cloud
