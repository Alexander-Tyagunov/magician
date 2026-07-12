# micronaut — Compile-time DI & AOT

Micronaut resolves DI/AOP **at compile time** via annotation processors that generate `BeanDefinition` classes (ASM bytecode). No runtime classpath scanning, no reflection-based injection, no runtime-generated proxies. Startup time and heap are ~independent of codebase size; native-image friendly. Contrast Spring: runtime reflection + runtime proxies, cost scales with bean count.

Version map (verify before asserting):
- **Micronaut 5.x** (current): Java **25** baseline, Groovy 5, Kotlin 2.3, GraalVM 25.0.3; `jakarta.*`.
- **Micronaut 4.x**: Java **17** baseline; completed `javax`→`jakarta` (`jakarta.inject`/`.validation`/`.persistence`).
- **Micronaut 3.x**: Java **8** baseline; accepted both `javax.inject` and `jakarta.inject`.

## DO — annotation processor wiring

- DO register the annotation processor — without it no `BeanDefinition` is generated and the bean is invisible at runtime. The `io.micronaut.application` Gradle plugin wires `micronaut-inject-java`; for plain libs add it manually.
- DO put every processor (inject, validation, data, openapi) on `annotationProcessor`/`ksp`, not `implementation`. Kotlin: use **KSP** on MN 4+ (kapt is legacy).
- DO recompile after annotation changes — DI errors surface at build time, not startup.

## DO — beans, scopes, factories

- DO annotate managed classes with a scope. **Default scope is `@Prototype`** (new instance per injection point); `@Prototype` is a synonym for `@Bean`.
- DO use `jakarta.inject.Singleton` for shared state. Constructor injection is preferred (no annotation needed for a single constructor).

```java
import jakarta.inject.Singleton;

@Singleton
class OrderService {
    private final Repo repo;
    OrderService(Repo repo) { this.repo = repo; } // constructor injection
}
```

- DO use `@Factory` for beans you don't own (third-party/conditional). **Factory methods default to `@Singleton`**; annotate `@Prototype` for per-injection.

```java
import io.micronaut.context.annotation.Factory;
import jakarta.inject.Singleton;

@Factory
class Clients {
    @Singleton HttpClient httpClient() { return HttpClient.create(...); }
}
```

- DO pick scopes deliberately: `@Singleton` (one instance); `@Prototype`/`@Bean` (new each injection, default); `@Context` (eager, built with `ApplicationContext`); `@RequestScope` (per HTTP request); `@Refreshable` (rebuilt on `RefreshEvent`/`/refresh`); `@ThreadLocal`; `@Infrastructure` (unreplaceable core beans).
- DO qualify ambiguous beans with `jakarta.inject.Named` (or custom `@Qualifier`); `@Primary`/`@Secondary` to bias; `@Any` + `BeanProvider<T>` for deferred/multi resolution.
- DO drive conditional beans with `@Requires` (`property`, `beans`, `classes`, `env`, `missingBeans`). Use `@Replaces(Bean.class)` to override (great for tests).

## DON'T

- DON'T rely on runtime component scanning / `@ComponentScan` — nothing is discovered at runtime; if it wasn't compile-time processed it doesn't exist.
- DON'T inject into `private` fields — Micronaut falls back to reflection there (breaks native-image assumptions). Use constructor or `protected`/package-private `@Inject`.
- DON'T expect Spring proxies. AOP advice is a generated `MethodInterceptor` applied only to advice-annotated methods; self-invocation bypasses it (as in Spring).
- DON'T mix `javax.inject` on MN 4/5 (removed). DON'T assume a factory method is prototype — it's singleton unless annotated.

## DO — configuration (type-safe, compile-time)

- DO model config with `@ConfigurationProperties("prefix")`. Prefer **immutable** config via `@ConfigurationInject` on the constructor.

```java
@ConfigurationProperties("engine")
public class EngineConfig {
    @ConfigurationInject
    public EngineConfig(@Nullable String name, int year) { ... }
}
```

- DO use `@EachProperty("my.datasources")` + `@Parameter` for one-bean-per-sub-key config; `@EachBean` for a dependent bean per existing bean.
- DO inject single values with `@Value("${x:default}")` or `@Property(name="x")`; add `jakarta.validation` constraints — validated at startup.

## DO — reflection-free data & native image

- DO annotate value/DTO types with `@Introspected` for compile-time `BeanIntrospection` (reflection-free property access). Required for many bind/serialize paths under native-image.
- DO prefer **Micronaut Serialization** (`micronaut-serialization`, `@Serdeable`) over Jackson Databind for native builds — serializers computed at build time. With Jackson Databind, non-introspected types need `@ReflectiveAccess` (MN 5) or GraalVM metadata.
- DON'T add libs needing runtime reflection/CGLIB without GraalVM reachability metadata — they fail in native image.

## DO — AOT (ahead-of-time optimization)

Micronaut AOT is a **build-time** post-processor (not a runtime dep) that precomputes startup work. Experimental — pin versions. Enable via the build plugin, not app config.

- Gradle: apply both plugins; configure the `aot` DSL.

```groovy
plugins {
    id("io.micronaut.application") version "..."
    id("io.micronaut.aot")         version "..."
}
micronaut {
    aot {
        convertYamlToJava.set(true)     // YAML → Java config
        precomputeOperations.set(true)
        cacheEnvironment.set(true)      // env immutable after startup
        netty { enabled.set(true) }     // Netty startup props
    }
}
```

- Maven: `micronaut-maven-plugin` (`<configuration><aot>…`).
- DO build/run optimized artifacts: Gradle tasks `optimizedJar`, `optimizedRun`, `optimizedJitJarAll` (fat jar, needs shadow), `nativeOptimizedCompile`, `optimizedDockerBuild`.
- DO push non-DSL optimizers via `configFile.set(file("gradle/micronaut-aot.properties"))` or `aotPlugins`; diagnostics report: `micronaut.aot.report.enabled=true`.
- DON'T hand-edit AOT-generated sources or add these keys to `application.yml` — they belong to the build plugin only.

## Spring → Micronaut deltas (reviewer notes)

- `@Component/@Service/@Repository` → `@Singleton` (+ `@Introspected` where needed); `@Bean` methods → `@Factory` methods.
- `@Autowired` → constructor injection / `jakarta.inject.Inject`; `@Qualifier` → `@Named`.
- `@Conditional...` → `@Requires`; `@Profile` → `@Requires(env=...)`.
- No `BeanFactoryPostProcessor`/runtime-proxy tricks — extend via annotation processors, `@Introduction`/`@Around` AOP, or bean events.

## Sources

- Micronaut User Guide (latest / 5.x): https://docs.micronaut.io/latest/guide/
- Micronaut 4 User Guide (Java 17 baseline, javax→jakarta): https://docs.micronaut.io/4.9.0/guide/
- Micronaut Guides: https://guides.micronaut.io/
- micronaut-core (IoC scopes, factories, config, introspection, breaking changes): https://github.com/micronaut-projects/micronaut-core
- Micronaut 5 Release notes (Java 25 / Groovy 5 / Kotlin 2.3 / GraalVM 25.0.3): https://github.com/micronaut-projects/micronaut-core/wiki/Micronaut-5-Release
- Micronaut AOT reference: https://micronaut-projects.github.io/micronaut-aot/latest/guide/
- Micronaut Gradle plugin (application + AOT plugins, DSL, tasks): https://micronaut-projects.github.io/micronaut-gradle-plugin/latest/
- Micronaut Serialization (`@Serdeable`, build-time serializers): https://github.com/micronaut-projects/micronaut-serialization
