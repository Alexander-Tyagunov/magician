# spring — Data access (JDBC, JPA, Data)

Framework-specifics only. Complements `lore/jdbc.md` and `lore/orm.md`; assumes Java lore in `lore/java/*`.

Version map (tie to Java baseline):
- **Spring Boot 3.x** → Spring Framework 6.x, **Java 17+**, Jakarta EE (`jakarta.persistence.*`, `jakarta.transaction.*`). Boot **3.2+** = Framework **6.1** (adds `JdbcClient`). Current line: Boot 4.x → Framework 7.x, Java 17+.
- **Spring Boot 2.x** → Framework 5.x, **Java 8+**, `javax.persistence.*`. No `JdbcClient`; use `JdbcTemplate`/`NamedParameterJdbcTemplate`.

## `@Transactional` semantics

DO
- Put `@Transactional` on the **service** layer, not repositories/controllers. Repos already run in their own tx.
- Use `@Transactional(readOnly = true)` on all read methods — enables Hibernate flush-mode `MANUAL` and driver read-only hints.
- Keep `PROPAGATION_REQUIRED` (default). Use `Propagation.REQUIRES_NEW` only for a truly independent unit (e.g. audit log that must commit even if caller rolls back).
- Remember: rollback fires on `RuntimeException`/`Error` only; **checked exceptions do NOT roll back** by default. Add `@Transactional(rollbackFor = Exception.class)` when you throw checked and want rollback.
- Boot autoconfigures the right `PlatformTransactionManager` (`JpaTransactionManager` with JPA, `DataSourceTransactionManager`/`JdbcTransactionManager` for plain JDBC). Don't declare one manually unless multi-datasource.

DON'T
- **Self-invocation trap:** calling a `@Transactional` method from another method of the *same bean* bypasses the proxy — no transaction/new propagation applies. Fix: move the method to another bean, self-inject the proxy, or switch to AspectJ weaving mode.
- Don't annotate `private` methods — never advised. (Since 6.0, `protected`/package methods work only with **class-based (CGLIB) proxies**; interface proxies still need `public`.)
- Don't expect `isolation`/`timeout`/`readOnly` to apply under `NESTED`/`SUPPORTS`/`MANDATORY` etc. — they only take effect for `REQUIRED`/`REQUIRES_NEW`.
- Don't do slow I/O (HTTP, external calls) inside a tx — holds the DB connection.

```java
@Service
public class OrderService {
  @Transactional(readOnly = true)
  public Order find(Long id) { ... }

  @Transactional(rollbackFor = PaymentException.class)
  public void place(Order o) throws PaymentException { ... }
}
```
Global switch (Framework 6.2+) for consistent rollback incl. checked: `@EnableTransactionManagement(rollbackOn = ALL_EXCEPTIONS)`.

## Spring Data JPA repositories

DO
- Extend `JpaRepository<T, ID>` (adds `CrudRepository` + `PagingAndSortingRepository` + flush/batch). Prefer derived queries for simple cases: `findByEmailAndActiveTrue(...)`.
- Use `@Query` (JPQL) for anything non-trivial; it takes precedence over `@NamedQuery`. Add `@Param` for named binds (omit-able on Framework 7 / Boot 4 if compiled with `-parameters`).
- Use `@Modifying` on bulk update/delete `@Query`; set `clearAutomatically = true` (and consider `flushAutomatically`) so the persistence context doesn't serve stale entities after a bulk write.
- Return `Optional<T>` for single lookups.

DON'T
- Don't hand-write CRUD/boilerplate DAOs when a derived method suffices.
- Don't rely on derived `deleteByX(...)` for volume — it **loads then deletes one-by-one** (fires lifecycle callbacks). Use `@Modifying @Query("delete from ...")` for a single bulk statement (skips callbacks).
- Don't put function calls in `Sort.by("LENGTH(name)")` — throws; use `JpaSort.unsafe(...)`.

## N+1 avoidance

DO
- Default associations to **`FetchType.LAZY`** (`@OneToMany` is lazy already; make `@ManyToOne`/`@OneToOne` explicit `LAZY`).
- Fetch the graph you need in one query: `@Query("select o from Order o join fetch o.items where ...")`, or **`@EntityGraph(attributePaths = {"items"})`** on the repo method (declarative, works with derived + paged methods).
- Detect N+1 early: log SQL and enable `spring.jpa.properties.hibernate.generate_statistics=true` in tests.

