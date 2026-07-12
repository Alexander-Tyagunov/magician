# orm — Choosing & cross-ORM pitfalls

Data-layer lore. Java + framework covered elsewhere. Schema/DDL is **not** the ORM's job — see `db-migrations` lore. Verify version facts against official docs; APIs below are current as of Hibernate ORM 7.x / jOOQ 3.x / MyBatis 3.x.

**This lore is JVM-wide.** Hibernate/JPA, jOOQ, and MyBatis are Java libraries but are used identically from **Kotlin, Scala, and Groovy** — the rules here (parameterize, N+1, transaction boundaries, fetch strategy) don't change; only the surrounding syntax does (e.g. Kotlin `data class`/`no-arg` plugin for entities, Scala case classes). **Language-*native* ORMs are a different topic and belong in that language's lore, not here:** Kotlin → **Exposed**, **Ktorm**; Scala → **Slick**, **Doobie**, **Quill**, **Magnum**. If a project uses one of those, follow the language lore; if it uses Hibernate/jOOQ/MyBatis from any JVM language, follow this.

## DO — pick the tool by use case
- **Plain JDBC** (`java.sql`) — trivial apps, one-off scripts, tightest control, zero deps. Verbose; you own mapping, connection/resource lifecycle, and `try-with-resources`.
- **jOOQ** — SQL-centric apps. Type-safe Java DSL mirroring SQL from generated schema code; compile-time-checked queries/columns. Reach for it when you *think in SQL* and want DB-vendor features. Editions: Open Source + commercial (Express/Pro/Enterprise).
- **MyBatis** — you want to hand-write SQL but skip JDBC boilerplate. SQL lives in XML mappers or annotations; results map to POJOs/Maps. No dirty-checking, no unit-of-work — it's a SQL mapper, not a full ORM.
- **JPA / Hibernate** — domain-model-centric CRUD apps. Entity graph, dirty checking, cascades, caching, HQL/JPQL, portability. Best when the object graph *is* the model; worst for report-shaped queries. Use jOOQ/native SQL alongside for analytics.

## DON'T
- DON'T force one tool everywhere. Hibernate for the domain + jOOQ/native SQL for reports is a normal, healthy mix. jOOQ can even map JPA-annotated classes.
- DON'T reach for JPA when the workload is bulk/analytical SQL — you'll drown in N+1 and mapping hacks.

## Version-adaptivity (Hibernate / Jakarta namespace break)
- **Hibernate 5.x** — `javax.persistence.*`, Java 8 baseline.
- **Hibernate 6.x** — `jakarta.persistence.*` (the Jakarta EE 9 `javax`→`jakarta` package rename — a hard, non-optional break), Java 11 baseline; major internal redesign.
- **Hibernate 7.x** — `jakarta.persistence.*`, **Java 17** baseline, targets JPA 3.2.
- DO match imports to the version: `jakarta.persistence.Entity` (6+) vs `javax.persistence.Entity` (5). Mixing packages fails silently or at startup.
- Hibernate-native annotations are `org.hibernate.annotations.*` (e.g. `@BatchSize`, `@Fetch`, `@NaturalId`) across versions.
- jOOQ / MyBatis are namespace-neutral; JDBC (`java.sql.*`) is stable across all Java versions.

## SECURITY — parameterized queries, always
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

## Universal pitfalls

### N+1 selects
DON'T let a loop over N parents fire 1 query per child (1 + N). DO fetch what you need up front.
- JPA default fetch: `@ManyToOne`/`@OneToOne` are **EAGER**; `@OneToMany`/`@ManyToMany` are **LAZY**. Hibernate's own recommendation: mark **all** associations `fetch = LAZY` and fetch eagerly *per query*.
- Fix per-query with a fetch join: `select b from Book b join fetch b.authors` (JPQL) or an EntityGraph. For collections, batch-fetch instead of joining: `@BatchSize(size = 50)` or `@Fetch(FetchMode.SUBSELECT)` (`org.hibernate.annotations.*`).
- jOOQ/MyBatis: N+1 comes from your code — join or use `IN (...)` / `MULTISET` (jOOQ) / nested result maps (MyBatis).

### Cartesian product from multiple join-fetches
DON'T `join fetch` two+ **collections** in one query — rows multiply (M×N) and results balloon.
- DO fetch at most one collection per query; get the rest via `@BatchSize`, subselect, or separate queries. `distinct` hides duplicates in Java but not the wire cost.

### Entity identity / equals & hashCode
- DON'T use a DB-generated `@Id` in `equals`/`hashCode` — it's null before persist, breaking `Set`/`Map` membership across the persist boundary.
- DO base equality on a stable business/natural key (`@NaturalId`), or a client-assigned UUID. Composite-key `@IdClass`/`@EmbeddedId` **must** override `equals`/`hashCode` — a Java `record` satisfies this cleanly.

### Unbounded result sets
- DON'T `SELECT` / `from Entity` without a bound — one big table OOMs the app.
- DO paginate: JPA `setMaxResults`/`setFirstResult`, jOOQ `.limit().offset()`, MyBatis `RowBounds` or SQL `LIMIT`. Prefer keyset (seek) pagination over deep `OFFSET`. Stream large reads (`Stream`/`ScrollableResults`) instead of listing all rows.

### Mapping enums
- DON'T use `@Enumerated(EnumType.ORDINAL)` (the JPA default) — reordering/inserting enum constants silently corrupts stored data.
- DO use `@Enumerated(EnumType.STRING)` (stores the name) — reorder-safe; renames still break, so treat enum names as schema.

### Mapping JSON
- No portable JPA JSON type. DO use `@JdbcTypeCode(SqlTypes.JSON)` (Hibernate 6+) for `jsonb`/`json` columns, or a converter. jOOQ has `JSON`/`JSONB` types + bindings; MyBatis uses a custom `TypeHandler`. Push filtering into DB JSON operators, not Java.

### Migrations are owned separately
- DON'T let `hibernate.hbm2ddl.auto` mutate a real schema (`update`/`create` in prod = data loss / drift). Set it to `none` (or `validate`) outside dev.
- DO own DDL with a migration tool (Flyway/Liquibase). jOOQ *generates code from* the migrated schema, so migrations run first. See `db-migrations` lore.

## Sources
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
