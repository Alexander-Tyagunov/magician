# quarkus — REST & Panache (data)

Framework-specifics only. Java-language lore lives in `lore/java/*`. Complements ORM lore.

Version map (verify against `pom.xml` / build):
- **Quarkus 3.x** → `jakarta.*` namespace (Jakarta EE 10), Java 17+ baseline. Default REST stack is **Quarkus REST** (reactive core on Vert.x).
- **Quarkus 2.x** → `javax.*` namespace, Java 8/11. RESTEasy Reactive became the *default* in 2.8; RESTEasy Classic was default before that.
- **Rename**: `quarkus-resteasy-reactive*` → `quarkus-rest*` in **Quarkus 3.9**. Same runtime; only the extension/artifact names changed. Legacy blocking stack = `quarkus-resteasy` (RESTEasy Classic).

## REST extensions & JSON

DO pick the extension for the version:
- 3.9+: `quarkus-rest`; JSON via `quarkus-rest-jackson` or `quarkus-rest-jsonb`; also `quarkus-rest-jaxb` (XML), `quarkus-rest-client`.
- 3.0–3.8: `quarkus-resteasy-reactive` + `quarkus-resteasy-reactive-jackson`.
- Legacy/blocking-only: `quarkus-resteasy` + `quarkus-resteasy-jackson`.

DO use standard Jakarta REST annotations: `@Path`, `@GET/@POST/@PUT/@DELETE/@PATCH`, `@Produces`, `@Consumes`, `@PathParam`, `@QueryParam`. Quarkus shortcuts infer the name from the parameter: `@RestPath`, `@RestQuery`, `@RestHeader`, `@RestForm`.

DON'T mix RESTEasy Classic and Quarkus REST providers/extensions in one app — they are separate stacks and conflict.

## Execution model (Quarkus REST)

Quarkus REST runs on the Vert.x event loop. **Return type picks the thread**:
- Reactive types (`Uni`, `Multi`, `CompletionStage`) → run on the **IO/event-loop** thread. Never block them.
- Everything else → dispatched to a **worker** thread (safe to block).

DO annotate `@Blocking` / `@NonBlocking` to override the default. A method annotated `@Transactional` is treated as blocking automatically.
DO prefer `@RunOnVirtualThread` (needs `quarkus-virtual-threads`, Java 21) for blocking code that you want cheap concurrency for — don't combine it with reactive return types.
DON'T do JDBC/JPA (blocking) work on an event-loop thread. If a method returns a plain type or is `@Blocking`, you're safe; if it returns `Uni`/`Multi`, you must use reactive Panache.

## Responses & errors

DO return `org.jboss.resteasy.reactive.RestResponse<T>` over raw `jakarta.ws.rs.core.Response` — it's strongly typed, so Quarkus registers the type for reflection at build time (no `@RegisterForReflection` needed for native).

DO map exceptions with `@ServerExceptionMapper` (method-level, no `@Provider` boilerplate):
```java
class Mappers {
  @ServerExceptionMapper
  RestResponse<String> notFound(EntityNotFoundException x) {
    return RestResponse.status(Response.Status.NOT_FOUND, x.getMessage());
  }
}
```
Standard `jakarta.ws.rs.ext.ExceptionMapper` + `@Provider` still works.

## Panache — extension & datasource

DO add `quarkus-hibernate-orm-panache` (blocking) **plus** a JDBC driver: `quarkus-jdbc-postgresql` / `-h2` / `-mariadb` / `-mssql` / `-oracle`. `quarkus-agroal` (pooling) is pulled in automatically for built-in drivers.

Config (`application.properties`):
```properties
quarkus.datasource.db-kind=postgresql
quarkus.datasource.username=app
quarkus.datasource.password=secret
quarkus.datasource.jdbc.url=jdbc:postgresql://localhost:5432/app
quarkus.datasource.jdbc.max-size=16
quarkus.hibernate-orm.schema-management.strategy=none   # 3.x: none|create|drop-and-create|update|validate
```
- JDBC props are under `jdbc.*`; reactive props under `reactive.*`.
- `sql-load-script` defaults to `import.sql` (dev/test only). Each statement needs a trailing `;`.
- DON'T use `drop-and-create`/`update` in prod — use `none` + a migration tool (Flyway/Liquibase).
- Older docs/2.x use `quarkus.hibernate-orm.database.generation` (same values); recent 3.x adds `schema-management.strategy`. Match the codebase.

## Panache — active record vs repository

Active record — entity extends `PanacheEntity` (auto `Long id`) and holds public fields; Panache rewrites field access to getters/setters at build time:
```java
@Entity
public class Person extends PanacheEntity {   // io.quarkus.hibernate.orm.panache
  public String name;
  public LocalDate birth;
  public static List<Person> findByName(String n) { return list("name", n); }
}
```
Repository — inject a bean, keep entities as plain JPA:
```java
@ApplicationScoped
public class PersonRepo implements PanacheRepository<Person> { }
```

