# quarkus — deep dive

> On-demand companion to `lore/quarkus.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Core, ArC (CDI) & build-time](#core-and-arc) · [Reactive & Mutiny](#reactive-and-mutiny) · [REST & Panache (data)](#rest-and-panache) · [Native, dev services & testing](#native-dev-and-testing)

## Core, ArC (CDI) & build-time <a id="core-and-arc"></a>

Framework lore only. Java-language rules live in `lore/deep/java.md`. Quarkus does as much work as possible at **build time** (augmentation), not runtime — that is the whole point. Fidelity: annotations/config keys below are verified against current docs (3.x).

### Version baseline — read first

DO know which major you target; it dictates the namespace and JDK.
- **Quarkus 3.x** (current; 3.20 & 3.15 are LTS): **Java 17+** (17/21/25), **`jakarta.*`** namespace (`jakarta.inject.Inject`, `jakarta.enterprise.context.*`, `jakarta.ws.rs.*`). CDI is **Jakarta CDI 4.1 (Lite)**.
- **Quarkus 2.x** (legacy): **Java 11+** (Java 8 only in early 2.x), **`javax.*`** namespace, CDI Lite (older).
- DON'T mix namespaces. Migrating 2→3 = `javax.*` → `jakarta.*` across the whole app. Use the OpenRewrite recipe / `quarkus update`; don't hand-edit at scale.

DON'T assume config keys are stable across majors. Example (verified): **`quarkus.package.type` (2.x) → `quarkus.package.jar.type` (3.x)**. Check the current property name before writing it.

### Build-time augmentation philosophy

DO push work to build time. Benefits: fast startup, low RSS, dead-code elimination, and GraalVM native-image compatibility. Three boot phases:
1. **Augmentation** (build) — build steps read the **Jandex** annotation index; must NOT load application classes. Output is recorded bytecode.
2. **Static Init** (`@Record(STATIC_INIT)`) — runs in a static init method; for native it runs *at build* and state is serialized into the binary. No ports, no threads, no runtime config reads here.
3. **Runtime Init** (`@Record(RUNTIME_INIT)`) — runs from `main`; the only phase allowed to open ports / read runtime config.

DON'T do reflection, classpath scanning, or config parsing at runtime if an extension can do it at build. DON'T use `System.getProperty`/`System.getenv` for config (bypasses recording).

### ArC (CDI) — DO

- Annotate beans: `@ApplicationScoped` (default for singletons — normal-scoped, lazy, proxied), `@Singleton` (pseudo-scope, eager-ish, no proxy), `@RequestScoped`, `@Dependent`. `@SessionScoped` needs the Undertow extension.
- Inject with `@Inject` (field/constructor). `@Inject` is **optional** on a sole constructor and on fields that already carry a qualifier.
- Prefer **constructor injection** for testability. No no-arg constructor needed for normal-scoped beans.
- Producers: `@Produces` (skippable if the method has a scope/qualifier/stereotype). Observers: `@Observes`.
- String qualifier: prefer `@io.smallrye.common.annotation.Identifier("x")` over `@Named`.
- Eager startup work: `@io.quarkus.runtime.Startup` on a bean/method.
- Conditional wiring is **build-time**: `@io.quarkus.arc.DefaultBean`, `@IfBuildProfile`/`@UnlessBuildProfile`, `@IfBuildProperty`/`@UnlessBuildProperty`. Runtime-conditional lookup: `@LookupIfProperty`/`@LookupUnlessProperty`.
- Inject all implementations: `@All List<MyIface> beans`.

### ArC — DON'T

- DON'T expect CDI **Full**: no portable extensions, no `InterceptionFactory`, no decorators-as-in-full. ArC is CDI **Lite** + extras.
- DON'T rely on a bean surviving if nothing references it — ArC **removes unused beans** by default. If accessed only via `CDI.current()`/reflection, mark `@io.quarkus.arc.Unremovable` or tune `quarkus.arc.remove-unused-beans`.
- DON'T annotate a class you expect to be a bean without a **bean-defining annotation** — simplified discovery (`annotated` mode) skips it (producers/observers on unannotated classes are still picked up as `@Dependent`).
- DON'T reach for runtime config inside `@IfBuildProperty` — those resolve at build time only.

### Config — MicroProfile Config / SmallRye — DO

- Put config in `src/main/resources/application.properties` (tests: `src/test/resources/...`). YAML needs the `quarkus-config-yaml` extension.
- Inject scalars: `@org.eclipse.microprofile.config.inject.ConfigProperty(name="greeting.message", defaultValue="hi") String msg;` (`@Inject` optional). Use `Optional<T>` for truly optional values.
- Prefer type-safe groups: `@io.smallrye.config.ConfigMapping(prefix="server")` on an **interface**; method `sslPort()` maps to `server.ssl-port` (kebab-case).
- Source precedence (high→low): system props (400) > env vars (300) > `.env` (295) > `$PWD/config/application.properties` (260) > classpath `application.properties` (250).
- Env-var form: `foo.bar` ↔ `FOO_BAR` (non-alphanumeric → `_`, uppercased).
- Profiles: prefix keys with `%dev.`, `%test.`, `%prod.` or use `application-{profile}.properties`. `dev` = `quarkus:dev`, `test` = tests, `prod` = default. Activate custom via `quarkus.profile`.

### Config — DON'T

- DON'T use the reserved `quarkus.` prefix for app properties.
- DON'T expect a **build-time-fixed** property (lock icon in docs, e.g. most `quarkus.arc.*`, datasource driver) to change at runtime — it needs a rebuild. Runtime override of a build-fixed key triggers a mismatch warning (`quarkus.config.build-time-mismatch-at-runtime=warn|fail`).

### Dev mode & build — DO

- Live coding: `quarkus dev` or `./mvnw quarkus:dev` (Gradle: `./gradlew quarkusDev`). Recompiles + redeploys on next request/refresh. Debug on `5005` (no suspend) by default. Dev UI at `/q/dev`.
- Continuous testing runs in the dev console; **Dev Services** auto-start backing containers (DB, Kafka, …) in dev/test — no local config needed.
- Add extensions: `quarkus extension add hibernate-orm-panache` or `./mvnw quarkus:add-extension -Dextensions=...`. List with `quarkus:list-extensions`.
- Build: `quarkus build` / `./mvnw install`. Default package is **fast-jar** → `target/quarkus-app/`, run `java -jar target/quarkus-app/quarkus-run.jar` (NOT a single jar). Uber-jar: `quarkus.package.jar.type=uber-jar`.
- Native: `quarkus build --native` or `./mvnw install -Dnative` (`-Dquarkus.native.container-build=true` for a containerized GraalVM build). Native tests: `./mvnw verify -Dnative`.

### Dev mode & build — DON'T

- DON'T ship the fast-jar `runner`-only jar and expect it standalone — the whole `quarkus-app/` dir (lib, quarkus, app) is required.
- DON'T register beans/resources for reflection ad hoc in native — use an extension build step or `@io.quarkus.runtime.annotations.RegisterForReflection` on classes accessed reflectively.
- DON'T do heavy init in constructors for native; prefer `@Record(RUNTIME_INIT)` recorders / `@Startup`.

### Reactive core (context)

Quarkus core is reactive: engine is **Eclipse Vert.x + Netty**; async API is **Mutiny** (`io.smallrye.mutiny.Uni` = 0/1 item, `Multi` = stream). Blocking endpoints run on worker threads; reactive ones on the event loop — don't block the event loop.

### Sources

- https://quarkus.io/guides/ (guide index; current version 3.37.x)
- https://quarkus.io/guides/cdi-reference (ArC / Jakarta CDI 4.1 Lite)
- https://quarkus.io/guides/cdi (CDI intro)
- https://quarkus.io/guides/config-reference (SmallRye / MicroProfile Config, profiles, sources)
- https://quarkus.io/guides/config-mappings (@ConfigMapping)
- https://quarkus.io/guides/maven-tooling (dev mode, build, packaging, native)
- https://quarkus.io/guides/writing-extensions (build steps, recorders, boot phases)
- https://quarkus.io/guides/quarkus-reactive-architecture (Vert.x, Mutiny)
- https://github.com/quarkusio/quarkus

## Reactive & Mutiny <a id="reactive-and-mutiny"></a>

Framework-specifics only. Java-language lore lives in `lore/deep/java.md`.

Quarkus reactive core = **Eclipse Vert.x + Netty**. The reactive API is **Mutiny**
(`io.smallrye.mutiny`, `Uni`/`Multi`) — **not** Reactor, **not** RxJava. Two execution
lanes coexist in one app: **event-loop (I/O) threads** and the **worker thread pool**.
Quarkus REST picks the lane per method via a "best guess" on the return type; annotations
override it.

### Version baseline (adapt to what the project runs)

DO map guidance to the major:
- **Quarkus 3.x** — `jakarta.*` namespace (Jakarta EE 10), Hibernate ORM 6, MicroProfile 6.
  Java 11 minimum, **17 recommended**. Virtual threads need **Java 21+**.
- **Quarkus 2.x** — `javax.*` namespace, pre-Jakarta. Same Java 11 floor. No `@RunOnVirtualThread`.

DO know the **3.9 "big rename"** (March 2024): RESTEasy Reactive → **Quarkus REST**.
- 3.9+: `quarkus-rest`, `quarkus-rest-jackson`, `quarkus-rest-jsonb`.
- 2.x / pre-3.9: `quarkus-resteasy-reactive`, `quarkus-resteasy-reactive-jackson`.
- DON'T mix `quarkus-rest*` and `quarkus-resteasy*` (classic) in one build — duplicate-provider errors.
- DON'T confuse with legacy blocking `quarkus-resteasy` (RESTEasy Classic) — different stack.

### The golden rule

DON'T block an I/O (event-loop) thread. There are only a few; blocking one stalls many
requests. No JDBC, no `Thread.sleep`, no `.await()`, no `toIterable()` on the event loop —
Mutiny's `await`/`toIterable` throw if called on an I/O thread.

### Choosing the model

DO pick per endpoint, not per app:
- **Reactive (`Uni`/`Multi`)** — high concurrency, I/O-bound, streaming, end-to-end
  non-blocking stack (reactive SQL client, reactive REST client). Runs on the event loop.
- **Imperative on virtual threads (`@RunOnVirtualThread`)** — I/O-bound but you want plain
  blocking-style code; needs Java 21+. Best when reactive composition adds no value.
- **Imperative on worker thread** — default for blocking libs (JDBC, JPA); CPU-bound work.

DON'T use virtual threads for CPU-bound work — no benefit, adds scheduling cost.
DON'T rewrite blocking code to reactive just for style; virtual threads or the worker pool
are fine when the win is only ergonomic.

### Thread selection & @Blocking

Quarkus REST runs a method on the **I/O thread** (non-blocking) when it returns:
`io.smallrye.mutiny.Uni`, `Multi`, `java.util.concurrent.CompletionStage`,
`org.reactivestreams.Publisher`, or a Kotlin `suspend` fn. Otherwise → **worker thread**.

Override with `io.smallrye.common.annotation.@Blocking` / `@NonBlocking` (method, class, or
`jakarta.ws.rs.core.Application` level):

```java
@GET @Path("/x")
@Blocking                          // force worker thread even though it returns Uni
public Uni<Foo> x() { ... }
```

DO remember `jakarta.transaction.@Transactional` methods are treated as **blocking** (JTA is
blocking) unless you override. DON'T annotate a method `@NonBlocking` and then call JDBC in it.

### @RunOnVirtualThread (Quarkus 3, Java 21+)

`io.smallrye.common.annotation.@RunOnVirtualThread` — each invocation runs on a fresh virtual
thread. With Quarkus REST it applies **only to `@Blocking` or blocking-by-signature** endpoints.

```java
@GET @Path("/v")
@RunOnVirtualThread                 // implies worker/blocking semantics; write plain blocking code
public Fortune v() {
    var list = repo.findAllAsyncAndAwait();   // andAwait()/await().atMost() are VT-friendly
    return pickOne(list);
}
```

DON'T guard shared state with `synchronized` on Java 21–23 — it **pins** the carrier thread.
Use `java.util.concurrent.locks.ReentrantLock`. Java 24+ (JEP 491) removes `synchronized`
pinning; native downcalls can still pin.
DON'T use the PostgreSQL JDBC driver **< 42.6.0** on virtual threads (pins heavily; 42.6.0+
switched to reentrant locks).
DO mind `ThreadLocal` object pools (Jackson, Netty) — with many short-lived VTs they blow up
memory. DO note thread-locals are **not** propagated into VT methods (duplicated context is).
DO detect pinning in tests with the `junit-virtual-threads` extension (`@ShouldNotPin`,
`@ShouldPin(atMost=n)`, `@VirtualThreadUnit`).

### Mutiny essentials

- `Uni<T>` — 0..1 item or failure. **Does not** implement Reactive Streams `Publisher`.
- `Multi<T>` — 0..n items, then completion or failure. **Implements** `Publisher`, enforces
  backpressure.
- Event-driven grammar: `on{Item,Failure,Completion,...}().action()`.

```java
uni.onItem().transform(x -> ...)            // sync map;    shortcut: .map()
   .onItem().transformToUni(x -> callDb(x)) // async chain; shortcut: .chain()/.flatMap()
   .onFailure().recoverWithItem(fallback)
   .onFailure().retry().atMost(3);
