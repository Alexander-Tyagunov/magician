# orm — deep dive

> On-demand companion to `lore/orm.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [JPA / Hibernate](#jpa-hibernate) · [jOOQ](#jooq) · [MyBatis](#mybatis) · [Choosing & cross-ORM pitfalls](#choosing-and-pitfalls)

## JPA / Hibernate <a id="jpa-hibernate"></a>

Data-layer specifics for JPA (Jakarta Persistence) on Hibernate ORM. Assume Java + Spring/Micronaut/Quarkus lore live separately. Verify facts against current docs; version facts below are checked against Hibernate release matrix + reference guide.

### Version & namespace (decide FIRST — it dictates every import)

DO detect the Hibernate major before writing imports. Hibernate **6.0+ and 7.x → `jakarta.persistence.*`**; Hibernate **5.x → `javax.persistence.*`**. This is a hard break, not a rename.
- Hibernate 6.0 (2022) = Jakarta Persistence 3.0/3.1, min **Java 11**. Dialect auto-detected — drop `hibernate.dialect`.
- Hibernate 7.x = Jakarta Persistence 3.2, min **Java 17**.
- Hibernate 5.6 = JPA 2.2, `javax.persistence`, Java 8 (5.5+ shipped transformed `jakarta` artifacts as a bridge).

DON'T mix namespaces in one project. If a lib still imports `javax.persistence`, it is JPA ≤2.2 / Hibernate ≤5.x — do not pair with Hibernate 6+.

```java
// Hibernate 6+/7            // Hibernate 5.x
import jakarta.persistence.*; import javax.persistence.*;
```

### Entity mapping & IDs

DO annotate `@Entity`; give a surrogate `@Id @GeneratedValue`. Strategies (`GenerationType`): `IDENTITY` (DB autoincrement — disables JDBC insert batching), `SEQUENCE` (preferred on Postgres/Oracle; tune `@SequenceGenerator(allocationSize=…)` to batch id blocks), `TABLE` (portable, slow), `UUID` (Hibernate 6+), `AUTO` (picks SEQUENCE/TABLE/UUID by type+DB).
DON'T expose columns you don't map; use `@Column`, `@Table`, `@Version` (optimistic lock — `Integer`/`Long`/`Instant`/`LocalDateTime`).

### Associations & fetch types — the #1 source of bugs

DO make **every** association LAZY. JPA defaults: `@ManyToOne` and `@OneToOne` = **EAGER** (bad); `@OneToMany`/`@ManyToMany` = LAZY. Override the to-one defaults explicitly:
```java
@ManyToOne(fetch = FetchType.LAZY) Publisher publisher;
@OneToMany(mappedBy = "publisher") Set<Book> books; // already LAZY
```
DON'T use EAGER: it can't be turned off per-query and silently triggers N+1. Own the FK on the `@ManyToOne` side; use `@OneToMany(mappedBy=…)` as the inverse.

### N+1 problem

DO fetch what a query needs up front. Symptom: 1 query for parents + N queries for each parent's association.
- HQL/JPQL: `join fetch` (or `left join fetch` to keep parents with no children).
  ```hql
  select b from Book b left join fetch b.publisher join fetch b.authors
  ```
- Or an `@EntityGraph` (JPA standard, dynamic fetch plan) / Hibernate `@FetchProfile`.
DON'T "fix" N+1 by flipping associations to EAGER — that spreads the problem. DON'T `join fetch` two sibling collections in one query (Cartesian product); use one collection + `@BatchSize`, or separate queries.

### LazyInitializationException & open-session-in-view

DO fetch every association you'll touch **before the persistence context (session/tx) closes** — via join fetch or entity graph. LIE = accessing a lazy proxy after the session is gone.
DON'T rely on **open-session-in-view (OSIV)** to paper over it. OSIV holds the session open across view rendering: it hides missing fetches, fires lazy N+1 outside the tx, and holds DB connections longer. Disable it (Spring: `spring.jpa.open-in-view=false`) and fetch explicitly.

### Transactions, persistence context, dirty checking, flush

DO scope work in a transaction; the persistence context (first-level cache) lives per session. Managed entities are **dirty-checked** — modifying a field inside the tx auto-updates on flush; no explicit `save`/`update` needed for already-managed entities.
DO let flush be automatic (`FlushModeType.AUTO`: before matching queries + at commit). Use `FlushModeType.COMMIT` only when you know no query depends on pending changes.
DON'T do slow/remote work (HTTP, large loops) inside a tx — you pin a DB connection. Keep transactions short; read-heavy paths can use a `StatelessSession` (no first-level cache, no dirty checking).

### DTO projections — don't fetch entities to read them

DO project straight to a DTO/record for read-only queries. Skips the persistence context, cheaper, no lazy traps.
```java
record IsbnTitle(String isbn, String title) {}
em.createQuery("select b.isbn, b.title from Book b", IsbnTitle.class).getResultList();
// or: select new com.app.IsbnTitle(b.isbn, b.title) from Book b
```
DON'T load full entity graphs just to map a few fields to JSON.

### equals() / hashCode()

DO base them on an immutable **business/natural key** (e.g. ISBN), not the generated `@Id` (null before persist) and not all fields. Use `instanceof` (proxy-safe), not `getClass()`.
```java
@Override public boolean equals(Object o){ return o instanceof Book b && isbn.equals(b.isbn); }
@Override public int hashCode(){ return isbn.hashCode(); }
```
DON'T use the auto-generated id (breaks `Set` semantics across persist) or mutable fields.

### SQL safety — non-negotiable

DO bind all user input with named/ordinal parameters. Applies to JPQL/HQL, Criteria, and native SQL.
```java
em.createQuery("from Book b where b.title = :t", Book.class).setParameter("t", title);
em.createNativeQuery("select * from books where isbn = ?1", Book.class).setParameter(1, isbn);
```
DON'T ever concatenate/interpolate user input into a query string — SQL injection. No exceptions. Allowlist dynamic identifiers (table/column/sort keys); parameters can't stand in for them.

### Sources
- https://docs.hibernate.org/orm/current/introduction/html_single/Hibernate_Introduction.html
- https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html
- https://hibernate.org/orm/releases/
- https://github.com/hibernate/hibernate-orm (documentation/src/main/asciidoc: introduction/Entities.adoc, introduction/Querying.adoc, userguide/chapters/fetching/Fetching.adoc, userguide/appendices/BestPractices.adoc, querylanguage/From.adoc)
- https://jakarta.ee/specifications/persistence/

## jOOQ <a id="jooq"></a>

jOOQ is **not** an ORM in the JPA sense. It is a type-safe SQL DSL: you write SQL in Java, jOOQ generates a class model from your **actual database schema** (codegen), and the compiler checks your queries. There is **no persistence context, no session, no lazy-loading, no dirty-checking, no first-level cache**. SQL is explicit and eager. Reach for jOOQ when SQL is the point.

Version note: latest is **3.21.x** (this file: 3.21.5; dev branch 3.22). Only the **Open Source Edition** is on Maven Central (`org.jooq:jooq`), and (3.21) it requires **Java 21+** — the OSS edition tracks the latest JDK and has the *most restrictive* baseline. Older JDKs are covered only by the per-JDK **commercial** editions — `org.jooq.pro` (Java 21), `org.jooq.pro-java-17`, `-java-11`, `-java-8` (and `org.jooq.trial*` mirrors) — installed from `repo.jooq.org`, not Central. Check the JDK support matrix before pinning a build. Artifacts: `jooq`, plus `jooq-meta` + `jooq-codegen` for code generation.

### When jOOQ beats JPA — DO
- **DO reach for jOOQ when the workload is SQL-centric:** complex joins, window functions, CTEs, `GROUP BY`/aggregation, reporting, analytics, bulk DML, vendor-specific SQL. JPQL/Criteria fight you here; jOOQ mirrors SQL 1:1.
- **DO use it to eliminate runtime query surprises.** No N+1 from lazy proxies, no flush-order mysteries, no detached-entity exceptions. What you write is what runs.
- **DO combine it with JPA** if you already have entities: use JPA for entity CRUD, jOOQ for the hard read queries. They coexist on the same `DataSource`/transaction.

### When NOT to use it — DON'T
- **DON'T pick jOOQ if you want automatic identity map, cascade persistence, and lazy graphs** — that's JPA/Hibernate's job. jOOQ has no managed-entity lifecycle.
- **DON'T expect the commercial editions on Maven Central.** OSS covers many DBs; some dialects/features are commercial-only.

### Code generation (the foundation) — DO
- **DO generate the model from the live schema** (via `jooq-codegen` / `GenerationTool`, Maven/Gradle plugin, Flyway/Liquibase-migrated DB, or DDL files). Output: `Tables`, `TableRecord`s, `Keys`, POJOs, DAOs.
- **DO regenerate on schema change** and commit or build generated sources deterministically. Type safety is only as fresh as the last codegen run.
- **DON'T hand-write column constants.** The generated `BOOK.TITLE` etc. carry column types; that's what makes the DSL type-safe.

### DSLContext — DO
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

### SQL injection — NON-NEGOTIABLE
- **DO trust the typed DSL by default.** jOOQ builds a type-safe AST where bind values are nodes; the DSL renders JDBC `?` placeholders and binds via `PreparedStatement`. You **cannot** inject through the typed API. Wrap literals with `DSL.val(x)` when you need an explicit bind value.
- **DON'T concatenate user input into the plain-SQL API.** Methods annotated `@org.jooq.PlainSQL` (since jOOQ 3.6) accept raw SQL strings — `create.fetch(String, Object...)`, `DSL.field(String)`, `DSL.condition(String)`, etc. Their Javadoc carries an injection warning.

```java
// SAFE — placeholders bound as parameters:
create.fetch("SELECT * FROM BOOK WHERE ID = ? AND TITLE = ?", 5, "Animal Farm");
// INJECTION — user input inlined into the string. NEVER do this:
create.fetch("SELECT * FROM BOOK WHERE TITLE = '" + userInput + "'");
```

- **DON'T inline user data via `DSL.inline()` or `StatementType.STATIC_STATEMENT`.** Inlining renders the literal value into SQL text (escaped) instead of binding it. Reserve inlining for **constants/trusted values** or plan-cache tuning — never for untrusted input. Per-query: `Query.getSQL(ParamType)`; per-value: `DSL.inline(x)`; global: `new Settings().withStatementType(StatementType.STATIC_STATEMENT)`.

### Records vs POJOs — DO
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

### Transactions — DO
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

### Sources
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

## MyBatis <a id="mybatis"></a>

MyBatis is a **SQL mapper**, not a full ORM. You write the SQL; MyBatis maps
params in and rows out, killing JDBC boilerplate. No dirty-checking, no
persistence context, no automatic schema. Reach for it when you want hand-tuned
SQL, legacy/complex queries, stored procs, or fine control over exactly what
hits the DB. Reach for JPA/Hibernate instead when you want entity lifecycle and
generated CRUD.

- Latest: **MyBatis 3.5.19** (Jan 2025). Artifact `org.mybatis:mybatis`.
- Java baseline: **Java 8+** for 3.5.x (bytecode targets 1.8; `java.time` type
  handlers use JDBC 4.0 `getObject(col, Class)`). Tested through JDK 17–25.
- Spring: `mybatis-spring` + `mybatis-spring-boot-starter` for `@Mapper` scan.

### Security — #{} vs ${} (non-negotiable)

This is the single most important MyBatis rule.

- **`#{param}` → PreparedStatement `?`.** MyBatis binds the value safely via
  JDBC. Safe from SQL injection. "Safer, faster and almost always preferred."
