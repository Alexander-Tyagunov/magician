# micronaut — Micronaut Data & reactive

Framework-specific checklist for Micronaut Data (compile-time repositories) and the reactive/R2DBC stack. Assumes `lore/java/*` covers the language. Complements `jdbc`/`orm` lore.

**Version map (verify against the target project's build file):**
- **Micronaut Framework 5.x** (current, `5.1.x`) — JDK 25 baseline, Groovy 5, Kotlin 2.3.
- **Micronaut Framework 4.x** (prior major) — JDK 17 baseline; 3.x — JDK 8 minimum.
- **Micronaut Data 5.x** (current, `5.0.x`/`5.1.x`) ships with framework 5. Micronaut Data 4.x pairs with framework 4.x.
- All coordinates use groupId `io.micronaut.data`. Prefer Micronaut Launch/CLI `--features` over hand-writing coordinates.

## Core model — DO
- DO treat Micronaut Data as **AoT / compile-time**: queries are pre-computed by the annotation processor. No runtime model, no query translation, no reflection, no runtime proxies. A missing/ambiguous root entity is a **compile error**, not a runtime one.
- DO add the annotation processor. It is mandatory or repositories generate nothing:
  ```gradle
  annotationProcessor("io.micronaut.data:micronaut-data-processor")
  // MongoDB/Cosmos instead use micronaut-data-document-processor
  ```
- DO define repositories as **interfaces** extending a repository type, annotated per backend:
  ```java
  @JdbcRepository(dialect = Dialect.POSTGRES)          // JDBC
  public interface BookRepository extends CrudRepository<Book, Long> {}
  ```
- DO map entities with Micronaut Data annotations (`io.micronaut.data.annotation.*`): `@MappedEntity`, `@Id`, `@GeneratedValue`, `@Version` (optimistic lock), `@Query`, `@Join`, `@Where`. For JPA/Hibernate backend, use `jakarta.persistence.*` on entities instead.
- DO add `@Serdeable` (or configure serde) on entities exposed via JSON — Micronaut avoids reflection.

## Core model — DON'T
- DON'T omit `dialect` on SQL repositories. Queries are compiled per-dialect: `@JdbcRepository(dialect = Dialect.X)` / `@R2dbcRepository(dialect = Dialect.X)`. Wrong dialect → wrong SQL at build time.
- DON'T unit-test against H2 while production is Postgres by silently swapping. DO test against the real dialect via Testcontainers; if you must run H2 in tests, define a `@Replaces` subinterface pinned to `Dialect.H2`.
- DON'T expect Spring Data-style runtime query parsing. Everything derivable from the method name/return type is resolved at compile time.

## Backend selection — DO
- **JDBC** (blocking, lightweight, no JPA): feature `data-jdbc`, `io.micronaut.data:micronaut-data-jdbc` + a pool feature (`jdbc-hikari`). Use `@JdbcRepository`.
- **R2DBC** (non-blocking SQL): feature `data-r2dbc`, `io.micronaut.data:micronaut-data-r2dbc`. Use `@R2dbcRepository`. Repository methods return reactive types.
- **JPA/Hibernate**: feature `data-hibernate-jpa`. Use `@Repository`; full Hibernate/JPQL. Heaviest runtime.
- **Hibernate Reactive**: feature `data-hibernate-reactive` — reactive JPA on a Vert.x SQL client.
- **MongoDB / Azure Cosmos**: document backends via `micronaut-data-document-processor`.

## Datasources & transactions — DO
- DO configure datasources under `datasources.*` (JDBC) / `r2dbc.datasources.*` (R2DBC):
  ```yaml
  datasources:
    default:
      url: jdbc:postgresql://localhost:5432/app
      dialect: POSTGRES
      driver-class-name: org.postgresql.Driver
  ```
- DO scope a repo to a named datasource when multiple exist: `@JdbcRepository(dialect = ..., dataSource = "inventory")`; default is the primary datasource.
- DO drive blocking transactions with `@Transactional` (`jakarta.transaction.Transactional`, or `io.micronaut.transaction.annotation.Transactional` for datasource-qualified `@Transactional("inventory")`). Mark reads `@Transactional(readOnly = true)`.
- DON'T call `@Transactional` methods from within the same bean (self-invocation bypasses the AOP interceptor). Split into a collaborating bean.

## Reactive repositories — DO
- DO pick the repository interface by reactive runtime; methods return the matching type:
  - `ReactiveStreamsCrudRepository` → `Publisher`
  - `ReactorCrudRepository` / `ReactorPageableRepository` → `Mono`/`Flux` (needs `io.micronaut.reactor:micronaut-reactor`)
  - `RxJavaCrudRepository` → **RxJava 2** (`io.reactivex.*` types; module `io.micronaut.rxjava2:micronaut-rxjava2`). For RxJava 3 (`io.reactivex.rxjava3.*`) add `io.micronaut.rxjava3:micronaut-rxjava3` and return its `Single`/`Flowable` from a `ReactiveStreamsCrudRepository`.
  - `CoroutineCrudRepository` / `CoroutinePageableCrudRepository` → Kotlin `suspend` + `Flow`
  - `AsyncCrudRepository` → `CompletableFuture`
- DO use R2DBC (or Hibernate Reactive) as the backend for reactive repos so I/O is truly non-blocking. When the driver natively supports reactive types, the I/O thread pool is **not** used — the driver handles it.
- DO manage reactive transactions declaratively with `@Transactional` on a `@R2dbcRepository`, or programmatically:
  ```java
  r2dbcOperations.withTransaction(status -> /* Mono/Flux */ Mono.empty());
  ```

## Reactive — DON'T
- DON'T put a **JDBC** (`@JdbcRepository`) repo behind a reactive controller expecting non-blocking behavior — JDBC is blocking regardless of return type. Use R2DBC, or offload with `@ExecuteOn` (see virtual threads).
- DON'T call `.block()` / `.toBlocking()` on repository results in production request paths.
- DON'T mix reactive dependencies you didn't add: `Mono`/`Flux` need `micronaut-reactor` on the classpath.

## Blocking on virtual threads (framework 4+/JDK 21+) — DO
- DO offload blocking work (JDBC, blocking clients) off the Netty event loop with `@ExecuteOn`:
  ```java
  @Get @ExecuteOn(TaskExecutors.BLOCKING)
  public List<Book> list() { return repo.findAll(); }  // JDBC repo, safe here
  ```
- DO rely on the `blocking` executor auto-using **virtual threads** when the JDK supports them; otherwise Micronaut aliases `blocking` to the `io` pool. On JDK 19/20 it required `--enable-preview`; finalized in JDK 21.
- DON'T block the event loop directly. DON'T pin virtual threads inside `synchronized` blocks holding JDBC connections — prefer `ReentrantLock`. The experimental Netty `loom-carrier` flag (`micronaut.netty.event-loops.default.loom-carrier: true`) needs preview features + open JDK internals — avoid outside experiments.

## Sources
- Micronaut Data reference (5.x): https://micronaut-projects.github.io/micronaut-data/latest/guide/
- Micronaut Framework reference (5.1.x): https://docs.micronaut.io/latest/guide/
- Virtual Threads / thread pools: https://docs.micronaut.io/latest/guide/#virtualThreads
- Access a DB with Micronaut Data JDBC (guide): https://guides.micronaut.io/latest/micronaut-data-jdbc-repository.html
- Micronaut Data source (5.1.x branch): https://github.com/micronaut-projects/micronaut-data
- Micronaut Core source (5.1.x branch): https://github.com/micronaut-projects/micronaut-core
