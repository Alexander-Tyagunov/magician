# Java — Sync vs async & reactive

Senior-reviewer checklist. Pick ONE model per call path; never mix blocking calls into a
non-blocking chain. Target Java 25 LTS; fallbacks noted per rule.

## Choosing a model (decision first)

- **DO** default to plain **blocking, thread-per-task** code on **Java 21+** — virtual threads
  make it scale. Reserve reactive for pre-21 baselines or genuine event-loop/streaming needs.
- **DO** use **CompletableFuture** for a *few* independent async steps you compose in one method.
- **DO** use **Reactor/RxJava** only when you need operator pipelines, backpressure across a
  network boundary, or you're already in a reactive stack (WebFlux, R2DBC).
- **DON'T** adopt reactive "for performance" on Java 21+; virtual threads give the same
  throughput with debuggable stack traces. Reactive's cost is real: hard debugging.

## Virtual threads (Java 21+, JEP 444)

Finalized in **Java 21** (JEP 444). A blocking call *unmounts* the virtual thread from its
carrier, so the OS thread is free — millions of VTs are fine.

- **DO** create one VT per task; the executor is auto-closeable and joins on close:
  ```java
  try (var exec = Executors.newVirtualThreadPerTaskExecutor()) {
      exec.submit(() -> httpClient.send(req, ofString())); // blocking is OK here
  }
  ```
  Also `Thread.ofVirtual().start(r)` / `Thread.startVirtualThread(r)`.
- **DON'T** pool virtual threads. Pools reuse *expensive* resources; VTs are cheap. To cap a
  scarce downstream (DB pool), use a `Semaphore`, not a fixed thread pool.
- **DON'T** rely on `ThreadLocal` for heavy caching across millions of VTs — memory blows up.
- **Pinning:** pre-24, a VT blocking inside `synchronized` pinned its carrier. **JEP 491
  (Java 24)** removed `synchronized` pinning; native/FFM frames can still pin.
  - **Java 21–23:** replace `synchronized` guarding a blocking op with `ReentrantLock`; diagnose
    with `-Djdk.tracePinnedThreads=full` or JFR `jdk.VirtualThreadPinned`.
  - **Java 24+:** `synchronized` no longer pins on block — the workaround is optional.
- **Java 8–17 fallback:** no VTs. Use a **bounded** platform-thread pool
  (`Executors.newFixedThreadPool(n)`); never `newCachedThreadPool()` for unbounded blocking I/O.

## CompletableFuture (Java 8+; timeouts Java 9+)

- **DO** pass an explicit `Executor` to every `*Async` step doing real work. The no-executor
  `supplyAsync`/`thenApplyAsync` run on `ForkJoinPool.commonPool()`.
  ```java
  var pool = Executors.newFixedThreadPool(8);
  CompletableFuture.supplyAsync(this::loadA, pool)
      .thenCombine(CompletableFuture.supplyAsync(this::loadB, pool), this::merge);
  ```
- **DON'T** run **blocking** I/O on the common pool — it's sized to CPU count and shared
  JVM-wide; you starve parallel streams and other futures. (On Java 21+, hand the blocking work
  to `newVirtualThreadPerTaskExecutor()` instead.)
- **DO** compose, don't block: `thenCompose` (flatMap, avoid nested `CompletableFuture<CompletableFuture<T>>`),
  `thenCombine` (join two), `allOf`/`anyOf` (fan-in). `thenApply` (no `Async`) may run on the
  completing thread — fine for cheap, pure maps only.
- **DON'T** swallow failures. Terminate every chain with `exceptionally(fn)` or `handle((v,ex)->…)`;
  an uncaught exceptional stage is silent. Add `orTimeout(d,unit)` (fails with `TimeoutException`)
  or `completeOnTimeout(fallback,d,unit)`.
- **DON'T** call `.get()`/`.join()` mid-pipeline — it blocks a pool thread.

## Flow API / Reactive Streams (spec)

`java.util.concurrent.Flow` (JDK 9+) is **1:1 semantically equivalent** to the Reactive Streams
1.0.4 spec (`org.reactivestreams`). Four interfaces, seven one-way `void` methods:

- `Flow.Publisher<T>.subscribe(Subscriber<? super T>)`
- `Flow.Subscriber<T>`: `onSubscribe(Subscription)`, `onNext(T)`, `onError(Throwable)`, `onComplete()`
- `Flow.Subscription`: `request(long n)`, `cancel()`
- `Flow.Processor<T,R> extends Subscriber<T>, Publisher<R>`