- **`${param}` → raw string substitution.** MyBatis "won't modify or escape the
  string" — it is concatenated straight into the SQL text. This is SQL
  injection if the value comes from a user.

DO
- Use `#{}` for every value: WHERE operands, INSERT/UPDATE columns, LIMIT args.
  ```xml
  <select id="find" resultType="User">
    SELECT * FROM users WHERE email = #{email}
  </select>
  ```
- Use `${}` ONLY for SQL identifiers that can't be bound (table/column name,
  `ORDER BY` column, sort direction) — and ONLY after whitelisting the value
  against a fixed allow-list in Java. Never pass user text through raw.
  ```xml
  ORDER BY ${sortColumn} <!-- sortColumn validated against an enum/allow-list -->
  ```

DON'T
- Never put user input in `${}`. `WHERE name = '${name}'` is injectable.
- Don't reach for `${}` to "fix" a binding that failed — that usually means the
  value belongs in `#{}` and you had a mapping/type issue.
- Don't build SQL by Java string concatenation of user input in providers
  either — use `#{}` placeholders inside the built string.

### XML mappers vs annotations

DO
- Prefer **XML mappers** for anything nontrivial: dynamic SQL, joins, reuse.
  XML is "necessary for the most complex mappings."
- Use **annotations** (`@Select`/`@Insert`/`@Update`/`@Delete`, `@Results`,
  `@Result`, `@ResultMap`, `@Options`, `@Param`) for simple, static statements
  where XML overhead isn't worth it.
