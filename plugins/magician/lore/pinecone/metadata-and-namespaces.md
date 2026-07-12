# Pinecone — Metadata & Namespaces

Managed serverless vector DB; verify current API — GA except early-access flags noted inline.

## Metadata model
Each record carries flat key/value metadata. Value types: string, number (ints stored as 64-bit float), boolean, list of strings. NO nested objects, no null (drop the key), keys are strings not starting with `$`. Budget ~40KB per record — store filter keys + a small pointer, not whole documents (keep source text/blobs in your own store, reference by id).

## Filtering (single-stage ANN)
Pass `filter` at query time; filter and vector search run together, so results are top-k WITHIN the matching subset (not post-filtered). Operators: `$eq`,`$ne`,`$exists` (num/str/bool); `$gt`,`$gte`,`$lt`,`$lte` (number only); `$in`,`$nin` (str/num, ≤10,000 values). Only `$and`/`$or` at the top level. Shorthand `{"genre":"drama"}` == `$eq`. A list-valued field matches ANY of its values — you can't require two via `$and`, and a raw array as a filter value is a compile error.
- Over-filtering hurts recall/latency: a predicate excluding almost everything forces scanning far more of the namespace to fill top-k. Prefer namespaces for the highest-cardinality partition; reserve filters for secondary, less selective attributes.
- Numeric ranges need number type; years/prices stored as strings won't `$gt`.

## Selective metadata indexing
By default serverless indexes ALL metadata for filtering (costs build + query work). To restrict, declare `schema.fields` with `"filterable": true` — index-level rules apply to namespaces without their own; namespace rules override. Early access, API version `2025-10`, not in the CLI, and IMMUTABLE after index/namespace creation — plan the schema up front. Unindexed fields are stored and returned but not filterable.

## Namespaces
Records are partitioned into namespaces; every upsert/query/fetch/list targets exactly ONE namespace, created implicitly on first upsert (`"__default__"` for the unnamed default). One namespace per tenant/customer gives isolation AND speed — a scoped query scans only that partition, the biggest structural latency lever at scale. No cross-namespace query: to search several, fan out in parallel and merge/rerank client-side. Rename/move records isn't supported — delete + re-upsert.
- Scale: Standard/Enterprise handle very large namespace counts; >100k → contact support. Starter is limited.
- Manage: list returns up to 100 (page via `pagination_token`/`limit`); describe returns `record_count`; delete is IRREVERSIBLE.

## Rerank interplay
`fields` controls which metadata is returned; integrated `rerank` (`rank_fields`, `top_n` over `top_k` candidates) re-scores results from the queried namespace. Retrieve a wide `top_k` under your filter, then rerank down. See lore/pinecone/query-and-hybrid-search.md.

DO partition the dominant tenant/segment as namespaces; filter on secondary attributes.
DO keep metadata lean; pin numeric fields to number type.
DO decide selective-index schema before creation (immutable).
DON'T post-filter client-side to fake missing operators — it under-fetches top-k.
DON'T rely on cross-namespace search or namespace rename — neither exists.

See also lore/pinecone/indexes-and-upsert.md, performance.md, lore/databases.md.

## Sources
docs.pinecone.io/guides: index-data/indexing-overview · search/filter-by-metadata · index-data/create-an-index · manage-data/manage-namespaces · search/rerank-results
