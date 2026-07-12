# Java — Performance & GC

Senior-reviewer checklist. Measure before you tune; the JVM's defaults are good. Version-adaptive: modern target is Java 25 (LTS), with fallbacks for 8/11/17/21.

## Choosing a collector

DO let ergonomics pick unless you have a measured latency/throughput goal. On server-class hardware the default is **G1** (default since Java 9, JEP 248). On small/single-core machines ergonomics may pick **Serial**.

DO map the collector to the goal:
- **G1** (`-XX:+UseG1GC`) — default. Balanced pause/throughput, pause target via `-XX:MaxGCPauseMillis` (default 200). Start here.
- **Parallel** (`-XX:+UseParallelGC`) — max throughput for batch/offline work where multi-second pauses are fine.
- **ZGC** (`-XX:+UseZGC`) — low latency: sub-millisecond, heap-size-independent pauses, heaps up to ~16 TB. Trades some throughput.
- **Serial** (`-XX:+UseSerialGC`) — tiny heaps (≤~100 MB), single core, containers with 1 CPU.

DON'T switch collectors as a first move. First adjust heap size (`-Xmx`), verify GC is actually the bottleneck (check logs), *then* try another collector.

DON'T reach for CMS — removed in Java 14 (JEP 363). Its replacement for low pauses is ZGC (or G1).

### ZGC generational status (verify against your JDK)
- **Java 21**: Generational ZGC added as opt-in (JEP 439) via `-XX:+UseZGC -XX:+ZGenerational`.
- **Java 23**: generational mode became the **default** for `-XX:+UseZGC` (JEP 474).
- **Java 24+ (incl. 25)**: non-generational mode **removed** (JEP 490). `-XX:+UseZGC` is always generational; `-XX:+ZGenerational` is obsolete — DON'T pass it.

```
# Java 25 low-latency service
java -XX:+UseZGC -Xmx8g -Xlog:gc*:file=gc.log:tags,uptime -jar app.jar
```

## Heap & allocation

DO size the heap explicitly in production; don't rely on the fraction default. In containers prefer `-XX:MaxRAMPercentage` over hardcoded `-Xmx` so the JVM tracks the cgroup limit.

DO keep allocation rate low on hot paths — allocation, not collection, is usually the real cost. Fewer short-lived objects → fewer young GCs.

DON'T set `-Xmx` larger than needed "to be safe": bigger heaps mean longer G1/Parallel pauses (ZGC is the exception — its pauses are heap-independent).

DON'T pool ordinary objects to "avoid GC." The young generation makes short-lived allocation nearly free; pools add contention and bugs. Pool only genuinely expensive resources (threads, connections, direct buffers).

DO trust **escape analysis**: the JIT can stack-allocate/scalar-replace objects that don't escape a method, eliminating the allocation entirely — but only after C2 has compiled the method, and only for non-escaping objects. Don't hand-inline to "help" it.

## JIT / warmup

DO account for warmup. Code runs interpreted, then C1, then **C2**-optimized after enough invocations. First calls are 10–100× slower. Warm up before measuring anything.

DON'T draw conclusions from a cold `main()` timing or a single run — you're measuring the interpreter, not steady state.

DO consider AppCDS / (Java 19+) project-level startup features and, if startup latency matters, tiered-compilation tuning — but measure first.

## Collections

DO pre-size when the count is known: `new ArrayList<>(expected)`, `HashMap<>(expected)` (or `HashMap.newHashMap(n)` on Java 19+ to size by entry count, not capacity). Avoids rehash/copy churn.

DO pick by access pattern: `ArrayList` for index/iterate, `ArrayDeque` for stack/queue (not `Stack`/`LinkedList`), `HashMap` for lookup, `EnumMap`/`EnumSet` for enum keys.

DO use factory methods for small fixed data: `List.of(...)`, `Map.of(...)` (Java 9+) — compact and immutable.

DON'T use `LinkedList` as a default list, or `Vector`/`Hashtable`/`Stack` (legacy, synchronized). For concurrency use `ConcurrentHashMap`.

## Records & immutability

DO use **records** (final since Java 16, JEP 395) for immutable data carriers — DTOs, keys, tuples, value-like results. They give correct `equals`/`hashCode`/`toString` and communicate immutability, which enables safe sharing across threads without locks.

```java
record Point(int x, int y) {}   // Java 16+
```

DON'T assume records are faster — they aren't magic; the win is correctness, immutability, and thread-safety. On Java 8–15 fall back to a final class with explicit fields + Objects.equals/hash.

## Measuring — the hard rule

DON'T micro-optimize without a benchmark. Hand-written timing loops lie (dead-code elimination, constant folding, warmup, GC noise).

DO use **JMH** (github.com/openjdk/jmh) for micro/nano benchmarks. Bootstrap with the Maven archetype; consume results via `Blackhole` to defeat dead-code elimination.

```java
@State(Scope.Thread)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Fork(1) @Warmup(iterations = 5) @Measurement(iterations = 5)
public class MyBench {
  @Benchmark
  public void hot(Blackhole bh) { bh.consume(doWork()); }
}
```

DO profile the real application, not a synthetic loop, for end-to-end work:
- **JFR** (Flight Recorder, JEP 328, Java 11+; free): `-XX:StartFlightRecording=duration=60s,filename=rec.jfr`, or programmatically via `jdk.jfr.consumer.RecordingStream` (JEP 349, Java 14+) for live event streaming. Analyze in JDK Mission Control.
- **async-profiler** — low-overhead CPU/alloc/lock sampling with flame graphs; avoids the safepoint-bias of naive samplers.

DO turn on GC logging in production to diagnose pauses: unified logging `-Xlog:gc*` (Java 9+, JEP 271). On Java 8 the old flags are `-XX:+PrintGCDetails -XX:+PrintGCDateStamps`.

DON'T optimize on a hunch: measure → find the dominant cost → change one thing → re-measure.

## Sources

- [Java 25 GC Tuning Guide — Available Collectors](https://docs.oracle.com/en/java/javase/25/gctuning/available-collectors.html)
- [Java 25 GC Tuning Guide — Introduction & Ergonomics](https://docs.oracle.com/en/java/javase/25/gctuning/introduction-garbage-collection-tuning.html)
- [Java 25 JFR API (jdk.jfr) documentation](https://docs.oracle.com/en/java/javase/25/jfapi/)
- [OpenJDK ZGC wiki](https://wiki.openjdk.org/display/zgc/Main)
- JEP 248: Make G1 the Default Garbage Collector (Java 9) — https://openjdk.org/jeps/248
- JEP 271: Unified GC Logging (Java 9) — https://openjdk.org/jeps/271
- JEP 328: Flight Recorder (Java 11) — https://openjdk.org/jeps/328
- JEP 349: JFR Event Streaming (Java 14) — https://openjdk.org/jeps/349
- JEP 363: Remove the Concurrent Mark Sweep (CMS) Garbage Collector (Java 14) — https://openjdk.org/jeps/363
- JEP 395: Records (Java 16) — https://openjdk.org/jeps/395
- JEP 439: Generational ZGC (Java 21) — https://openjdk.org/jeps/439
- JEP 474: ZGC: Generational Mode by Default (Java 23) — https://openjdk.org/jeps/474
- JEP 490: ZGC: Remove the Non-Generational Mode (Java 24) — https://openjdk.org/jeps/490
- [JMH — Java Microbenchmark Harness](https://github.com/openjdk/jmh)
- [async-profiler](https://github.com/async-profiler/async-profiler)
