# Quarkus — core digest

Version cue: current **Quarkus 3.x** → Java 17+, `jakarta.*` (Jakarta EE 10), CDI via ArC. Prior **2.x** → Java 11+, `javax.*`, REST ext `quarkus-resteasy-reactive`.

DO put config in `application.properties`; inject with `@ConfigProperty(name=..)` or type-safe `@ConfigMapping`.
DO use CDI: `@ApplicationScoped`/`@Inject` (`jakarta.enterprise`/`jakarta.inject`). Prefer `@ApplicationScoped` over `@Singleton`.
DO use JAX-RS: `@Path`,`@GET`,`@Produces` (`jakarta.ws.rs`); add ext `quarkus-rest` + `quarkus-rest-jackson` for JSON (3.x rename of resteasy-reactive).
DO wrap DB writes in `@Transactional` (`jakarta.transaction`); Panache: extend `PanacheEntity` or impl `PanacheRepository<E>` (`io.quarkus.hibernate.orm.panache`).
DON'T block reactive threads — return Mutiny `Uni`/`Multi` (`io.smallrye.mutiny`), not `CompletableFuture`.
DON'T rely on runtime reflection in native — register with `@RegisterForReflection` if needed.
DON'T mix `javax.*` (2.x) imports into a 3.x project — use `jakarta.*`.
DO test with `@QuarkusTest`; Dev Services auto-start DB/broker containers, no manual config in tests.

Commands: create `mvn io.quarkus.platform:quarkus-maven-plugin:create -Dextensions=rest`; dev `./mvnw quarkus:dev`; test `./mvnw test`; jar `./mvnw install`; native `./mvnw package -Dnative`.

Deep dive when writing non-trivial quarkus — read lore/quarkus/{core-and-arc,reactive-and-mutiny,rest-and-panache,native-dev-and-testing}.md

Sources: quarkus.io/guides (getting-started, hibernate-orm-panache, native-reference); github.com/quarkusio/quarkus
