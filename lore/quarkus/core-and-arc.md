# quarkus — Core, ArC (CDI) & build-time

Framework lore only. Java-language rules live in `lore/java/*`. Quarkus does as much work as possible at **build time** (augmentation), not runtime — that is the whole point. Fidelity: annotations/config keys below are verified against current docs (3.x).

## Version baseline — read first

DO know which major you target; it dictates the namespace and JDK.
- **Quarkus 3.x** (current; 3.20 & 3.15 are LTS): **Java 17+** (17/21/25), **`jakarta.*`** namespace (`jakarta.inject.Inject`, `jakarta.enterprise.context.*`, `jakarta.ws.rs.*`). CDI is **Jakarta CDI 4.1 (Lite)**.
- **Quarkus 2.x** (legacy): **Java 11+** (Java 8 only in early 2.x), **`javax.*`** namespace, CDI Lite (older).
- DON'T mix namespaces. Migrating 2→3 = `javax.*` → `jakarta.*` across the whole app. Use the OpenRewrite recipe / `quarkus update`; don't hand-edit at scale.

DON'T assume config keys are stable across majors. Example (verified): **`quarkus.package.type` (2.x) → `quarkus.package.jar.type` (3.x)**. Check the current property name before writing it.

## Build-time augmentation philosophy

DO push work to build time. Benefits: fast startup, low RSS, dead-code elimination, and GraalVM native-image compatibility. Three boot phases:
1. **Augmentation** (build) — build steps read the **Jandex** annotation index; must NOT load application classes. Output is recorded bytecode.
2. **Static Init** (`@Record(STATIC_INIT)`) — runs in a static init method; for native it runs *at build* and state is serialized into the binary. No ports, no threads, no runtime config reads here.
3. **Runtime Init** (`@Record(RUNTIME_INIT)`) — runs from `main`; the only phase allowed to open ports / read runtime config.

DON'T do reflection, classpath scanning, or config parsing at runtime if an extension can do it at build. DON'T use `System.getProperty`/`System.getenv` for config (bypasses recording).

## ArC (CDI) — DO

- Annotate beans: `@ApplicationScoped` (default for singletons — normal-scoped, lazy, proxied), `@Singleton` (pseudo-scope, eager-ish, no proxy), `@RequestScoped`, `@Dependent`. `@SessionScoped` needs the Undertow extension.
- Inject with `@Inject` (field/constructor). `@Inject` is **optional** on a sole constructor and on fields that already carry a qualifier.
- Prefer **constructor injection** for testability. No no-arg constructor needed for normal-scoped beans.
- Producers: `@Produces` (skippable if the method has a scope/qualifier/stereotype). Observers: `@Observes`.
- String qualifier: prefer `@io.smallrye.common.annotation.Identifier("x")` over `@Named`.
- Eager startup work: `@io.quarkus.runtime.Startup` on a bean/method.
- Conditional wiring is **build-time**: `@io.quarkus.arc.DefaultBean`, `@IfBuildProfile`/`@UnlessBuildProfile`, `@IfBuildProperty`/`@UnlessBuildProperty`. Runtime-conditional lookup: `@LookupIfProperty`/`@LookupUnlessProperty`.
- Inject all implementations: `@All List<MyIface> beans`.

## ArC — DON'T

- DON'T expect CDI **Full**: no portable extensions, no `InterceptionFactory`, no decorators-as-in-full. ArC is CDI **Lite** + extras.
- DON'T rely on a bean surviving if nothing references it — ArC **removes unused beans** by default. If accessed only via `CDI.current()`/reflection, mark `@io.quarkus.arc.Unremovable` or tune `quarkus.arc.remove-unused-beans`.
- DON'T annotate a class you expect to be a bean without a **bean-defining annotation** — simplified discovery (`annotated` mode) skips it (producers/observers on unannotated classes are still picked up as `@Dependent`).
- DON'T reach for runtime config inside `@IfBuildProperty` — those resolve at build time only.

## Config — MicroProfile Config / SmallRye — DO

