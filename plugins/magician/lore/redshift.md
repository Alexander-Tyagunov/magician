# Amazon Redshift — core digest
Version: managed cloud MPP columnar DW, Postgres-derived SQL; no user version, features/pricing evolve — verify. RA3 provisioned or Serverless (RPUs).

DO scan less: columnar + zone maps — select only needed cols; no SELECT *; no secondary indexes.
DO collocate joins: DISTKEY a high-card, even join col; ALL for small dims; else EVEN/AUTO; watch skew.
DO SORTKEY filter/join cols (compound = leading prefix) so zone maps skip blocks; leave dist/sort on AUTO.
DO bulk-load via COPY from S3 (parallel, manifest); auto-encodes (AZ64/ZSTD); VACUUM/ANALYZE after big loads.
DO upsert with MERGE; stream Kinesis/MSK into an MV; result cache + MVs for hot aggregates.
DO burst via Concurrency Scaling, not a bigger cluster; store semi-structured as SUPER + PartiQL.

DON'T trust PK/FK/UNIQUE — informational, NOT enforced; invalid keys → wrong results.
DON'T write row-by-row or per-row UPDATE/DELETE — batch every write; no indexes to add.
DON'T default to INTERLEAVED SORTKEY (VACUUM REINDEX cost) or assume full Postgres — some types/functions unsupported.

Deep dive — read lore/redshift/{distribution-and-sort-keys,loading-and-maintenance,performance,performance-and-concurrency,spectrum-and-federation}.md

## Sources
docs.aws.amazon.com/redshift/latest/dg: c_best-practices-best-practices · t_Defining_constraints · aws.amazon.com/redshift/pricing
