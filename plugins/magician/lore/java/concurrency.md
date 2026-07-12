# Java — Concurrency & virtual threads

Senior-reviewer checklist. Verify the target JDK before applying any rule.
Finality map (do not misremember): Virtual Threads **final in 21** (JEP 444);
synchronized-pinning fix **in 24** (JEP 491); Scoped Values **final in 25** (JEP 506);
Structured Concurrency **still preview in 25** (JEP 505) — `StructuredTaskScope` is not stable API.

## Threads vs ExecutorService

- **DON'T** create raw `new Thread(...).start()` for tasks — unbounded, unmanaged, no result/error channel.
- **DO** submit to an `ExecutorService` and always shut it down (try-with-resources on 19+; `ExecutorService` is `AutoCloseable`, `close()` awaits termination).
```java
try (var pool = Executors.newFixedThreadPool(8)) {
    Future<Integer> f = pool.submit(() -> compute());
    int r = f.get();
} // close() blocks until tasks finish
```
- **DO** size platform pools to the workload: CPU-bound ≈ `Runtime.getRuntime().availableProcessors()`; I/O-bound needs more — but prefer virtual threads (21+) over a huge platform pool.
- **DON'T** use `newCachedThreadPool()` for untrusted/bursty load — unbounded, can exhaust the OS.
- **DON'T** call `Thread.stop()`/`suspend()`/`resume()`. Cancel via interruption + a checked flag.

## Virtual threads (JEP 444, final in Java 21)

- **DO** use virtual threads for high-throughput, thread-per-request, blocking I/O — **21+ only**.
```java
// Java 21+
try (var vexec = Executors.newVirtualThreadPerTaskExecutor()) {
    for (var req : requests) vexec.submit(() -> handle(req));
}
// or: Thread.ofVirtual().start(runnable);
```
- **Java 8–17 fallback:** no virtual threads. Use a **bounded** platform pool (`newFixedThreadPool`) or `CompletableFuture` + async I/O — never unbounded pools.
- **DON'T pool virtual threads.** Cheap and disposable — one per task. Never build a `newFixedThreadPool` of virtual threads; never reuse them.
- **DON'T** use virtual threads for CPU-bound work — no speed, only scale (Little's Law). Keep a platform `ForkJoinPool` for parallel compute.
- **DON'T** cap concurrency by pool size on virtual threads. Limit a scarce resource with a `Semaphore`, not a small pool.
- Virtual threads have fixed `NORM_PRIORITY` (`setPriority` no-op) and always support `ThreadLocal`.

### Pinning

- Pinning = a virtual thread cannot unmount from its carrier while blocked, starving the scheduler.
- **Java 21–23:** `synchronized` blocks/methods that guard blocking I/O **pin**. **DO** replace those hot `synchronized` regions with `ReentrantLock`.
```java
private final ReentrantLock lock = new ReentrantLock();
lock.lock(); try { blockingIo(); } finally { lock.unlock(); }
```
- **Java 24+ (JEP 491):** `synchronized` no longer pins in nearly all cases — the migration above is usually unnecessary. Remaining pinning: native/JNI and foreign-function calls.
- **DO** detect pinning via the `jdk.VirtualThreadPinned` JFR event (on by default, 20 ms threshold). (`-Djdk.tracePinnedThreads` was the 21–23 diagnostic.)

## Structured concurrency (JEP 505 — PREVIEW in 25, not final)

- **STATUS:** `StructuredTaskScope` is **preview** through JDK 25 (fifth; sixth = JEP 525 in 26). Requires `--enable-preview`. Do not adopt where a stable API surface is required.
- **DO** (25 preview) open via static factory + `Joiner`; scope is `AutoCloseable`:
```java
// Java 25 preview
try (var scope = StructuredTaskScope.open()) {          // all-success policy
    Subtask<String>  a = scope.fork(() -> query(left));
    Subtask<Integer> b = scope.fork(() -> query(right));
    scope.join();                                       // throws if any fails
    return new Result(a.get(), b.get());
}
```
- `fork`/`join`/`close` are owner-thread only; `join()` runs once; `fork` cannot follow `join`. Joiners: `awaitAllSuccessfulOrThrow`, `allSuccessfulOrThrow`, `anySuccessfulResultOrThrow`, `awaitAll`.
- **Pre-25 / no preview:** coordinate fan-out with `ExecutorService.invokeAll` or `CompletableFuture.allOf` — cancel siblings on failure yourself.

