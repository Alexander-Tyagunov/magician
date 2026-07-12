# Micronaut (core)

DO use compile-time DI/AOP — no runtime reflection. If injection "randomly" fails, the annotation processor didn't run: wire `annotationProcessor`/`kapt`/`ksp` (`io.micronaut:micronaut-inject-java`). DON'T expect classpath scanning.
DO use `jakarta.inject` (`@Singleton`, `@Inject`, `@Named`, `@Qualifier`) + `@Factory`/`@Bean`, `@ConfigurationProperties`, `@Value("${x}")`, `@Requires`. DON'T use Spring stereotypes (`@Component`/`@Autowired`).
DO put `@Introspected` on POJOs crossing DI/serde/HTTP (reflection-free access); use `@ReflectiveAccess` only when unavoidable — critical for GraalVM native.
DO build HTTP with `@Controller`+`@Get/@Post`, declarative `@Client`. Netty/non-blocking: DON'T block the event loop — return `Mono/Flux`/`CompletableFuture`, or mark blocking (JDBC) methods `@ExecuteOn(TaskExecutors.BLOCKING)`.
DO use Micronaut Data `@Repository` (compile-time queries). DO test with `@MicronautTest`.

Version: Micronaut 5.x current (Java 25, Groovy 5, Kotlin 2.3, GraalVM 25; JSpecify nullability); prior 4.x (Java 17). Both use `jakarta.*` + `jakarta.inject`.
Commands: scaffold `mn create-app`; run `./gradlew run` / `./mvnw mn:run`; build `./gradlew assemble` / `./mvnw package`; native `./gradlew nativeCompile` / `./mvnw package -Dpackaging=native-image`; test `./gradlew test`.

Deep dive when writing non-trivial micronaut — read lore/micronaut/{di-and-aot,http-server-and-clients,data-and-reactive,native-and-testing}.md

Sources: docs.micronaut.io/latest/guide, guides.micronaut.io, github.com/micronaut-projects/micronaut-core
