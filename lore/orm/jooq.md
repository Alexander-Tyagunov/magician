# orm — jOOQ

jOOQ is **not** an ORM in the JPA sense. It is a type-safe SQL DSL: you write SQL in Java, jOOQ generates a class model from your **actual database schema** (codegen), and the compiler checks your queries. There is **no persistence context, no session, no lazy-loading, no dirty-checking, no first-level cache**. SQL is explicit and eager. Reach for jOOQ when SQL is the point.

Version note: latest is **3.21.x** (this file: 3.21.5; dev branch 3.22). Only the **Open Source Edition** is on Maven Central (`org.jooq:jooq`), and (3.21) it requires **Java 21+** — the OSS edition tracks the latest JDK and has the *most restrictive* baseline. Older JDKs are covered only by the per-JDK **commercial** editions — `org.jooq.pro` (Java 21), `org.jooq.pro-java-17`, `-java-11`, `-java-8` (and `org.jooq.trial*` mirrors) — installed from `repo.jooq.org`, not Central. Check the JDK support matrix before pinning a build. Artifacts: `jooq`, plus `jooq-meta` + `jooq-codegen` for code generation.

## When jOOQ beats JPA — DO
- **DO reach for jOOQ when the workload is SQL-centric:** complex joins, window functions, CTEs, `GROUP BY`/aggregation, reporting, analytics, bulk DML, vendor-specific SQL. JPQL/Criteria fight you here; jOOQ mirrors SQL 1:1.
- **DO use it to eliminate runtime query surprises.** No N+1 from lazy proxies, no flush-order mysteries, no detached-entity exceptions. What you write is what runs.
- **DO combine it with JPA** if you already have entities: use JPA for entity CRUD, jOOQ for the hard read queries. They coexist on the same `DataSource`/transaction.

## When NOT to use it — DON'T
- **DON'T pick jOOQ if you want automatic identity map, cascade persistence, and lazy graphs** — that's JPA/Hibernate's job. jOOQ has no managed-entity lifecycle.
- **DON'T expect the commercial editions on Maven Central.** OSS covers many DBs; some dialects/features are commercial-only.

## Code generation (the foundation) — DO
- **DO generate the model from the live schema** (via `jooq-codegen` / `GenerationTool`, Maven/Gradle plugin, Flyway/Liquibase-migrated DB, or DDL files). Output: `Tables`, `TableRecord`s, `Keys`, POJOs, DAOs.
- **DO regenerate on schema change** and commit or build generated sources deterministically. Type safety is only as fresh as the last codegen run.
- **DON'T hand-write column constants.** The generated `BOOK.TITLE` etc. carry column types; that's what makes the DSL type-safe.

## DSLContext — DO
- **DO create one `DSLContext` per configuration**: `DSLContext create = DSL.using(connection, dialect);` (or `DSL.using(dataSource, SQLDialect.POSTGRES)`).
- **DO share `Configuration`/`DSLContext` across threads** — they are thread-safe **only if** you never call `Configuration.set(...)` after init. For a one-off tweak, use `Configuration.derive()` to copy, never mutate the shared instance. Any custom SPI (e.g. `DataSourceConnectionProvider`) must itself be thread-safe.
- **DO set the correct `SQLDialect`** — it drives rendered SQL and emulations.

```java
Result<Record3<String, String, String>> r =
  create.select(BOOK.TITLE, AUTHOR.FIRST_NAME, AUTHOR.LAST_NAME)
        .from(BOOK).join(AUTHOR).on(BOOK.AUTHOR_ID.eq(AUTHOR.ID))
        .where(BOOK.PUBLISHED_IN.eq(1948))
        .fetch();
```

## SQL injection — NON-NEGOTIABLE
- **DO trust the typed DSL by default.** jOOQ builds a type-safe AST where bind values are nodes; the DSL renders JDBC `?` placeholders and binds via `PreparedStatement`. You **cannot** inject through the typed API. Wrap literals with `DSL.val(x)` when you need an explicit bind value.
- **DON'T concatenate user input into the plain-SQL API.** Methods annotated `@org.jooq.PlainSQL` (since jOOQ 3.6) accept raw SQL strings — `create.fetch(String, Object...)`, `DSL.field(String)`, `DSL.condition(String)`, etc. Their Javadoc carries an injection warning.

