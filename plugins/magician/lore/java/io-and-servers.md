# Java — I/O & servers (Netty vs Tomcat)

Checklist for I/O model, concurrency model, and server runtime. Version-adaptive: target
Java 25 LTS, with fallbacks for 8/11/17/21.

## I/O model: the three tiers

- **`java.io` (blocking streams)** — `InputStream`/`Reader`. One thread parks per call.
  Simplest; scales with thread count.
- **`java.nio` (buffers + channels + `Selector`)** — non-blocking, readiness-based. Since
  **Java 1.4**. One thread multiplexes many sockets; the base for event-loop servers.
- **NIO.2 (`java.nio.file`, async channels)** — `Path`, `Files`,
  `AsynchronousSocketChannel`. Since **Java 7** (JSR 203).

DO use `java.nio.file` (`Path`/`Files`) for new filesystem code, not `java.io.File`.
DON'T hand-roll raw `Selector` loops; use Netty. Manual NIO is a bug farm (partial reads,
`flip()`/`compact()` errors, `OP_WRITE` starvation).

## Concurrency model: thread-per-request vs event-loop

- **Thread-per-request (servlet/Tomcat).** Each request owns a thread; straight-line
  blocking code. Throughput ceiling ≈ pool size; blocked threads still cost stack memory.
  Easy to write, profile, and debug (real stack traces).
- **Event-loop (Netty/reactive).** A few threads run non-blocking handlers over many
  connections. High connection density, low per-connection cost. But **any blocking call on
  an event-loop thread stalls every connection it serves.**

DON'T block a Netty `EventLoop` thread (JDBC, `Thread.sleep`, filesystem, `synchronized`
waits). Offload to a separate executor. DO keep handlers small and return fast.

## Virtual threads: the modern default (Java 21+)

Keep the simple thread-per-request style AND get event-loop-class scalability. Final
(non-preview) in **Java 21** via **JEP 444** (previewed: JEP 425 in 19, JEP 436 in 20).

```java
// Java 21+: one virtual thread per task, no pooling
try (var exec = Executors.newVirtualThreadPerTaskExecutor()) {
    exec.submit(() -> handle(conn));   // blocking I/O inside is fine
}
// Also: Thread.ofVirtual().start(r);  Thread.startVirtualThread(r);
```

Fallback (**Java 8–17**): bounded platform-thread pool (`Executors.newFixedThreadPool(n)`)
with a bounded queue + rejection policy.

DO write plain blocking code on virtual threads — that is the point. They boost
**throughput (scale), not latency (speed).**
DON'T pool virtual threads; they are cheap tasks, not scarce resources.
DON'T cache expensive objects in `ThreadLocal` on virtual threads (a new instance per task
can hit millions). Use immutable shared objects (`DateTimeFormatter`, not `SimpleDateFormat`)
or scoped values (`ScopedValue`, final only in Java 25 / JEP 506; preview on 21–24).
DO cap concurrency against a downstream with a `Semaphore`, not a thread pool:

```java
Semaphore db = new Semaphore(20);
db.acquire(); try { callDb(); } finally { db.release(); }
```

### Pinning (why a virtual thread can't unmount)

- **Java 21–23:** a `synchronized` block around a blocking call **pins** the carrier.
  Replace hot `synchronized` with `ReentrantLock`.
- **Java 24+:** `synchronized` no longer pins (**JEP 491**). Per the **Java 25** docs the
  only remaining pinning causes are **`native` methods** and **FFM (foreign function)** calls.

DO detect pinning via the `jdk.VirtualThreadPinned` JFR event (on by default, 20 ms
threshold) before micro-optimizing locks.

## Running Tomcat on virtual threads (reactive alternative)

Tomcat 11 (Servlet 6.1, requires **Java 17+**) can dispatch each request on a virtual
thread instead of a pooled platform thread:

```xml
<Connector port="8080" protocol="org.apache.coyote.http11.Http11NioProtocol"
           useVirtualThreads="true" .../>
```

`useVirtualThreads` defaults to `false` and is **ignored if a shared `<Executor>` is set**.
On Java 21+ this gives blocking servlet code near-reactive scalability with far less
complexity than a reactive rewrite.
DON'T enable `useVirtualThreads` on Java < 21.

## Connection handling & backpressure

