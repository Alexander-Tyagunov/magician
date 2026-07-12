# Couchbase — core digest
Version: Server 8.0 GA, latest 8.0.2; prior 7.6/7.2. 8.0 gates: Magma default, 128 vBuckets, vector search. Capella = managed DBaaS. Auto-sharded by doc-key hash — no partition-key design.

DO model for the query: embed read-together data, reference to bound doc size; keyspace = bucket.scope.collection (≤1000 scopes AND ≤1000 collections per cluster).
DO reach by key: KV get/subdoc + USE KEYS is sub-ms — not SQL++ for point reads.
DO back every SQL++ predicate with a GSI; prefer covering; never the primary index in prod.
DO set durability per write: majority (only Ephemeral), persistToMajority strongest; up to 3 replicas but durable writes need ≤2 (impossible at 3).
DO pick scan_consistency: not_bounded (default) vs request_plus for read-your-writes.
DO use small multi-doc ACID txns for cross-doc invariants.
DO isolate tenants via scopes/collections + RBAC.

DON'T scan the primary index or filter unindexed fields — full keyspace scan.
DON'T page with OFFSET on large sets; keyset-page an indexed key.
DON'T assume writes durable — default is none (async).
DON'T chat per-doc; batch KV ops + subdoc for single fields.

Deep dive — read lore/couchbase/{data-model-and-collections,sqlpp-query-and-indexes,durability-and-consistency,performance}.md

## Sources
docs.couchbase.com/server/current · learn/data/{durability,scopes-and-collections}
