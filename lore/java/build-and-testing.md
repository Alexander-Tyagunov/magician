# Java — Build & testing

Senior-reviewer checklist. Target Java 25 LTS; fall back per baseline. Verify version facts against docs, never memory.

## Build tool: Maven vs Gradle

DO reach for **Maven** on library/corporate multi-module projects wanting a fixed, declarative lifecycle (`validate → compile → test → package → verify → install`). Convention over config; less to break.
DO reach for **Gradle** for faster incremental builds (build cache, configuration cache), custom build logic, polyglot (Android/Kotlin), or large monorepos. Prefer the **Kotlin DSL** (`build.gradle.kts`) for type safety.
DO commit and invoke the **wrapper** — `./mvnw` / `./gradlew` — so every machine builds with the pinned tool version; never the global `mvn`/`gradle`.
DON'T mix both tools in one module or hand-edit lockfiles.
- Verify: Maven `./mvnw -q verify`; Gradle `./gradlew build`.

## Pin the JDK (toolchains + release)

DO decouple the JDK that *runs the build* from the JDK you *compile/test against* via **toolchains** — CI can run on 25 while targeting 17.

Gradle: `java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }`. Add the Foojay resolver in `settings.gradle.kts` for auto-download: `id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"`.
Maven: `maven-toolchains-plugin` (`toolchain` goal) reads `~/.m2/toolchains.xml` mapping `<provides>` (version+vendor) → `<jdkHome>`.

DO set the bytecode target with **`--release N`** (JDK 9+): compiles *and* links against that release's API, catching accidental use of newer APIs. Maven `<maven.compiler.release>17</maven.compiler.release>`; Gradle `tasks.withType<JavaCompile>{ options.release = 17 }`.
DON'T use `<source>/<target>` (or `sourceCompatibility/targetCompatibility` alone) — they don't restrict the API surface, so code compiles but fails at runtime on the older JVM.

## Reproducible / deterministic builds

DO set `project.build.outputTimestamp` (Maven) or `preserveFileTimestamps=false` + `isReproducibleFileOrder=true` on jar/zip tasks (Gradle) for byte-identical archives.
DO pin every plugin and dependency to an exact version; forbid ranges and `LATEST`/`RELEASE`/dynamic `+`. Lock: Gradle `dependencyLocking`; Maven `maven-enforcer-plugin` (`requireReleaseDeps`).
DON'T let the build read wall-clock, hostname, or env into artifacts.

## Dependency hygiene

DO import a **BOM** in `dependencyManagement` (Maven) / `platform(...)` (Gradle) to align a family's versions; then declare deps *without* versions.
```groovy
testImplementation platform("org.junit:junit-bom:5.14.4")
testImplementation "org.junit.jupiter:junit-jupiter"
```
DO run `mvn dependency:tree` / `gradle dependencies` + enforcer `dependencyConvergence` to kill conflicting transitive versions.
DO scope correctly: `test`/`testImplementation` for test-only; `provided`/`compileOnly` for container-supplied APIs; prefer `implementation` over `api` (Gradle) to limit transitive leakage.
DON'T ship deps with known CVEs — wire an audit (OWASP dependency-check, Renovate/Dependabot).

## JUnit 5 (Jupiter) structure

Versions: latest 5.x is **5.14.4** (Java 8+). **JUnit 6.x** (6.1.1) needs **Java 17+** — same Jupiter model; move when your baseline is 17+.

DO organize with lifecycle + display:
```java
@DisplayName("OrderService")
class OrderServiceTest {
  @BeforeEach void setUp() { /* fresh fixture per test */ }
  @Test void placesOrder() { /* ... */ }
  @Nested @DisplayName("when out of stock") class OutOfStock { @Test void rejects() {} }
}
```
DO use `assertAll(...)` to report every failed assertion at once; `assertThrows(X.class, () -> ...)` for exceptions; `@Timeout` for bounds; `@TempDir Path dir` for auto-cleaned filesystem work.
DON'T rely on test ordering or shared mutable static state. DON'T use `@TestInstance(PER_CLASS)` unless you want one instance per class (enables non-static `@BeforeAll`/`@MethodSource`).
DON'T keep JUnit 4 (`org.junit.Test`) in new code — migrate; run legacy via the Vintage engine only during transition.

## Parameterized & data-driven

