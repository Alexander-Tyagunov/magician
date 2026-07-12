# quarkus — Reactive & Mutiny

Framework-specifics only. Java-language lore lives in `lore/java/*`.

Quarkus reactive core = **Eclipse Vert.x + Netty**. The reactive API is **Mutiny**
(`io.smallrye.mutiny`, `Uni`/`Multi`) — **not** Reactor, **not** RxJava. Two execution
lanes coexist in one app: **event-loop (I/O) threads** and the **worker thread pool**.
Quarkus REST picks the lane per method via a "best guess" on the return type; annotations
override it.

## Version baseline (adapt to what the project runs)

DO map guidance to the major:
- **Quarkus 3.x** — `jakarta.*` namespace (Jakarta EE 10), Hibernate ORM 6, MicroProfile 6.
  Java 11 minimum, **17 recommended**. Virtual threads need **Java 21+**.
- **Quarkus 2.x** — `javax.*` namespace, pre-Jakarta. Same Java 11 floor. No `@RunOnVirtualThread`.

DO know the **3.9 "big rename"** (March 2024): RESTEasy Reactive → **Quarkus REST**.
- 3.9+: `quarkus-rest`, `quarkus-rest-jackson`, `quarkus-rest-jsonb`.
- 2.x / pre-3.9: `quarkus-resteasy-reactive`, `quarkus-resteasy-reactive-jackson`.
- DON'T mix `quarkus-rest*` and `quarkus-resteasy*` (classic) in one build — duplicate-provider errors.
- DON'T confuse with legacy blocking `quarkus-resteasy` (RESTEasy Classic) — different stack.

## The golden rule

DON'T block an I/O (event-loop) thread. There are only a few; blocking one stalls many
requests. No JDBC, no `Thread.sleep`, no `.await()`, no `toIterable()` on the event loop —
Mutiny's `await`/`toIterable` throw if called on an I/O thread.

## Choosing the model

DO pick per endpoint, not per app:
- **Reactive (`Uni`/`Multi`)** — high concurrency, I/O-bound, streaming, end-to-end
  non-blocking stack (reactive SQL client, reactive REST client). Runs on the event loop.
- **Imperative on virtual threads (`@RunOnVirtualThread`)** — I/O-bound but you want plain
  blocking-style code; needs Java 21+. Best when reactive composition adds no value.
- **Imperative on worker thread** — default for blocking libs (JDBC, JPA); CPU-bound work.

DON'T use virtual threads for CPU-bound work — no benefit, adds scheduling cost.
DON'T rewrite blocking code to reactive just for style; virtual threads or the worker pool
are fine when the win is only ergonomic.

## Thread selection & @Blocking

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

## @RunOnVirtualThread (Quarkus 3, Java 21+)

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

## Mutiny essentials

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

## Reactive data & config

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

## Sources

- https://quarkus.io/guides/getting-started-reactive
- https://quarkus.io/guides/quarkus-reactive-architecture
- https://quarkus.io/guides/mutiny-primer
- https://quarkus.io/guides/rest
- https://quarkus.io/guides/virtual-threads
- https://quarkus.io/blog/road-to-quarkus-3/
- https://github.com/quarkusio/quarkusio.github.io/blob/main/_posts/2024-03-21-the-big-rename.adoc
- https://github.com/quarkusio/quarkus