**Backpressure = demand:** the subscriber pulls via `request(n)`; a compliant publisher never
sends more than requested. `Flow.defaultBufferSize()` is **256**.

- **DO** treat `Flow` as the neutral SPI for interop; **DON'T** hand-write publishers/subscribers
  for app logic — use Reactor or RxJava operators. Backpressure signaling stays non-blocking.
- **DON'T** block or throw inside `onNext`/`onError`/`onComplete`; **DON'T** `request(n<=0)`.

## Reactor (Mono/Flux) & RxJava — basics + backpressure

**Reactor** (`Flux<T>` 0..N, `Mono<T>` 0..1) — foundation of Spring WebFlux.
**RxJava 3** (`io.reactivex.rxjava3`): `Flowable` (backpressure, Reactive Streams) vs
`Observable` (NO backpressure — bounded/UI streams only); plus `Single`/`Maybe`/`Completable`.

- **DO** isolate blocking calls onto a dedicated scheduler so you don't stall the event loop:
  ```java
  Mono.fromCallable(() -> blockingJdbcCall())
      .subscribeOn(Schedulers.boundedElastic());   // Reactor
  ```
  RxJava equivalent: `Flowable.fromCallable(...).subscribeOn(Schedulers.io())`.
- **DON'T** block on the parallel/computation scheduler (Reactor `Schedulers.parallel()`,
  RxJava `Schedulers.computation()`) — those are CPU-bound, sized to cores.
- **`subscribeOn`** sets where the *source* runs (one per chain, position-independent);
  **`publishOn`**/`observeOn` switches the thread for operators *downstream* of it.
- **Backpressure:** prefer demand-aware sources. For bursty producers use
  `onBackpressureBuffer()` (bounded — set a max + overflow strategy; unbounded risks OOM),
  `onBackpressureDrop`, or `onBackpressureLatest`. In RxJava, use `Flowable` (not `Observable`)
  with a `BackpressureStrategy` when bridging via `Flowable.create(...)`.
- **DON'T** `block()`/`blockFirst()`/`blockLast()` (Reactor) or `blockingGet()`/`blockingFirst()`
  (RxJava) inside a reactive chain or on a non-blocking scheduler — allowed only at the true
  boundary (e.g. a `main`/test). To bridge to `CompletableFuture` **without** blocking, use
  `Mono.toFuture()` — it subscribes and completes the future on `onNext`/`onComplete` (it does
  not block and does not throw on a non-blocking scheduler).
- **DON'T** forget to subscribe — nothing runs until a terminal `subscribe(...)`. Handle the
  error consumer; a missing one rethrows to the global hook.

## Version cheat-sheet

- **Java 8:** CompletableFuture. No Flow, no VTs. Bounded pools; reactive libs for scale.
- **Java 9–17:** + `Flow` API, CF timeouts. Reactive is the scaling path.
- **Java 21 (LTS):** virtual threads final (JEP 444) — new code goes blocking thread-per-task.
- **Java 24:** `synchronized` no longer pins virtual threads (JEP 491).
- **Java 25 (LTS):** blocking + VTs is the default; reactive only for streaming/backpressure.
  Scoped Values final (JEP 506) as the `ThreadLocal` alternative; **Structured Concurrency is
  still preview (JEP 505) — behind `--enable-preview`, don't rely on it in production.**

## Sources

- Oracle Java SE 25 API — `java.util.concurrent.Flow`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/Flow.html
- Oracle Java SE 25 API — `java.util.concurrent.CompletableFuture`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/CompletableFuture.html
- Reactive Streams (spec 1.0.4, interfaces, backpressure, Flow equivalence): https://www.reactive-streams.org/
- JEP 444: Virtual Threads (finalized in Java 21): https://openjdk.org/jeps/444
- JEP 491: Synchronize Virtual Threads without Pinning (Java 24): https://openjdk.org/jeps/491
- Oracle — Creating/using virtual threads (no pooling, pinning, Semaphore): https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html
- Project Reactor Reference (schedulers, blocking bridge, backpressure): https://projectreactor.io/docs/core/release/reference/
- ReactiveX / RxJava (Observable vs Flowable, backpressure, Schedulers): https://github.com/ReactiveX/RxJava