DO collapse near-identical tests into `@ParameterizedTest`:
```java
@ParameterizedTest @ValueSource(ints = {1, 2, 3})
void positive(int n) { assertThat(n).isPositive(); }
```
- `@CsvSource` / `@CsvFileSource` for tabular rows; `@EnumSource` for enums; `@MethodSource("factory")` / `@FieldSource("fixtures")` for complex objects (`Stream<Arguments>` / static field).
- `@NullSource`, `@EmptySource`, `@NullAndEmptySource` for edge inputs.
- **`@ParameterizedClass`** (introduced **JUnit 5.13**, still `@API` **EXPERIMENTAL** in 6.x — don't rely on API stability) parameterizes a whole class, not one method.
DON'T loop over cases inside a single `@Test` — you lose per-case reporting.

## AssertJ (assertions)

DO make assertions fluent with AssertJ (3.27.x). One static import: `import static org.assertj.core.api.Assertions.*;`.
```java
assertThat(orders).hasSize(2).extracting("id").containsExactly(1L, 2L);
assertThatThrownBy(() -> svc.load(null))
    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("id");
```
DO use `containsExactlyInAnyOrder`, `extracting`, `satisfies`, `usingRecursiveComparison().ignoringFields(...)` for deep checks, and `assertThatCode(...).doesNotThrowAnyException()`. Group with `SoftAssertions`/`assertSoftly` for all failures at once.
DON'T write `assertThat(a.equals(b))` — it asserts nothing; use `.isEqualTo(b)`. DON'T put `.as(...)`/`.withFailMessage(...)` *after* the terminal assertion — it's a no-op.

## Mockito (mocks)

DO wire JUnit 5 via the extension (adds `mockito-junit-jupiter`):
```java
@ExtendWith(MockitoExtension.class)
class Test { @Mock Repo repo; @InjectMocks Service svc; }
```
Mockito 5.x requires **Java 11+** (stay on Mockito 4.x for Java 8). Stub with `when(repo.find(id)).thenReturn(x)` or BDD `given(...).willReturn(...)`; verify with `verify(repo).save(any())`; capture with `@Captor ArgumentCaptor<T>`.
DO keep default **strict stubbing** (via the extension) — it fails on unused stubs. Use `mockStatic(...)`/`mockConstruction(...)` (inline default in 5.x) *sparingly* for legacy statics.
DON'T mock types you don't own (wrap them), value objects/DTOs, or everything — over-mocking tests the mock, not the code.

## Testcontainers (integration)

DO use real dependencies in a container instead of in-memory fakes for DB/queue/broker integration tests. Needs Docker; add `org.testcontainers:testcontainers-junit-jupiter` (import `testcontainers-bom`, v2.0.5).
```java
@Testcontainers
class RepoIT {
  @Container static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16");
}
```
DO make the container **`static`** to share one instance across all methods (started once); use an **instance** field only when each test needs a fresh one. Reuse the singleton pattern across classes to cut startup; keep IT tests sequential (parallel is unsupported).
DON'T point ITs at shared/staging infra, or run them as unit tests — bind to `*IT` + Failsafe (`verify`), not Surefire (`test`).

## What to test (and not)

DO test: business/domain logic, branch + boundary cases, error paths, serialization contracts, and one integration test per external boundary (DB, HTTP, queue). Prefer many fast unit tests + a thin layer of ITs (the pyramid); keep tests deterministic, isolated, order- and network-independent.
DON'T test framework/library internals, trivial getters/setters, generated code, or private methods directly (test via the public API). DON'T chase 100% coverage — assert behavior, not lines.

## Sources

- Maven Guides: https://maven.apache.org/guides/
- Maven Toolchains: https://maven.apache.org/guides/mini/guide-using-toolchains.html
- Maven Compiler `--release`: https://maven.apache.org/plugins/maven-compiler-plugin/
- Gradle User Guide: https://docs.gradle.org/current/userguide/userguide.html
- Gradle Java Toolchains: https://docs.gradle.org/current/userguide/toolchains.html
- JUnit 5 User Guide: https://docs.junit.org/current/user-guide/
- JUnit 5.13 Release Notes (@ParameterizedClass): https://docs.junit.org/5.13.0/release-notes/
- AssertJ Docs: https://assertj.github.io/doc/
- Mockito: https://site.mockito.org/
- Testcontainers for Java: https://java.testcontainers.org/
- Testcontainers JUnit 5: https://java.testcontainers.org/test_framework_integration/junit_5/
