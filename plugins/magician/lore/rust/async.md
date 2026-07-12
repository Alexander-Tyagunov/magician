> **Source:** adapted from the *Rust Development Guidelines* by the rmcp-server-kit contributors,
> dual-licensed MIT OR Apache-2.0 —
> https://github.com/andrico21/rmcp-server-kit/blob/main/RUST_GUIDELINES.md
> Condensed and reformatted for magician lore; consult the source for full rationale and examples.

# Rust — Async Rules

## DON'T: Call blocking I/O in async functions

Blocking calls (`std::fs`, `std::net`, heavy computation) stall the runtime's worker thread and starve other tasks. Use async I/O; for unavoidable blocking use `spawn_blocking`.

```rust
// BAD: blocks the Tokio runtime
async fn read_config(path: &str) -> String {
    std::fs::read_to_string(path).unwrap()
}

// GOOD: async I/O
tokio::fs::read_to_string(path).await

// GOOD: unavoidable blocking
tokio::task::spawn_blocking(move || expensive_hash(&data)).await
```

## DO: Use `tokio::select!` for cancellation and timeouts

```rust
tokio::select! {
    result = do_work() => handle_result(result),
    _ = tokio::time::sleep(Duration::from_secs(30)) => {
        tracing::warn!("operation timed out");
    }
}
```

## DON'T: Hold locks across `.await` points

`std::sync::Mutex` is not async-aware. Holding it across `.await` blocks the whole thread if another task tries to acquire it. Minimize lock scope, or use `tokio::sync::Mutex` when the guard must live across `.await`.

```rust
// BAD
let guard = mutex.lock().unwrap();
do_async_work().await;
drop(guard);

// GOOD: drop before await
{
    let guard = mutex.lock().unwrap();
    let data = guard.clone();
}
do_async_work_with(data).await;

// OR: use tokio::sync::Mutex when you must hold across await
let guard = async_mutex.lock().await;
do_async_work().await;
```

**LLM-bias note.** LLM-generated async code defaults to `std::sync::Mutex` (dominant in training data). Review every `Mutex` import in async modules:

- `tokio` tasks: `tokio::sync::Mutex` when the guard may live across `.await`; `std::sync::Mutex` only for strictly synchronous, short critical sections.
- embassy / `no_std`: `embassy_sync::mutex::Mutex` for async-aware locks. `embassy_sync::blocking_mutex::Mutex` (with `CriticalSectionRawMutex`) only when the critical section never `.await`s.
- `clippy::await_holding_lock` catches the obvious case but does NOT see through helper-function returns, struct fields, or `MutexGuard::map`. Necessary but not sufficient.

## DO: Use `tokio::task::yield_now()` in CPU-bound async loops

If you must do CPU work in an async context, yield periodically to avoid starving other tasks.

## DO: Annotate every async fn with cancel safety (cancel-safe / NOT cancel-safe)

Futures are cancellable at **every** `.await` point. Any future used inside `tokio::select!`, `tokio::time::timeout`, `embassy_futures::select`, or `JoinHandle::abort` can be dropped between awaits, leaving partial state. Cancel safety is **not expressible in the type system** — no `CancelSafe` marker trait exists; it lives only in documentation. LLM-generated code almost never raises this. Treat the annotation as mandatory.

```rust
// NOT cancel-safe: if dropped between insert() and send_ack(), we wrote to the
// DB but never acknowledged — client retries and we duplicate.
async fn process(stream: TcpStream, db: &Db) -> Result<()> {
    let data = read_message(&stream).await?;
    db.insert(&data).await?;       // if cancelled here, dup on retry
    send_ack(&stream).await?;
    Ok(())
}

// GOOD: isolate the non-cancel-safe section so outer cancellation can't tear it.
let handle = tokio::spawn(async move {
    db.insert(&data).await?;
    send_ack(&stream).await?;
    Ok::<_, Error>(())
});
handle.await?
```

Rules:

- Every async fn that may run inside `select!`, `timeout`, or an `abort`-able task MUST carry a `// cancel-safe: <reason>` or `// NOT cancel-safe: <reason>` doc comment. No exceptions.
- "All awaits are idempotent" is NOT a valid reason — idempotency is about retries, not partial state between awaits.
- Consult tokio docs per call. E.g. `AsyncReadExt::read` is cancel-safe, `read_exact` is NOT.
- embassy: `embassy_futures::select` cancels the losing branch by dropping its future — same rules apply.

## DO: Audit Drop impls of async resources (transactions, connections, guards)

Drop runs on every exit path, including panics and cancellation. For types returned from `.await` (DB transactions, pooled connections, async file handles), Drop may perform I/O — which in an async runtime can run blocking code on a worker thread or silently no-op.

```rust
// Subtle: commit() can itself fail, leaving tx in an indeterminate drop state.
//   - sqlx: Drop queues a rollback that runs on the *next* async use of the
//     connection (or on pool return); if nothing drives it, rollback never runs.
//   - deadpool-postgres: deferred cleanup via the connection's background task;
//     rollback may not run if the runtime is shutting down.
async fn run(pool: &Pool) -> Result<Data> {
    let tx = pool.get().await?.transaction().await?;
    match do_work(&tx).await {
        Ok(result) => { tx.commit().await?; Ok(result) }
        Err(e)     => { tx.rollback().await?; Err(e) }
    }
}
```

Rules:

- For every async resource type you `.await` into scope, know what its Drop does — read the source, not just the docs.
- Prefer explicit `commit` / `rollback` / `close` on every path. Do not rely on Drop to clean up async work.
- If Drop is the only cleanup path, document it at the call site.