```java
// SAFE — placeholders bound as parameters:
create.fetch("SELECT * FROM BOOK WHERE ID = ? AND TITLE = ?", 5, "Animal Farm");
// INJECTION — user input inlined into the string. NEVER do this:
create.fetch("SELECT * FROM BOOK WHERE TITLE = '" + userInput + "'");
```

- **DON'T inline user data via `DSL.inline()` or `StatementType.STATIC_STATEMENT`.** Inlining renders the literal value into SQL text (escaped) instead of binding it. Reserve inlining for **constants/trusted values** or plan-cache tuning — never for untrusted input. Per-query: `Query.getSQL(ParamType)`; per-value: `DSL.inline(x)`; global: `new Settings().withStatementType(StatementType.STATIC_STATEMENT)`.

## Records vs POJOs — DO
- **`Record` (e.g. `BookRecord`) is jOOQ's active-record.** Fetch typed records from a single table with `selectFrom(BOOK)`:
```java
BookRecord book = create.selectFrom(BOOK).where(BOOK.ID.eq(1)).fetchOne();
book.getTitle();                 // typed getter
```
- **`UpdatableRecord.store()` does INSERT-or-UPDATE** based on whether the record is new. IDENTITY values are fetched back after INSERT.
```java
BookRecord b = create.newRecord(BOOK);
b.setTitle("1984");
b.store();                       // INSERT; b.getId() now populated
b.setPublishedIn(1948);
b.store();                       // UPDATE by primary key
```
- **DO map to plain POJOs when you want detached, immutable data** (DTOs, API responses). Use `into(Class)` / `fetchInto(Class)` (backed by `DefaultRecordMapper`); mutable POJOs need a no-arg constructor:
```java
List<MyBook> books = create.select().from(BOOK).fetchInto(MyBook.class);
```
- **DON'T confuse the two:** `Record` is DB-attached (can `store()`); a POJO is inert until you reload it via `create.newRecord(BOOK, pojo)` then `store()`/`executeInsert()`/`executeUpdate()`.

## Transactions — DO
- **DO wrap units of work in `transaction(...)` / `transactionResult(...)`.** Commit is implicit on normal return; **any uncaught exception rolls back** the whole scope.
```java
create.transaction((Configuration trx) -> {
    trx.dsl().insertInto(AUTHOR, AUTHOR.FIRST_NAME, AUTHOR.LAST_NAME)
             .values("George", "Orwell").execute();
    trx.dsl().insertInto(BOOK, BOOK.TITLE).values("1984").execute();
    // implicit commit here
});
int n = create.transactionResult(cfg -> DSL.using(cfg).insertInto(...).execute());
```
- **DO use `trx.dsl()` (the derived `Configuration`) inside the lambda.** DON'T reuse the outer `create` inside a transaction — that escapes the transactional scope.
- **Nested transactions** create implicit savepoints; the inner rolls back to its savepoint on exception, and you decide whether to rethrow and roll back the outer. Requires a `TransactionProvider` that supports nesting.
- **In Spring**, let Spring manage the transaction (`@Transactional` + `TransactionAwareDataSourceProxy`) rather than jOOQ's own `transaction(...)`; don't nest the two managers.

## Sources
- jOOQ Manual (latest): https://www.jooq.org/doc/latest/manual/
- Getting jOOQ / editions & JDK matrix: https://www.jooq.org/doc/3.21/manual/getting-started/getting-jooq
- DSLContext API & thread safety: https://www.jooq.org/doc/3.21/manual/sql-building/dsl-context/thread-safety
- Bind values: https://www.jooq.org/doc/latest/manual/sql-building/bind-values/
- SQL injection: https://www.jooq.org/doc/latest/manual/sql-building/bind-values/sql-injection/
- Inlined parameters: https://www.jooq.org/doc/latest/manual/sql-building/bind-values/inlined-parameters/
- CRUD with UpdatableRecords: https://www.jooq.org/doc/3.21/manual/sql-execution/crud-with-updatablerecords/simple-crud
- Fetching into POJOs: https://www.jooq.org/doc/3.21/manual/sql-execution/fetching/pojos
- Transaction management: https://www.jooq.org/doc/3.21/manual/sql-execution/transaction-management
- jOOQ on GitHub: https://github.com/jOOQ/jOOQ
