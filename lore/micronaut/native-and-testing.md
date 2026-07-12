# micronaut — GraalVM native & testing

Senior-reviewer checklist. Framework-specifics only (Java-language lore lives in `lore/java/*`). Verify version facts against docs, never memory.

Versions: **Micronaut 5.x** current (5.1.x; JDK 25 baseline). Prior **4.x** (Java 17). Both use `jakarta.*`. Native/test annotations below are stable across 4→5. Native build wiring is the same; only the JDK/GraalVM baseline moves.

Micronaut's edge is compile-time DI/AOT — it emits GraalVM reflection/resource/proxy metadata for its own beans automatically. You only configure the reflection GraalVM can't see: your reflectively-accessed types and third-party libs.

## GraalVM native build

DO scaffold with the `graalvm` feature: `mn create-app --features=graalvm demo` — wires the native plugin + a GraalVM base Dockerfile.
DO build the native executable:
- Gradle: `./gradlew nativeCompile` (via `io.micronaut.application` plugin, which applies `org.graalvm.buildtools.native`). Native container image: `./gradlew dockerBuildNative`.
- Maven: `./mvnw package -Dpackaging=native-image`. Native container: `-Dpackaging=docker-native`.
DO run the build on a **GraalVM JDK** matching the framework baseline (JDK 25 for MN 5, 17 for MN 4) with the `native-image` component installed. Verify with `native-image --version`.
DON'T hand-invoke `native-image` — let the build plugin pass the generated arg files. DON'T expect a plain OpenJDK to compile native.

## Reflection & resource config

DO annotate every POJO crossing DI / serialization / HTTP boundaries with `@Introspected` — compile-time, reflection-free bean access; the native-safe default.
DO use `@ReflectiveAccess` (`io.micronaut.core.annotation`) on the specific type/constructor/method/field that genuinely needs runtime reflection.
DO bulk-configure third-party types you can't annotate with `@TypeHint`:
```java
@TypeHint(value = { LinkedHashMap.class, HashSet.class },
          accessType = TypeHint.AccessType.ALL_DECLARED_CONSTRUCTORS)
```
DO use `@ReflectionConfig` (repeatable) to model GraalVM reflect entries per type in Java instead of raw JSON.
DON'T reach for hand-written `reflect.json` unless nothing else fits — it's the legacy escape hatch; prefer the annotations, which the AOT step merges into the generated config.
DO keep runtime-loaded files (templates, `application.yml`, `logback.xml`) on the classpath — Micronaut auto-registers config + logging resources for native. For extra resources add `META-INF/native-image/<group>/<artifact>/resource-config.json` (or `-H:IncludeResources` regex) so GraalVM bundles them.
DON'T rely on `Class.forName`, classpath scanning, or dynamic proxies of arbitrary interfaces at runtime — none survive native without explicit metadata.

## What breaks in native (and the fix)

DON'T use `jackson-databind` for JSON on native without help — it's reflection-heavy. DO use **Micronaut Serde** (`io.micronaut.serde:micronaut-serde-jackson`) with `@Serdeable` on DTOs — compile-time, reflection-free, native-ready. If you must keep Jackson databind, annotate each model `@ReflectiveAccess`.
DON'T assume a library "just works" — pull **GraalVM Reachability Metadata** (the buildtools plugin consumes the shared metadata repo automatically) for common libs (JDBC drivers, Netty, etc.).
DO move heavy/illegal-at-build-time work out of static initializers — build-time class init can capture host state or fail. Push such init to runtime (or mark the class for runtime init via native-image args).
DON'T read env/hostname/wall-clock at build init and bake it into the image.
DO regenerate metadata for unknown reflection with the **GraalVM tracing agent** on the JVM run (`-agentlib:native-image-agent=config-output-dir=...`), then feed the output into `META-INF/native-image`. Treat it as a last resort after annotations.

## @MicronautTest

DO add `io.micronaut.test:micronaut-test-junit5` (or `-spock` / `-kotest`) as a test dependency and ensure the annotation processor runs (`micronaut-inject-java` on `annotationProcessor`/`kapt`/`ksp`) — without it the context won't build.
DO annotate the test class; it starts an `ApplicationContext` (and the embedded server when needed) and injects beans:
```java
@MicronautTest
class OrderControllerTest {
  @Inject @Client("/") HttpClient client;   // server auto-started
  @Inject OrderService service;             // real bean injected
}
```
Key options (verify against your version):
- `transactional` (default **true**) — each test method runs in a transaction rolled back at the end. Set `@MicronautTest(rollback = false)` to commit; `transactional = false` to disable wrapping.
- `startApplication = false` — build the context but don't start the HTTP server (unit-style).
- `environments = {"test","integration"}` — activate env-specific config.
- `application = App.class` / `packages = "com.acme"` — scope for integrations needing classpath scanning.
DO replace collaborators with `@MockBean`:
```java
@MockBean(MathService.class)
MathService mathService() { return Mockito.mock(MathService.class); }
```
DON'T rely on field injection order or shared static state across methods — the context is per-class by default.
DO inject test-only properties inline with `@Property(name="foo", value="bar")`, or dynamically via `TestPropertyProvider.getProperties()` (requires `@TestInstance(PER_CLASS)`).

## Test Resources & Testcontainers

DO prefer **Micronaut Test Resources** over hand-wiring Testcontainers. It resolves a *missing* config property by spinning up a throwaway container:
- Gradle: apply `io.micronaut.test-resources`. Maven: set `micronaut.test.resources.enabled`. Easiest via Micronaut Launch `test-resources` feature.
- Leave `datasources.default.url` **unset** in test config → it auto-provides `url`/`username`/`password`/`driver-class-name` (and R2DBC `r2dbc.datasources.*`). Detection needs one of `db-type`, `dialect`, or `driver-class-name`.
- Modules cover postgres/mysql/mariadb/oracle/mssql, kafka (`kafka.bootstrap.servers`), redis (`redis.uri`), mongodb (`mongodb.uri`), rabbitmq, elasticsearch, localstack, etc.
- Override images with `test-resources.containers.<db-type>.image-name`; MSSQL needs `test-resources.containers.mssql.accept-license=true`.
DON'T set the property AND expect a test resource — a present property short-circuits provisioning (that's how prod/CI overrides work).
DO hand-wire raw Testcontainers only when Test Resources lacks the module: implement `TestPropertyProvider` (needs `@TestInstance(PER_CLASS)`), `db.start()`, and return `datasources.default.url`/`username`/`password` from `getProperties()`.
DON'T point integration tests at shared/staging infra; bind slow ITs to `*IT` + Failsafe, keep fast `@MicronautTest` units on Surefire (see `lore/java/build-and-testing.md`).

## Sources

- Micronaut Reference (guide): https://docs.micronaut.io/latest/guide/
- GraalVM support (graalServices/graalFAQ): https://docs.micronaut.io/latest/guide/#graal
- Micronaut Guides: https://guides.micronaut.io/
- Micronaut Test: https://micronaut-projects.github.io/micronaut-test/latest/guide/
- Micronaut Test Resources: https://micronaut-projects.github.io/micronaut-test-resources/latest/guide/
- Micronaut Serde: https://micronaut-projects.github.io/micronaut-serde/latest/guide/
- micronaut-core (5.1.x docs source): https://github.com/micronaut-projects/micronaut-core
- GraalVM Native Build Tools: https://graalvm.github.io/native-build-tools/latest/
