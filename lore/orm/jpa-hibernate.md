# orm — JPA / Hibernate

Data-layer specifics for JPA (Jakarta Persistence) on Hibernate ORM. Assume Java + Spring/Micronaut/Quarkus lore live separately. Verify facts against current docs; version facts below are checked against Hibernate release matrix + reference guide.

## Version & namespace (decide FIRST — it dictates every import)

DO detect the Hibernate major before writing imports. Hibernate **6.0+ and 7.x → `jakarta.persistence.*`**; Hibernate **5.x → `javax.persistence.*`**. This is a hard break, not a rename.
- Hibernate 6.0 (2022) = Jakarta Persistence 3.0/3.1, min **Java 11**. Dialect auto-detected — drop `hibernate.dialect`.
- Hibernate 7.x = Jakarta Persistence 3.2, min **Java 17**.
- Hibernate 5.6 = JPA 2.2, `javax.persistence`, Java 8 (5.5+ shipped transformed `jakarta` artifacts as a bridge).

DON'T mix namespaces in one project. If a lib still imports `javax.persistence`, it is JPA ≤2.2 / Hibernate ≤5.x — do not pair with Hibernate 6+.

```java
// Hibernate 6+/7            // Hibernate 5.x
import jakarta.persistence.*; import javax.persistence.*;
```

## Entity mapping & IDs

DO annotate `@Entity`; give a surrogate `@Id @GeneratedValue`. Strategies (`GenerationType`): `IDENTITY` (DB autoincrement — disables JDBC insert batching), `SEQUENCE` (preferred on Postgres/Oracle; tune `@SequenceGenerator(allocationSize=…)` to batch id blocks), `TABLE` (portable, slow), `UUID` (Hibernate 6+), `AUTO` (picks SEQUENCE/TABLE/UUID by type+DB).
DON'T expose columns you don't map; use `@Column`, `@Table`, `@Version` (optimistic lock — `Integer`/`Long`/`Instant`/`LocalDateTime`).

## Associations & fetch types — the #1 source of bugs

DO make **every** association LAZY. JPA defaults: `@ManyToOne` and `@OneToOne` = **EAGER** (bad); `@OneToMany`/`@ManyToMany` = LAZY. Override the to-one defaults explicitly:
```java
@ManyToOne(fetch = FetchType.LAZY) Publisher publisher;
@OneToMany(mappedBy = "publisher") Set<Book> books; // already LAZY
```
DON'T use EAGER: it can't be turned off per-query and silently triggers N+1. Own the FK on the `@ManyToOne` side; use `@OneToMany(mappedBy=…)` as the inverse.

## N+1 problem

DO fetch what a query needs up front. Symptom: 1 query for parents + N queries for each parent's association.
- HQL/JPQL: `join fetch` (or `left join fetch` to keep parents with no children).
  ```hql
  select b from Book b left join fetch b.publisher join fetch b.authors
  ```
- Or an `@EntityGraph` (JPA standard, dynamic fetch plan) / Hibernate `@FetchProfile`.
DON'T "fix" N+1 by flipping associations to EAGER — that spreads the problem. DON'T `join fetch` two sibling collections in one query (Cartesian product); use one collection + `@BatchSize`, or separate queries.

## LazyInitializationException & open-session-in-view

DO fetch every association you'll touch **before the persistence context (session/tx) closes** — via join fetch or entity graph. LIE = accessing a lazy proxy after the session is gone.
DON'T rely on **open-session-in-view (OSIV)** to paper over it. OSIV holds the session open across view rendering: it hides missing fetches, fires lazy N+1 outside the tx, and holds DB connections longer. Disable it (Spring: `spring.jpa.open-in-view=false`) and fetch explicitly.

## Transactions, persistence context, dirty checking, flush

DO scope work in a transaction; the persistence context (first-level cache) lives per session. Managed entities are **dirty-checked** — modifying a field inside the tx auto-updates on flush; no explicit `save`/`update` needed for already-managed entities.
DO let flush be automatic (`FlushModeType.AUTO`: before matching queries + at commit). Use `FlushModeType.COMMIT` only when you know no query depends on pending changes.
DON'T do slow/remote work (HTTP, large loops) inside a tx — you pin a DB connection. Keep transactions short; read-heavy paths can use a `StatelessSession` (no first-level cache, no dirty checking).

## DTO projections — don't fetch entities to read them

DO project straight to a DTO/record for read-only queries. Skips the persistence context, cheaper, no lazy traps.
```java
record IsbnTitle(String isbn, String title) {}
em.createQuery("select b.isbn, b.title from Book b", IsbnTitle.class).getResultList();
// or: select new com.app.IsbnTitle(b.isbn, b.title) from Book b
```
DON'T load full entity graphs just to map a few fields to JSON.

## equals() / hashCode()

DO base them on an immutable **business/natural key** (e.g. ISBN), not the generated `@Id` (null before persist) and not all fields. Use `instanceof` (proxy-safe), not `getClass()`.
```java
@Override public boolean equals(Object o){ return o instanceof Book b && isbn.equals(b.isbn); }
@Override public int hashCode(){ return isbn.hashCode(); }
```
DON'T use the auto-generated id (breaks `Set` semantics across persist) or mutable fields.

## SQL safety — non-negotiable

DO bind all user input with named/ordinal parameters. Applies to JPQL/HQL, Criteria, and native SQL.
```java
em.createQuery("from Book b where b.title = :t", Book.class).setParameter("t", title);
em.createNativeQuery("select * from books where isbn = ?1", Book.class).setParameter(1, isbn);
```
DON'T ever concatenate/interpolate user input into a query string — SQL injection. No exceptions. Allowlist dynamic identifiers (table/column/sort keys); parameters can't stand in for them.

## Sources
- https://docs.hibernate.org/orm/current/introduction/html_single/Hibernate_Introduction.html
- https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html
- https://hibernate.org/orm/releases/
- https://github.com/hibernate/hibernate-orm (documentation/src/main/asciidoc: introduction/Entities.adoc, introduction/Querying.adoc, userguide/chapters/fetching/Fetching.adoc, userguide/appendices/BestPractices.adoc, querylanguage/From.adoc)
- https://jakarta.ee/specifications/persistence/