```

DO use `.invoke()` for sync side-effects, `.call()` for async side-effects (both pass the item
through unchanged). DON'T subscribe manually in endpoints — returning `Uni`/`Multi` lets
Quarkus REST subscribe; a `Uni` with no subscriber does nothing.
DO stream large results as `Multi` (backpressure); DON'T hold a DB connection open streaming
rows straight to the client.
DON'T pull in Reactor/RxJava operators — Mutiny is the native API; convert only at true library
boundaries (Mutiny ships Reactive Streams converters).

### Reactive data & config

DO use reactive clients end-to-end to stay off the worker pool:
- Hibernate Reactive + Panache: `quarkus-hibernate-reactive-panache`;
  `io.quarkus.hibernate.reactive.panache.PanacheEntity` (import the **reactive** variant),
  methods return `Uni`; wrap writes in `Panache.withTransaction(...)`.
- Reactive SQL: `quarkus-reactive-pg-client` / `-mysql-client`, config
  `quarkus.datasource.reactive.url`, `quarkus.datasource.db-kind`.

DON'T mix a blocking JPA `EntityManager` into a reactive (`Uni`-returning) path.

Config keys: `quarkus.virtual-threads.name-prefix`,
`quarkus.micrometer.binder.virtual-threads.enabled`.

Kotlin: coroutines (`suspend`) are a first-class alternative to Mutiny — treated as
non-blocking by Quarkus REST.

### Sources

- https://quarkus.io/guides/getting-started-reactive
- https://quarkus.io/guides/quarkus-reactive-architecture
- https://quarkus.io/guides/mutiny-primer
- https://quarkus.io/guides/rest
- https://quarkus.io/guides/virtual-threads
- https://quarkus.io/blog/road-to-quarkus-3/
- https://github.com/quarkusio/quarkusio.github.io/blob/main/_posts/2024-03-21-the-big-rename.adoc
- https://github.com/quarkusio/quarkus

## REST & Panache (data) <a id="rest-and-panache"></a>

Framework-specifics only. Java-language lore lives in `lore/deep/java.md`. Complements ORM lore.

Version map (verify against `pom.xml` / build):
- **Quarkus 3.x** → `jakarta.*` namespace (Jakarta EE 10), Java 17+ baseline. Default REST stack is **Quarkus REST** (reactive core on Vert.x).
- **Quarkus 2.x** → `javax.*` namespace, Java 8/11. RESTEasy Reactive became the *default* in 2.8; RESTEasy Classic was default before that.
- **Rename**: `quarkus-resteasy-reactive*` → `quarkus-rest*` in **Quarkus 3.9**. Same runtime; only the extension/artifact names changed. Legacy blocking stack = `quarkus-resteasy` (RESTEasy Classic).

### REST extensions & JSON

DO pick the extension for the version:
- 3.9+: `quarkus-rest`; JSON via `quarkus-rest-jackson` or `quarkus-rest-jsonb`; also `quarkus-rest-jaxb` (XML), `quarkus-rest-client`.
- 3.0–3.8: `quarkus-resteasy-reactive` + `quarkus-resteasy-reactive-jackson`.
- Legacy/blocking-only: `quarkus-resteasy` + `quarkus-resteasy-jackson`.

DO use standard Jakarta REST annotations: `@Path`, `@GET/@POST/@PUT/@DELETE/@PATCH`, `@Produces`, `@Consumes`, `@PathParam`, `@QueryParam`. Quarkus shortcuts infer the name from the parameter: `@RestPath`, `@RestQuery`, `@RestHeader`, `@RestForm`.

DON'T mix RESTEasy Classic and Quarkus REST providers/extensions in one app — they are separate stacks and conflict.

### Execution model (Quarkus REST)

Quarkus REST runs on the Vert.x event loop. **Return type picks the thread**:
- Reactive types (`Uni`, `Multi`, `CompletionStage`) → run on the **IO/event-loop** thread. Never block them.
- Everything else → dispatched to a **worker** thread (safe to block).

DO annotate `@Blocking` / `@NonBlocking` to override the default. A method annotated `@Transactional` is treated as blocking automatically.
DO prefer `@RunOnVirtualThread` (needs `quarkus-virtual-threads`, Java 21) for blocking code that you want cheap concurrency for — don't combine it with reactive return types.
DON'T do JDBC/JPA (blocking) work on an event-loop thread. If a method returns a plain type or is `@Blocking`, you're safe; if it returns `Uni`/`Multi`, you must use reactive Panache.

### Responses & errors

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

### Panache — extension & datasource

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

### Panache — active record vs repository

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

### Panache — queries

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

### Transactions (blocking)

DO annotate service or REST methods that write with `jakarta.transaction.Transactional`. Recommended boundary = the REST endpoint or a service method.
```java
@POST @Transactional
public RestResponse<Person> create(Person p) { p.persist(); return RestResponse.status(CREATED, p); }
```
DON'T call `persist`/`delete`/bulk `update` outside a transaction — it throws.
DO use `persistAndFlush()` / `flush()` when you must surface a `PersistenceException` early (e.g. before returning).
DO pass `LockModeType` for pessimistic locking: `Person.findById(id, LockModeType.PESSIMISTIC_WRITE)` inside `@Transactional`.

### Reactive Panache

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

### Testing & mocking

DO mock active-record statics with `quarkus-panache-mock` (`PanacheMock.mock(Person.class)`); mock repositories with `@InjectMock` (`quarkus-junit-mockito`). Reactive tests use `quarkus-test-vertx`.

### Sources

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

## Native, dev services & testing <a id="native-dev-and-testing"></a>

Framework-specific lore. Java-language lore lives in `lore/deep/java.md`.

**Version map (verify against project's Quarkus version):**
- **Quarkus 3.x** — Java 17+, `jakarta.*`. Native needs **GraalVM for JDK 21 / Mandrel 23.1** (`quarkus.native.enabled=true`).
- **Quarkus 2.x** — Java 11+/17, `javax.*`. Native uses **GraalVM/Mandrel 22.3** (`quarkus.package.type=native`).
- `-Dnative` works in BOTH; the Maven `native` profile maps it to the correct property per version. Prefer the profile.

### Native image build

DO
- Add a `native` Maven profile activated by the `native` property, setting `skipITs=false` + the version-correct native property (`quarkus.native.enabled=true` for 3.x; `quarkus.package.type=native` for 2.x).
- Build: `./mvnw install -Dnative` (Gradle: `./gradlew build -Dquarkus.native.enabled=true`). Output: `target/*-runner`.
- No local GraalVM → container build: `-Dnative -Dquarkus.native.container-build=true`; runtime via `-Dquarkus.native.container-runtime=docker|podman`. On macOS/Windows this is the norm (Mandrel ships no macOS/amd64 native-image).
- Pin the builder image for reproducibility: `-Dquarkus.native.builder-image=quay.io/quarkus/ubi9-quarkus-mandrel-builder-image:jdk-21`.
- One-shot container image (needs a `quarkus-container-image-*` extension): add `-Dquarkus.container-image.build=true` to the package command.
- Extra `native-image` args via `quarkus.native.additional-build-args` (escape commas): `--initialize-at-run-time=com.acme.Foo\\,org.acme.Bar`.

DON'T
- Don't assume `quarkus.native.enabled` exists in 2.x — it's `quarkus.package.type=native`.
- Don't run a Quarkus 3.19+ native binary on a UBI 8 base image — builder is UBI 9-based (glibc mismatch). Match base to builder, or revert to the `ubi-quarkus-mandrel-builder-image:jdk-21` builder.

### Reflection & resources (native)

Native-image is closed-world: reflection, dynamic proxies, and classpath resources not reachable statically are dropped unless registered.

DO
- Register your own class: `@RegisterForReflection` on it.
- Register third-party classes you can't annotate via a host holder (host is NOT registered, only the targets): `@RegisterForReflection(targets = {User.class, UserImpl.class})` on an empty config class.
- Include runtime-loaded resources: `quarkus.native.resources.includes=foo/**,bar/**/*.txt` (glob).
- Dynamic proxies: `@RegisterForProxy`. Resource bundles: `@RegisterResourceBundle`.
- Hand-rolled GraalVM config → `reflect-config.json` / `resource-config.json` under `src/main/resources/META-INF/native-image/<group-id>/<artifact-id>/`.

DON'T
- Don't put your own `resource-config.json` directly under `.../META-INF/native-image/` (no group/artifact subdir) — Quarkus overwrites it.
- Don't rely on Jackson/JSON-B reflectively binding DTOs in native without registration — symptoms: "No default constructor found" or empty JSON body. Register the DTOs.
- Nested classes ARE registered by default; only set `ignoreNested` if you know they're unused.

### Dev Services (auto Testcontainers)

Dev Services auto-provision unconfigured backing services in **dev and test** mode — typically via Testcontainers. Lives in `deployment` modules only; zero prod impact.

DO
- Rely on it: add the extension (`quarkus-jdbc-postgresql`, `quarkus-messaging-kafka`, `quarkus-redis-client`, `quarkus-mongodb-client`, `quarkus-elasticsearch`, OIDC/Keycloak, etc.) and leave connection config unset in dev/test — the container starts and wires automatically.
- Keep prod config under a profile so it doesn't suppress Dev Services in dev/test: `%prod.quarkus.datasource.jdbc.url=...`.
- Docker/Podman must be running — required for most Dev Services (H2 runs in-process, no container).
- Share containers in dev mode: `quarkus.<service>.devservices.shared=true` (default) + `.service-name` for label discovery.
- Reuse across runs (DB/Elasticsearch): `quarkus.datasource.devservices.reuse=true` (default) AND `testcontainers.reuse.enable=true` in `~/.testcontainers.properties`.

DON'T
- Don't set explicit connection config in dev/test unless intended — configuring a service **disables** its Dev Service (the intended off-switch; explicit `.devservices.enabled=false` is usually redundant).
- Don't expect state reset between reused runs — Quarkus won't wipe the DB unless configured (e.g. `init-script-path`).
- Disable: global `quarkus.devservices.enabled=false` or per-service `quarkus.datasource.devservices.enabled=false`. Timeout: `quarkus.devservices.timeout` (default 60s).

### Testing (`@QuarkusTest`)

DO
- Deps (2.x + 3.x stable): `io.quarkus:quarkus-junit5` + `io.rest-assured:rest-assured` (test scope). Mockito: `io.quarkus:quarkus-junit5-mockito`.
- `@QuarkusTest` boots the app once before tests. Test port is **8081** (`quarkus.http.test-port`, `0`=random).
- Inject beans directly — tests are CDI beans: `@Inject MyService svc;`.
- Endpoint paths: `@TestHTTPEndpoint(GreetingResource.class)` + `@TestHTTPResource URL url;`.
- Mock beans with `@InjectMock` (**`io.quarkus.test`** on Quarkus 3.x — moved out of `io.quarkus.test.junit.mockito` to enable component testing) / `@InjectSpy` (`io.quarkus.test.junit.mockito`); or `QuarkusMock.installMockForType(...)` in `@BeforeAll`. `@RestClient` mocks need the `@RestClient` qualifier.
- Per-class config override: implement `QuarkusTestProfile` (`getConfigOverrides()`, `getConfigProfile()`, `testResources()`), apply `@TestProfile(MyProfile.class)`.
- External infra: `@QuarkusTestResource(X.class)`, `X implements QuarkusTestResourceLifecycleManager`. (Newer: `@WithTestResource` + `TestResourceScope`.)
- Roll back DB writes per test with `@TestTransaction` (vs `@Transactional`, which persists).

DON'T
- Don't `@InjectMock` a `@Singleton` directly — add `@MockitoConfig(convertScopes = true)`.
- Don't run `@QuarkusTest` and `@QuarkusIntegrationTest` in the same phase — Surefire runs the former, Failsafe the latter (Gradle: separate source sets).
- Don't assign different profiles/test resources to `@Nested` classes — unsupported.
- Don't use `quarkus.test.flat-class-path=true` unless forced — breaks continuous testing.

### Integration & native tests

DO
- Test the built artifact (jar/native/container) with `@QuarkusIntegrationTest` — commonly `class FooIT extends FooTest {}` to reuse the RestAssured HTTP tests.
- Run native tests: `./mvnw verify -Dnative` (the `native` profile sets `skipITs=false`). Startup wait: `quarkus.test.wait-time` (default 60s).
- Skip in the native/integration run with `@DisabledOnIntegrationTest`. Override run profile (default `prod`): `quarkus.test.integration-test-profile`.

DON'T
- Don't `@Inject` into `@QuarkusIntegrationTest` — black box, no CDI/in-JVM mocks. Drive it over HTTP.
- Don't use `@NativeImageTest` / `@DisabledOnNativeImage` — removed after 1.x; use `@QuarkusIntegrationTest` / `@DisabledOnIntegrationTest`.

### Continuous testing (dev mode)

DO
- Start dev mode: `quarkus dev` / `./mvnw quarkus:dev` / `./gradlew quarkusDev`. Tests **paused** by default — press `r` to resume, `h` for help. Hotkeys: `r` run all, `f` failed only, `b` broken-only, `v` print failures, `o` toggle output, `p` pause, `s` force restart.
- Auto-enable on startup: `quarkus.test.continuous-testing=enabled` (`paused` default / `enabled` / `disabled`; build-time fixed).
- Scope: `quarkus.test.include-pattern` / `exclude-pattern` (regex on class name), `quarkus.test.type=unit|quarkus-test|all` (default `all`). Build-tool `-Dtest=`/`--tests` overrides these.
- Continuous testing without dev mode (e.g. port conflicts): `./mvnw quarkus:test` — no Dev UI in this mode.

DON'T
- Don't expect the Dev UI in `quarkus:test` — it's dev-mode only.
- If `include-pattern` is set, `exclude-pattern` is ignored.

### Sources
- https://quarkus.io/guides/building-native-image (+ /version/2.16/ for 2.x facts)
- https://quarkus.io/guides/writing-native-applications-tips
- https://quarkus.io/guides/native-reference
- https://quarkus.io/guides/dev-services
- https://quarkus.io/guides/getting-started-testing (+ /version/3.20/ for artifact names)
- https://quarkus.io/guides/continuous-testing
- https://github.com/quarkusio/quarkus