- Use `@Param("x")` when a mapper method takes multiple params; reference as
  `#{x}`.

DON'T
- Don't expect annotations to do the heavy lifting: they're "limited in
  expressiveness." `@One`/`@Many` **cannot express recursive/circular join
  mappings** (Java annotation limitation). `@Options` can't specify null.
- For dynamic SQL in annotations you must fall back to `@SelectProvider` etc.
  (a class+method returning the SQL) — clunkier than XML `<if>`/`<foreach>`.
- Don't mix `resultType` and `resultMap` on one statement — one or the other.

### Dynamic SQL (XML)

Four elements cover it: `if`, `choose/when/otherwise`, `trim/where/set`,
`foreach`. Tests are OGNL expressions.

DO
- `<where>` strips a leading `AND`/`OR` and omits `WHERE` when empty. Use it
  instead of hand-managing `1=1`.
  ```xml
  <select id="search" resultType="User">
    SELECT * FROM users
    <where>
      <if test="name != null"> AND name = #{name}</if>
      <if test="minAge != null"> AND age >= #{minAge}</if>
    </where>
  </select>
  ```
- `<set>` for updates — prepends `SET`, trims trailing commas.
- `<foreach>` for `IN` lists — bind each element with `#{item}` (still
  parameterized, still safe):
  ```xml
  DELETE FROM users WHERE id IN
  <foreach item="id" collection="ids" open="(" separator="," close=")">
    #{id}
  </foreach>
  ```
  Attributes: `collection`, `item`, `index`, `open`, `close`, `separator`,
  `nullable`. For a Map, `index`=key, `item`=value.
