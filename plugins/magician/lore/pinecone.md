# Pinecone — core digest
Version: managed serverless, no version numbers; verify API/limits at docs.pinecone.io. Serverless default, pods legacy. Billing = storage + read/write + inference tokens; evolves.

DO set metric + dimension + cloud/region at create — all immutable; match your embedding model.
DO match metric to training: cosine (normalized), dotproduct (sparse/hybrid), euclidean.
DO batch upserts: <=1000 rec or 2MB/req (96 w/ text); never one-per-call.
DO scope queries to a namespace — the tenancy unit; limits (100 req/s/op) are per-namespace.
DO filter metadata at query (during search): $eq/$in/$gt/$exists/$and/$or; keep <40KB/vector.
DO raise recall with two-stage rerank (pinecone-rerank-v0, bge-reranker-v2-m3, cohere-rerank-*).
DO consider integrated inference (create_index_for_model) for raw-text; or dense+sparse hybrid.

DON'T change metric/dimension/cloud/region after create — recreate + reindex.
DON'T assume read-after-write: serverless is eventually consistent — poll describe_index_stats.
DON'T store blobs as metadata (40KB cap) or use it as source of truth.
DON'T combine raw sparse+dense scores — normalize (alpha) for single-index hybrid.

Deep dive when writing non-trivial Pinecone — read lore/pinecone/{indexes-and-upsert,metadata-and-namespaces,query-and-hybrid-search,performance}.md

## Sources
docs.pinecone.io/guides/index-data · reference/api/database-limits · guides/search/{rerank-results,hybrid-search}