**Tomcat 11 connector defaults:** default protocol is **NIO** (`Http11NioProtocol`);
`Http11Nio2Protocol` is the NIO2 variant (APR is gone as a connector — TLS backend only).
Both are non-blocking for headers/TLS/keep-alive, blocking for body/response.

| Attr | Default | Meaning |
|---|---|---|
| `maxThreads` | 200 | Max concurrent request threads (ignored if `<Executor>` set) |
| `maxConnections` | 8192 | Accepted-connection ceiling; `-1` disables counting (NIO/NIO2) |
| `acceptCount` | 100 | OS accept queue once `maxConnections` hit |
| `connectionTimeout` | 60000 ms | Shipped `server.xml` uses 20000 |

DO size `maxThreads`/`maxConnections` to the downstream, not CPU count; on virtual threads,
raise/uncap `maxConnections` and stop tuning a fixed pool.

**Netty backpressure is not automatic in your handlers.**
DO check `Channel.isWritable()` / set `WRITE_BUFFER_WATER_MARK`, and toggle
`config().setAutoRead(false)` when a slow consumer falls behind — else the outbound buffer
grows unbounded (OOM).
DO release `ByteBuf` (`ReferenceCountUtil.release`) — it is reference-counted; leaks are the
classic Netty bug. Test with `-Dio.netty.leakDetection.level=paranoid`.

## Netty setup (server)

```java
// Netty 4.1 (stable, min JDK 6): boss accepts, worker serves
EventLoopGroup boss = new NioEventLoopGroup(1), worker = new NioEventLoopGroup();
new ServerBootstrap().group(boss, worker)
    .channel(NioServerSocketChannel.class)
    .childHandler(new ChannelInitializer<SocketChannel>() {
        protected void initChannel(SocketChannel ch) { ch.pipeline().addLast(new MyHandler()); }
    })
    .bind(8080).sync();
```

**Netty 4.2:** transport-specific groups are deprecated — use
`new MultiThreadIoEventLoopGroup(NioIoHandler.newFactory())` instead of `NioEventLoopGroup`.
DO frame the byte stream yourself: TCP is a byte queue, not messages — decode with
`ByteToMessageDecoder`/`LengthFieldBasedFrameDecoder`. Never assume one read == one message.
DO `shutdownGracefully()` both groups on exit.

## Netty vs servlet container — pick correctly

DO default to a **servlet container (Tomcat/Jetty) + virtual threads** for standard
HTTP/REST apps: blocking code, full ecosystem, real stack traces.
DO reach for **Netty** for custom/binary wire protocols, extreme connection counts (100k+
idle sockets), lowest per-connection overhead, or fine pipeline control (proxies, gateways,
chat/game servers). It underlies Reactor Netty, gRPC-Java, and Spring WebFlux.
DON'T adopt reactive/Netty purely "for performance" on a CRUD service — on Java 21+ virtual
threads close most of the throughput gap without the callback/debugging tax.

## Sources

- [Netty User Guide for 4.x](https://netty.io/wiki/user-guide-for-4.x.html)
- [Netty 4.2 Migration Guide](https://github.com/netty/netty/wiki/Netty-4.2-Migration-Guide)
- [Apache Tomcat 11.0 Documentation](https://tomcat.apache.org/tomcat-11.0-doc/index.html)
- [Apache Tomcat 11.0 HTTP Connector reference](https://tomcat.apache.org/tomcat-11.0-doc/config/http.html)
- [Apache Tomcat "Which Version" (spec + Java requirements)](https://tomcat.apache.org/whichversion.html)
- [Oracle: Virtual Threads (Java 21 Core Libraries)](https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html)
- [Oracle: Virtual Threads (Java 25 Core Libraries)](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html)
- [Oracle Java Tutorial: Basic I/O (java.io / NIO.2)](https://docs.oracle.com/javase/tutorial/essential/io/index.html)
- JEP 444: Virtual Threads (final, Java 21) — https://openjdk.org/jeps/444
- JEP 425: Virtual Threads (Preview, Java 19) — https://openjdk.org/jeps/425
- JEP 436: Virtual Threads (Second Preview, Java 20) — https://openjdk.org/jeps/436
- JEP 491: Synchronize Virtual Threads without Pinning (Java 24) — https://openjdk.org/jeps/491
