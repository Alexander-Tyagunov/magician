# quarkus — Native, dev services & testing

Framework-specific lore. Java-language lore lives in `lore/java/*`.

**Version map (verify against project's Quarkus version):**
- **Quarkus 3.x** — Java 17+, `jakarta.*`. Native needs **GraalVM for JDK 21 / Mandrel 23.1** (`quarkus.native.enabled=true`).
- **Quarkus 2.x** — Java 11+/17, `javax.*`. Native uses **GraalVM/Mandrel 22.3** (`quarkus.package.type=native`).
- `-Dnative` works in BOTH; the Maven `native` profile maps it to the correct property per version. Prefer the profile.

## Native image build

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

## Reflection & resources (native)

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

## Dev Services (auto Testcontainers)

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

## Testing (`@QuarkusTest`)

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

## Integration & native tests

DO
- Test the built artifact (jar/native/container) with `@QuarkusIntegrationTest` — commonly `class FooIT extends FooTest {}` to reuse the RestAssured HTTP tests.
- Run native tests: `./mvnw verify -Dnative` (the `native` profile sets `skipITs=false`). Startup wait: `quarkus.test.wait-time` (default 60s).
- Skip in the native/integration run with `@DisabledOnIntegrationTest`. Override run profile (default `prod`): `quarkus.test.integration-test-profile`.

DON'T
- Don't `@Inject` into `@QuarkusIntegrationTest` — black box, no CDI/in-JVM mocks. Drive it over HTTP.
- Don't use `@NativeImageTest` / `@DisabledOnNativeImage` — removed after 1.x; use `@QuarkusIntegrationTest` / `@DisabledOnIntegrationTest`.

## Continuous testing (dev mode)

DO
- Start dev mode: `quarkus dev` / `./mvnw quarkus:dev` / `./gradlew quarkusDev`. Tests **paused** by default — press `r` to resume, `h` for help. Hotkeys: `r` run all, `f` failed only, `b` broken-only, `v` print failures, `o` toggle output, `p` pause, `s` force restart.
- Auto-enable on startup: `quarkus.test.continuous-testing=enabled` (`paused` default / `enabled` / `disabled`; build-time fixed).
- Scope: `quarkus.test.include-pattern` / `exclude-pattern` (regex on class name), `quarkus.test.type=unit|quarkus-test|all` (default `all`). Build-tool `-Dtest=`/`--tests` overrides these.
- Continuous testing without dev mode (e.g. port conflicts): `./mvnw quarkus:test` — no Dev UI in this mode.

DON'T
- Don't expect the Dev UI in `quarkus:test` — it's dev-mode only.
- If `include-pattern` is set, `exclude-pattern` is ignored.

## Sources
- https://quarkus.io/guides/building-native-image (+ /version/2.16/ for 2.x facts)
- https://quarkus.io/guides/writing-native-applications-tips
- https://quarkus.io/guides/native-reference
- https://quarkus.io/guides/dev-services
- https://quarkus.io/guides/getting-started-testing (+ /version/3.20/ for artifact names)
- https://quarkus.io/guides/continuous-testing
- https://github.com/quarkusio/quarkus
