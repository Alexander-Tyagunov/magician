# Amazon Redshift — Spectrum & Federation

Postgres-derived SQL, two ways to reach data you don't store: **Spectrum** (S3 files via an external catalog) and **federated query** (live RDS/Aurora Postgres & MySQL). Both attach via `CREATE EXTERNAL SCHEMA` but diverge from PostgreSQL; verify.

## Diverges from PostgreSQL
- `EXTERNAL SCHEMA`/`TABLE`/`PARTITIONED BY` and `$path`/`$size` are Redshift-only. Redshift has no `postgres_fdw` / `FOREIGN TABLE`; federated query is a distinct engine (docs note federated queries aren't reachable through a PostgreSQL FDW).
- External data is **read-only** — no writes to the source; export via `UNLOAD` to S3.

## Spectrum
DO register the external DB in **AWS Glue Data Catalog** (Athena catalog is legacy) via `FROM DATA CATALOG DATABASE '..' REGION '..' IAM_ROLE '..'`. Role needs S3 GET/LIST + `glue:GetTable`; add `CATALOG_ROLE` cross-account.
DO store facts as **Parquet/ORC** — columnar column pruning + predicate pushdown (text/JSON scan whole rows) + nested types.
DO **partition** on a filtered key (usually time) so the planner prunes folders. Partition columns live in the S3 path, not the row data: `PARTITIONED BY (saledate char(10))` then `ALTER TABLE ... ADD PARTITION (saledate='2008-01') LOCATION '.../saledate=2008-01/'`. Partitions are invisible until registered (crawler or `ADD PARTITION`, ≤100/stmt); inspect `SVV_EXTERNAL_PARTITIONS`.
DO keep big facts in S3, **small dimensions local**, join in one query. `EXPLAIN` shows `S3 Seq Scan` steps pushed to Spectrum.

**Cost:** Spectrum bills **bytes scanned from S3** (per-TB, ~10 MB min/query; DDL/failed queries free) — partitions + narrow columns cut it. On **provisioned clusters (incl. RA3)** it bills **separately, on top of node-hours**. Only **Serverless** folds external-S3 scans into RPU compute (no separate Spectrum charge); newer built-in data-lake nodes avoid one. Selecting `$path`/`$size` is a charged scan.

DON'T `SELECT *` on wide external tables, leave gzip-JSON, use many tiny files, or skip registering new partitions (silently missing data).

## Federated query
DO source-type the schema; creds come from **Secrets Manager** (never inline), role needs `secretsmanager:GetSecretValue`:
```sql
CREATE EXTERNAL SCHEMA pg_live FROM POSTGRES
  DATABASE 'appdb' SCHEMA 'public' URI 'host.rds.amazonaws.com' PORT 5432
  IAM_ROLE 'arn:...:role/FedRole' SECRET_ARN 'arn:...:secret/db';
```
`FROM MYSQL` takes no `SCHEMA` and defaults PORT 3306. Redshift pushes predicates to the remote, then parallelizes results across compute nodes.
DO use it for **ELT / live lookups** — `INSERT ... SELECT` operational rows into a local table — not to scan huge remote tables (hammers the OLTP source).

**Txn semantics:** Postgres federation opens `READ ONLY REPEATABLE READ` on the remote (`pg_export_snapshot` + read lock); an Aurora **reader** endpoint may raise "invalid snapshot" — use an instance endpoint or `pg_federation_repeatable_read=false` (READ COMMITTED). MySQL is READ COMMITTED only.

DON'T expect writes, `ALTER SCHEMA` (drop+recreate), concurrency scaling, or cheap cross-Region. Source must reach the cluster VPC (SG/peering; VPC routing + a Secrets Manager endpoint cross-VPC). MySQL zero `DATE`/`TIMESTAMP` → NULL.

## Sources
- docs.aws.amazon.com/redshift/latest/dg: c-getting-started-using-spectrum · r_CREATE_EXTERNAL_SCHEMA · c-spectrum-external-tables
- docs.aws.amazon.com/redshift/latest/dg: federated-overview · federated-limitations (no PostgreSQL FDW)