- `<bind>` to build a LIKE pattern safely, then bind with `#{}`:
  ```xml
  <bind name="p" value="'%' + name + '%'"/>
  ... WHERE name LIKE #{p}
  ```
- `<choose>/<when>/<otherwise>` when exactly one branch should apply.

DON'T
- Don't build LIKE with `LIKE '%${name}%'` — injectable. Use `<bind>` +`#{}`.
- Don't rely on `<foreach>` for huge `IN` lists — most DBs cap parameters
  (e.g. Oracle 1000); batch or use a temp table.

### resultMap

`resultMap` is the most powerful mapping element. Auto-mapping handles matching
column↔property names; declare a `resultMap` for renames, nested objects, and
type control.

DO
- Declare `<id>` for the identity column — MyBatis uses it for instance
  comparison, caching, and nested-result de-duplication.
- `<result column= property=>` for simple fields (name/type mismatches).
- `<association>` = has-one, `<collection ofType=>` = has-many.
- Prefer **nested results (JOIN)** over **nested select** for associations/
  collections to avoid the **N+1 selects problem**.

DON'T
- Don't lazy-nest per row when a single join works — N+1 kills throughput.
- Don't map a collection type in `resultType`; use the contained element type
  and a `<collection>`.

### Session / transaction hygiene

DO
- Always close `SqlSession` — try-with-resources.
- Use mapper interfaces (`session.getMapper(Foo.class)`) for type-safe calls;
  method name matches the statement id.
- Use `ExecutorType.BATCH` for bulk writes; call `flushStatements()`.
- Under Spring, let `@Transactional` + `SqlSessionTemplate` manage sessions —
  don't open your own.

DON'T
- Don't share one `SqlSession` across threads (not thread-safe).
- Default `openSession()` does NOT auto-commit — you must `commit()` writes.

### Sources