- Put config in `src/main/resources/application.properties` (tests: `src/test/resources/...`). YAML needs the `quarkus-config-yaml` extension.
- Inject scalars: `@org.eclipse.microprofile.config.inject.ConfigProperty(name="greeting.message", defaultValue="hi") String msg;` (`@Inject` optional). Use `Optional<T>` for truly optional values.
- Prefer type-safe groups: `@io.smallrye.config.ConfigMapping(prefix="server")` on an **interface**; method `sslPort()` maps to `server.ssl-port` (kebab-case).
- Source precedence (high→low): system props (400) > env vars (300) > `.env` (295) > `$PWD/config/application.properties` (260) > classpath `application.properties` (250).
- Env-var form: `foo.bar` ↔ `FOO_BAR` (non-alphanumeric → `_`, uppercased).
- Profiles: prefix keys with `%dev.`, `%test.`, `%prod.` or use `application-{profile}.properties`. `dev` = `quarkus:dev`, `test` = tests, `prod` = default. Activate custom via `quarkus.profile`.

## Config — DON'T

- DON'T use the reserved `quarkus.` prefix for app properties.
- DON'T expect a **build-time-fixed** property (lock icon in docs, e.g. most `quarkus.arc.*`, datasource driver) to change at runtime — it needs a rebuild. Runtime override of a build-fixed key triggers a mismatch warning (`quarkus.config.build-time-mismatch-at-runtime=warn|fail`).

## Dev mode & build — DO

- Live coding: `quarkus dev` or `./mvnw quarkus:dev` (Gradle: `./gradlew quarkusDev`). Recompiles + redeploys on next request/refresh. Debug on `5005` (no suspend) by default. Dev UI at `/q/dev`.
- Continuous testing runs in the dev console; **Dev Services** auto-start backing containers (DB, Kafka, …) in dev/test — no local config needed.
- Add extensions: `quarkus extension add hibernate-orm-panache` or `./mvnw quarkus:add-extension -Dextensions=...`. List with `quarkus:list-extensions`.
- Build: `quarkus build` / `./mvnw install`. Default package is **fast-jar** → `target/quarkus-app/`, run `java -jar target/quarkus-app/quarkus-run.jar` (NOT a single jar). Uber-jar: `quarkus.package.jar.type=uber-jar`.
- Native: `quarkus build --native` or `./mvnw install -Dnative` (`-Dquarkus.native.container-build=true` for a containerized GraalVM build). Native tests: `./mvnw verify -Dnative`.

## Dev mode & build — DON'T

- DON'T ship the fast-jar `runner`-only jar and expect it standalone — the whole `quarkus-app/` dir (lib, quarkus, app) is required.
- DON'T register beans/resources for reflection ad hoc in native — use an extension build step or `@io.quarkus.runtime.annotations.RegisterForReflection` on classes accessed reflectively.
- DON'T do heavy init in constructors for native; prefer `@Record(RUNTIME_INIT)` recorders / `@Startup`.

## Reactive core (context)

Quarkus core is reactive: engine is **Eclipse Vert.x + Netty**; async API is **Mutiny** (`io.smallrye.mutiny.Uni` = 0/1 item, `Multi` = stream). Blocking endpoints run on worker threads; reactive ones on the event loop — don't block the event loop.

## Sources

- https://quarkus.io/guides/ (guide index; current version 3.37.x)
- https://quarkus.io/guides/cdi-reference (ArC / Jakarta CDI 4.1 Lite)
- https://quarkus.io/guides/cdi (CDI intro)
- https://quarkus.io/guides/config-reference (SmallRye / MicroProfile Config, profiles, sources)
- https://quarkus.io/guides/config-mappings (@ConfigMapping)
- https://quarkus.io/guides/maven-tooling (dev mode, build, packaging, native)
- https://quarkus.io/guides/writing-extensions (build steps, recorders, boot phases)
- https://quarkus.io/guides/quarkus-reactive-architecture (Vert.x, Mutiny)
- https://github.com/quarkusio/quarkus
