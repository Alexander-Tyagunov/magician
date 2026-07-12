# Amazon Neptune — core digest
Version: managed AWS graph service, versionless; features evolve per engine release. Neptune Database (provisioned/Serverless) + Neptune Analytics (in-memory). Gremlin + openCypher (property graph); SPARQL 1.1 (RDF).

DO route writes to the writer endpoint, reads to readers (up to 15 replicas).
DO parameterize — Gremlin bindings, openCypher params, SPARQL — for plan reuse + safety.
DO anchor traversals on an indexed start node; Neptune auto-indexes every statement — no user indexes.
DO explain/profile nontrivial queries; upper-bound variable-length paths; avoid disconnected patterns.
DO bulk-load from S3 (non-ACID loader) for big ingests; batch small writes with UNWIND, not per-row.
DO connect in-VPC over TLS 1.2 with IAM SigV4 (no user/password); scope with IAM condition keys.

DON'T expect CREATE INDEX; the one optional extra is the OSGP lab-mode index (neptune_lab_mode ObjectIndex=enabled) — new/empty cluster only, no rebuild.
DON'T create supernodes — model hubs with intermediate nodes or dedicated edge types.
DON'T exceed the 150 MB HTTP limit or 55 MB per value (blobs -> S3); no null chars; deletes never reclaim storage — split big txns.

Deep dive when writing non-trivial Neptune — read lore/neptune/{query-languages-gremlin-opencypher-sparql,data-loading-and-modeling,performance}.md

## Sources
docs.aws.amazon.com/neptune/latest/userguide/intro.html · feature-overview-data-model.html · limits.html