## ScopedValue vs ThreadLocal (JEP 506 — final in 25)

- **DO** (25+) use `ScopedValue` for one-way, immutable, bounded-lifetime context — cheaper than `ThreadLocal`, safe for millions of virtual threads.
```java
// Java 25+
static final ScopedValue<User> USER = ScopedValue.newInstance();
ScopedValue.where(USER, user).run(() -> handle());   // USER.get() valid only inside
```
- **DON'T** reach for `ThreadLocal` as ambient context with virtual threads: mutable, unbounded lifetime, per-thread copies leak at scale. `ScopedValue` is immutable and auto-cleared at scope exit.
- **Pre-25 fallback:** `ThreadLocal` (`private static final`), and **always** `remove()` in a `finally` when reusing platform threads to avoid leaks/stale reads.
- `ThreadLocal` still fits expensive mutable per-thread caches (e.g. legacy `SimpleDateFormat`; better: share an immutable `DateTimeFormatter`).

## java.util.concurrent building blocks

- **DO** prefer `ConcurrentHashMap` over `Collections.synchronizedMap`; use atomic composites — `computeIfAbsent`, `merge`, `compute` — never get-then-put (a race). Iterators are weakly consistent.
- **DO** use `java.util.concurrent.atomic` for lock-free counters; `LongAdder` beats `AtomicLong` under high contention.
- **DON'T** hand-roll producer/consumer — use a `BlockingQueue` (`ArrayBlockingQueue` bounded, `SynchronousQueue`) for backpressure.
- **DO** compose async with `CompletableFuture` (`thenCompose`/`thenCombine`/`allOf`); pass an explicit `Executor` to `*Async` — the default common `ForkJoinPool` is shared and small. **Always** attach `exceptionally`/`handle`; a dropped future swallows exceptions.
- **DO** pick the right lock: `ReentrantLock` (try/timeout/fairness), `ReadWriteLock`/`StampedLock` (read-heavy; `StampedLock` optimistic, non-reentrant, no `Condition`), `Semaphore`, `CountDownLatch` (one-shot), `CyclicBarrier`/`Phaser` (reusable).

## Memory model & happens-before

- **DON'T** assume one thread's writes are visible to another without a happens-before edge. Unsynchronized shared mutable state = data race = undefined (torn/stale reads, reordering).
- **Edges you can rely on:** program order in a thread; monitor unlock → later lock of same monitor; `volatile` write → later read of that field; `Thread.start()` → the thread's actions; a thread's actions → another returning from its `join()`; `final` fields via a properly constructed object.
- **j.u.c. edges:** put into a concurrent collection → later read/remove; `Lock.unlock`→`lock`, `Semaphore.release`→`acquire`, `countDown`→`await`; submit → execution → `Future.get()`.
- **DO** mark a cross-thread flag `volatile` (e.g. a stop signal). `volatile` gives visibility + ordering, **not** atomicity of compound ops (`count++` still races — use an atomic/lock).
- **DO** publish safely (immutable `final`-field objects, or via `volatile`/`final`/concurrent collection). **DON'T** leak `this` from a constructor.

## Sources

- [JEP 444: Virtual Threads](https://openjdk.org/jeps/444) — final in JDK 21
- [JEP 491: Synchronize Virtual Threads without Pinning](https://openjdk.org/jeps/491) — delivered JDK 24
- [JEP 506: Scoped Values](https://openjdk.org/jeps/506) — final in JDK 25
- [JEP 505: Structured Concurrency (Fifth Preview)](https://openjdk.org/jeps/505) — preview in JDK 25
- [JEP 525: Structured Concurrency (Sixth Preview)](https://openjdk.org/jeps/525) — preview in JDK 26
- [java.util.concurrent package summary (JDK 25)](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/package-summary.html) — happens-before rules, classes
- [StructuredTaskScope (JDK 25 preview)](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/StructuredTaskScope.html)
- [dev.java — Learn Java](https://dev.java/learn/)
- JLS §17.4 Memory Model / happens-before order
