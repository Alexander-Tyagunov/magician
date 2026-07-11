Common AI mistakes: SELECT * in production; missing indexes on foreign keys and filter columns; N+1 queries without JOIN or CTE; not using EXPLAIN ANALYZE before deploying slow queries.
Commands: connect: `psql -U user -d db`, analyze: `EXPLAIN ANALYZE SELECT ...`.
Gotchas: JSONB for semi-structured data; CTEs for complex query readability; partial indexes for filtered queries; use transactions for multi-statement operations.