- MyBatis 3 home: https://mybatis.org/mybatis-3/
- Mapper XML (#{} vs ${}, resultMap): https://mybatis.org/mybatis-3/sqlmap-xml.html
- Dynamic SQL: https://mybatis.org/mybatis-3/dynamic-sql.html
- Java API / annotations: https://mybatis.org/mybatis-3/java-api.html
- GitHub (version, test matrix): https://github.com/mybatis/mybatis-3
- FAQ (#{} vs ${} injection): https://github.com/mybatis/mybatis-3/wiki/FAQ
- mybatis-spring-boot-starter: https://mybatis.org/spring-boot-starter/

## Choosing & cross-ORM pitfalls <a id="choosing-and-pitfalls"></a>

Data-layer lore. Java + framework covered elsewhere. Schema/DDL is **not** the ORM's job — see `db-migrations` lore. Verify version facts against official docs; APIs below are current as of Hibernate ORM 7.x / jOOQ 3.x / MyBatis 3.x.

**This lore is JVM-wide.** Hibernate/JPA, jOOQ, and MyBatis are Java libraries but are used identically from **Kotlin, Scala, and Groovy** — the rules here (parameterize, N+1, transaction boundaries, fetch strategy) don't change; only the surrounding syntax does (e.g. Kotlin `data class`/`no-arg` plugin for entities, Scala case classes). **Language-*native* ORMs are a different topic and belong in that language's lore, not here:** Kotlin → **Exposed**, **Ktorm**; Scala → **Slick**, **Doobie**, **Quill**, **Magnum**. If a project uses one of those, follow the language lore; if it uses Hibernate/jOOQ/MyBatis from any JVM language, follow this.

### DO — pick the tool by use case
- **Plain JDBC** (`java.sql`) — trivial apps, one-off scripts, tightest control, zero deps. Verbose; you own mapping, connection/resource lifecycle, and `try-with-resources`.
- **jOOQ** — SQL-centric apps. Type-safe Java DSL mirroring SQL from generated schema code; compile-time-checked queries/columns. Reach for it when you *think in SQL* and want DB-vendor features. Editions: Open Source + commercial (Express/Pro/Enterprise).
- **MyBatis** — you want to hand-write SQL but skip JDBC boilerplate. SQL lives in XML mappers or annotations; results map to POJOs/Maps. No dirty-checking, no unit-of-work — it's a SQL mapper, not a full ORM.
- **JPA / Hibernate** — domain-model-centric CRUD apps. Entity graph, dirty checking, cascades, caching, HQL/JPQL, portability. Best when the object graph *is* the model; worst for report-shaped queries. Use jOOQ/native SQL alongside for analytics.

### DON'T
- DON'T force one tool everywhere. Hibernate for the domain + jOOQ/native SQL for reports is a normal, healthy mix. jOOQ can even map JPA-annotated classes.
- DON'T reach for JPA when the workload is bulk/analytical SQL — you'll drown in N+1 and mapping hacks.

### Version-adaptivity (Hibernate / Jakarta namespace break)
- **Hibernate 5.x** — `javax.persistence.*`, Java 8 baseline.
- **Hibernate 6.x** — `jakarta.persistence.*` (the Jakarta EE 9 `javax`→`jakarta` package rename — a hard, non-optional break), Java 11 baseline; major internal redesign.
- **Hibernate 7.x** — `jakarta.persistence.*`, **Java 17** baseline, targets JPA 3.2.
- DO match imports to the version: `jakarta.persistence.Entity` (6+) vs `javax.persistence.Entity` (5). Mixing packages fails silently or at startup.
- Hibernate-native annotations are `org.hibernate.annotations.*` (e.g. `@BatchSize`, `@Fetch`, `@NaturalId`) across versions.
- jOOQ / MyBatis are namespace-neutral; JDBC (`java.sql.*`) is stable across all Java versions.

### SECURITY — parameterized queries, always
- DO use bind parameters / `PreparedStatement` for **every** value derived from input. NEVER concatenate input into SQL — that is SQL injection ("a single vulnerability can be enough for an attacker to dump your whole database").
- **JDBC** — `PreparedStatement` with `?` + `setString/setLong/...`. Never `Statement` + string concat.
- **JPA/Hibernate** — `setParameter(...)` with named (`:name`) or positional (`?1`) params in HQL/JPQL and native queries. Never build HQL from input strings.
- **jOOQ** — the DSL binds values automatically and is injection-safe by construction (type-safe AST). Danger is only "plain SQL" APIs: `create.fetch("... WHERE ID = ?", id)` is safe; `create.fetch("... WHERE ID = " + id)` is not. Plain-SQL methods carry `@org.jooq.PlainSQL` and a Javadoc warning.
- **MyBatis** — `#{}` is a `PreparedStatement` bind (safe). `${}` does raw string substitution — MyBatis "won't modify or escape the string": *"It's not safe to accept input from a user and supply it to a statement unmodified in this way."* Use `${}` only for trusted metadata (table/column/`ORDER BY`), and whitelist it.

```java
// JDBC — DO
try (PreparedStatement ps = con.prepareStatement(
        "SELECT * FROM book WHERE title = ?")) {
    ps.setString(1, userTitle);           // never "... = '" + userTitle + "'"
    try (ResultSet rs = ps.executeQuery()) { ... }
}
```

### Universal pitfalls

#### N+1 selects
DON'T let a loop over N parents fire 1 query per child (1 + N). DO fetch what you need up front.
- JPA default fetch: `@ManyToOne`/`@OneToOne` are **EAGER**; `@OneToMany`/`@ManyToMany` are **LAZY**. Hibernate's own recommendation: mark **all** associations `fetch = LAZY` and fetch eagerly *per query*.
- Fix per-query with a fetch join: `select b from Book b join fetch b.authors` (JPQL) or an EntityGraph. For collections, batch-fetch instead of joining: `@BatchSize(size = 50)` or `@Fetch(FetchMode.SUBSELECT)` (`org.hibernate.annotations.*`).
- jOOQ/MyBatis: N+1 comes from your code — join or use `IN (...)` / `MULTISET` (jOOQ) / nested result maps (MyBatis).

#### Cartesian product from multiple join-fetches
DON'T `join fetch` two+ **collections** in one query — rows multiply (M×N) and results balloon.
- DO fetch at most one collection per query; get the rest via `@BatchSize`, subselect, or separate queries. `distinct` hides duplicates in Java but not the wire cost.

#### Entity identity / equals & hashCode
- DON'T use a DB-generated `@Id` in `equals`/`hashCode` — it's null before persist, breaking `Set`/`Map` membership across the persist boundary.
- DO base equality on a stable business/natural key (`@NaturalId`), or a client-assigned UUID. Composite-key `@IdClass`/`@EmbeddedId` **must** override `equals`/`hashCode` — a Java `record` satisfies this cleanly.

#### Unbounded result sets
- DON'T `SELECT` / `from Entity` without a bound — one big table OOMs the app.
- DO paginate: JPA `setMaxResults`/`setFirstResult`, jOOQ `.limit().offset()`, MyBatis `RowBounds` or SQL `LIMIT`. Prefer keyset (seek) pagination over deep `OFFSET`. Stream large reads (`Stream`/`ScrollableResults`) instead of listing all rows.

#### Mapping enums
- DON'T use `@Enumerated(EnumType.ORDINAL)` (the JPA default) — reordering/inserting enum constants silently corrupts stored data.
- DO use `@Enumerated(EnumType.STRING)` (stores the name) — reorder-safe; renames still break, so treat enum names as schema.

#### Mapping JSON
- No portable JPA JSON type. DO use `@JdbcTypeCode(SqlTypes.JSON)` (Hibernate 6+) for `jsonb`/`json` columns, or a converter. jOOQ has `JSON`/`JSONB` types + bindings; MyBatis uses a custom `TypeHandler`. Push filtering into DB JSON operators, not Java.

#### Migrations are owned separately
- DON'T let `hibernate.hbm2ddl.auto` mutate a real schema (`update`/`create` in prod = data loss / drift). Set it to `none` (or `validate`) outside dev.
- DO own DDL with a migration tool (Flyway/Liquibase). jOOQ *generates code from* the migrated schema, so migrations run first. See `db-migrations` lore.

### Sources
- Hibernate ORM 7 Introduction — https://docs.hibernate.org/orm/current/introduction/html_single/Hibernate_Introduction.html
- Hibernate ORM User Guide (fetching, compatibility, settings) — https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html
- Hibernate ORM repo (docs source) — https://github.com/hibernate/hibernate-orm
- jOOQ manual — https://www.jooq.org/doc/latest/manual/
- jOOQ bind values — https://www.jooq.org/doc/latest/manual/sql-building/bind-values/
- jOOQ SQL injection — https://www.jooq.org/doc/latest/manual/sql-building/bind-values/sql-injection/
- MyBatis 3 reference — https://mybatis.org/mybatis-3/
- MyBatis Mapper XML (`#{}` vs `${}`) — https://mybatis.org/mybatis-3/sqlmap-xml.html
- MyBatis Dynamic SQL — https://mybatis.org/mybatis-3/dynamic-sql.html
- JDBC PreparedStatement tutorial — https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html
