# Databases (universal interaction discipline) — core digest

Standards cue: isolation levels follow ISO SQL:2023; engines differ on defaults/MVCC/phantom.

DO parameterize EVERY query — bind, never concat SQL/NoSQL filters; allow-list dynamic identifiers.
DO keep pools small, cap lifetime/idle; never connect per request.
DO scope txns at the lowest correct isolation (Read Committed default); know each level's anomalies.
DO cap statement + lock timeouts; retry ONLY transient errors (SQLSTATE 40001/40P01) with backoff+jitter, idempotently.
DO index real predicates/joins; read the plan (EXPLAIN) — verify use, not existence.
DO ship backward-compatible changes (expand→migrate→contract); backfill in bounded batches off the hot path.
DO run least-privilege, require TLS, vault secrets; log slow queries + spans — never log secrets/raw values.

DON'T hold a tx open across network calls/think-time.

Deep dive when writing non-trivial databases — read lore/databases/{connection-pooling,transactions-and-isolation,parameterized-queries-and-injection,indexing-and-query-plans,migrations-and-schema-changes,resilience-and-observability}.md

## Sources
cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html; postgresql.org/docs/current/transaction-iso.html; postgresql.org/docs/current/errcodes-appendix.html; opentelemetry.io/docs/specs/semconv/database