DO use `PanacheEntityBase` + your own `@Id` for a custom/composite id (repo: `PanacheRepositoryBase<Person, UUID>`).
DON'T add public getters/setters to `PanacheEntity` fields expecting they run — access is rewritten; put logic in explicit accessors only when you need it, and Panache respects them.
DON'T give one entity two persistence units — a Panache entity binds to exactly one.
DO add an empty `META-INF/beans.xml` for entities in an external jar so Quarkus enhances them.

## Panache — queries

Simplified HQL: the query is the part **after** `from Entity where` — a bare field expands to a `where` clause.
```java
Person.find("name", "Stef");
Person.find("name = ?1 and status = ?2", name, ACTIVE);
Person.find("#Person.byStatus", Map.of("status", ACTIVE)); // named query, '#' prefix
Person.list("order by name");
long n = Person.count("status", ACTIVE);
Person.delete("status", INACTIVE);
Person.update("name = ?1 where id = ?2", newName, id); // bulk update, needs @Transactional
```
- Params are 1-based positional (`?1`) or named via `Map`.
- Sorting: `Person.list("status", Sort.by("name").and("birth"), ACTIVE)`. Column names are escaped (HQL-injection safe); `disableEscaping()` only for HQL functions.
- Paging on `PanacheQuery`: `find(...).page(Page.of(0, 25)).list()`, `.nextPage()`, `.pageCount()`. `range(0,24)` is an alternative — don't mix range and page.
- Projection to a DTO/record: `find(...).project(PersonName.class)`. Projection class needs a matching constructor and `<maven.compiler.parameters>true</maven.compiler.parameters>`; records (Java 17+) fit well.

DO use `stream()`/`Multi` variants inside a transaction and close them (try-with-resources) — they hold the `ResultSet` open.

## Transactions (blocking)

DO annotate service or REST methods that write with `jakarta.transaction.Transactional`. Recommended boundary = the REST endpoint or a service method.
```java
@POST @Transactional
public RestResponse<Person> create(Person p) { p.persist(); return RestResponse.status(CREATED, p); }
```
DON'T call `persist`/`delete`/bulk `update` outside a transaction — it throws.
DO use `persistAndFlush()` / `flush()` when you must surface a `PersistenceException` early (e.g. before returning).
DO pass `LockModeType` for pessimistic locking: `Person.findById(id, LockModeType.PESSIMISTIC_WRITE)` inside `@Transactional`.

## Reactive Panache

For a fully reactive app (`Uni`/`Multi` endpoints) use **reactive** Panache — never blocking Panache on the event loop.

DO add `quarkus-hibernate-reactive-panache` + a **reactive** driver: `quarkus-reactive-pg-client` / `-mysql-client` / `-mssql-client` / `-oracle-client` / `-db2-client`. Set `quarkus.datasource.reactive.url`. (There is no reactive H2.)
DO import from `io.quarkus.hibernate.reactive.panache.*`; every operation returns a Mutiny `Uni<T>` / `Multi<T>`.
DO replace `@Transactional` with `@WithTransaction` (or `Panache.withTransaction(...)`); use `@WithSession` / `Panache.withSession(...)` for read-only. All from `io.quarkus.hibernate.reactive.panache.common`.
```java
@POST @WithTransaction
public Uni<Person> create(Person p) { return p.persist(); }
```
DON'T mix `@Transactional` with `@WithTransaction`/`@WithSession` in the same reactive pipeline — throws `UnsupportedOperationException`.
DON'T touch a reactive Panache entity from a blocking thread — operations must run on the Vert.x event loop.

## Testing & mocking

DO mock active-record statics with `quarkus-panache-mock` (`PanacheMock.mock(Person.class)`); mock repositories with `@InjectMock` (`quarkus-junit-mockito`). Reactive tests use `quarkus-test-vertx`.

## Sources

- https://quarkus.io/guides/rest
- https://quarkus.io/guides/rest-json
- https://quarkus.io/guides/resteasy (RESTEasy Classic)
- https://quarkus.io/guides/resteasy-client
- https://quarkus.io/guides/hibernate-orm-panache
- https://quarkus.io/guides/hibernate-reactive-panache
- https://quarkus.io/guides/hibernate-orm
- https://quarkus.io/guides/datasource
- https://quarkus.io/guides/virtual-threads
- https://github.com/quarkusio/quarkus/wiki/Migration-Guide-3.9 (RESTEasy Reactive → Quarkus REST rename)
- https://github.com/quarkusio/quarkus