DON'T
- Don't set `FetchType.EAGER` to "fix" N+1 — it just moves the problem and breaks pagination.
- Don't `join fetch` a collection **and** paginate in the same query — Hibernate pages in memory (warns/OOM). Paginate on the root, fetch collections via `@EntityGraph` or a second query (`@BatchSize` / `hibernate.default_batch_fetch_size`).

```java
public interface OrderRepo extends JpaRepository<Order, Long> {
  @EntityGraph(attributePaths = "items")
  List<Order> findByStatus(Status s);
}
```

## Projections

DO
- Use **interface projections** (closed) to select only needed columns — Spring generates a narrow query:
  ```java
  interface NameOnly { String getFirstname(); String getLastname(); }
  List<NameOnly> findByActiveTrue();
  ```
- Use **DTO/record class projections** via constructor expression when shaping: `@Query("select new com.x.NameDto(u.firstname, u.lastname) from User u")`, or a record as the return type.

DON'T
- Don't fetch full entities just to read two fields — wastes SQL and hydrates the persistence context.
- Avoid **open** projections (SpEL `@Value("#{...}")` getters): they force full-entity fetch, defeating the point.

## Pagination

DO
- Accept `Pageable` (`PageRequest.of(page, size, Sort.by(...))`). Return **`Page<T>`** when you need total count, **`Slice<T>`** when you only need "has next" (skips the count query). Use `Window<T>` + keyset (`ScrollPosition.keyset()`) for deep/large scans.
- For native paged `@Query`, supply an explicit `countQuery` (or add JSqlParser for auto-derivation).

DON'T
- Don't return `Page` on hot paths that don't display totals — the extra `count(*)` is wasted.
- Don't offset-paginate huge tables — deep offsets are O(n); prefer keyset scrolling.

## JdbcTemplate / JdbcClient (Boot 3.2+)

DO
- **New code on Boot 3.2+ / Framework 6.1+:** prefer **`JdbcClient`** — unified fluent facade over positional + named params. Boot autoconfigures the bean (`JdbcClientAutoConfiguration`, needs a `NamedParameterJdbcTemplate`); just inject it.
  ```java
  Optional<Actor> a = jdbcClient
      .sql("select * from actor where id = :id")
      .param("id", id)
      .query(Actor.class).optional();     // .single() / .list() / .update()
  ```
- On Boot 2.x (or existing code): `NamedParameterJdbcTemplate` (named `:params`) or `JdbcTemplate` (positional `?`). Both are autoconfigured and thread-safe.
- Use plain JDBC / `JdbcClient` when you want explicit SQL, complex reporting joins, bulk writes, or to avoid ORM overhead.

DON'T
- Don't reach for `JdbcTemplate.queryForObject` when it can return 0 rows — throws `EmptyResultDataAccessException`; use `JdbcClient...optional()`.
- Don't use `JdbcClient` for batch inserts / stored procs — still need `SimpleJdbcInsert`/`SimpleJdbcCall`/`JdbcTemplate.batchUpdate`.

## Spring Data JPA vs plain JDBC/jOOQ

- **Spring Data JPA** — domain-centric CRUD, entity graphs, derived queries, dirty-checking. Best for aggregate-oriented models.
- **JdbcClient / Spring Data JDBC** — no lazy loading / no dirty tracking; predictable SQL, lighter. Good for simple tables, CQRS read side, high-throughput.
- **jOOQ** — type-safe SQL DSL, compile-checked against schema. Best for complex/analytical SQL where JPQL is awkward. Combine: JPA for writes, jOOQ/`JdbcClient` for reporting reads.

## Sources
- https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html
- https://docs.spring.io/spring-framework/reference/data-access/jdbc/core.html
- https://docs.spring.io/spring-data/jpa/reference/jpa/query-methods.html
- https://docs.spring.io/spring-boot/3.5/reference/data/sql.html
- https://docs.spring.io/spring-boot/system-requirements.html
- https://docs.spring.io/spring-boot/index.html
