# Python — asyncio & concurrency model

Lore for an AI agent writing async Python. Terse, version-adaptive. Assume the reader targets some Python in 3.8..3.14. Give the modern form AND the fallback; never claim a feature earlier than the release that shipped it.

`async`/`await` syntax: PEP 492, Python 3.5. Async generators: PEP 525, Python 3.6. One event loop runs per thread; while a Task runs, no other Task runs until it hits an `await` suspension point.

## Entrypoint — asyncio.run

DO
- Use `asyncio.run(main())` as the single top-level entrypoint (added 3.7). It creates a fresh loop, runs the coroutine, and closes the loop.
- `loop_factory=` param exists since 3.12 if you must configure the loop. In the `python -m asyncio` REPL, `await` directly — no `run()`.

DON'T
- DON'T call `asyncio.run()` more than once or from inside a running loop — it raises `RuntimeError`.
- DON'T reach for `loop.run_until_complete()` / `get_event_loop()` / manual loop management in new code. Those are low-level, library-author APIs.
- DON'T rely on the deprecated policy system — it is slated for removal in 3.16.

## await vs create_task — concurrency is opt-in

DO
- Directly `await coro()` when you need the result *now*, sequentially.
- Use `asyncio.create_task(coro)` (3.7) to start work concurrently; `await` the task later. This is the only way multiple coroutines make progress together.
- Keep a strong reference to every task (`tasks = [...]` or a set). The loop holds only weak refs; an un-referenced task can be GC'd mid-flight.

DON'T
- DON'T assume `await a(); await b()` runs concurrently — it does not. It is strictly sequential.
- DON'T fire-and-forget without storing the task object.

## Structured concurrency — TaskGroup (3.11+) over gather

DO (Python 3.11+)
- Prefer `asyncio.TaskGroup` (added 3.11). It is structured: the `async with` block waits for all children, and if any task raises, siblings are **cancelled** and errors surface as an `ExceptionGroup` (PEP 654 / `except*`, 3.11).

```python
async with asyncio.TaskGroup() as tg:      # 3.11+
    tg.create_task(fetch(a))
    tg.create_task(fetch(b))
# all done here; failures raised as ExceptionGroup
```

DO (fallback, any version)
- Use `asyncio.gather(*aws)` to collect results in order.
- `return_exceptions=True` turns failures into result entries instead of propagating.

```python
results = await asyncio.gather(fetch(a), fetch(b), return_exceptions=True)
```

DON'T
- DON'T assume `gather()` cancels siblings on first error. With the default `return_exceptions=False`, the first exception propagates but the **other awaitables keep running** — a common leak. TaskGroup fixes this.
- DON'T pass raw coroutines to `asyncio.wait()` — forbidden since 3.11; wrap in tasks first.

## Timeouts — asyncio.timeout (3.11+) vs wait_for

DO (Python 3.11+)
- Use `async with asyncio.timeout(delay):` (added 3.11) around a block; it converts the internal `CancelledError` into `TimeoutError` caught *outside* the block. `asyncio.timeout_at(when)` for an absolute deadline.

```python
async with asyncio.timeout(5):   # 3.11+
    await do_work()
```

DO (fallback)
- Use `await asyncio.wait_for(coro, timeout)` (any version). On timeout it cancels the awaitable and raises `TimeoutError`.

DON'T
- DON'T catch `asyncio.TimeoutError` as distinct from `TimeoutError` — since 3.11 `wait_for`/`timeout` raise the builtin `TimeoutError` (they are the same object as `asyncio.TimeoutError`, aliased). Catch `TimeoutError`.

## Never block the loop

A single blocking/CPU-bound call stalls **every** Task and I/O on that loop's thread until it returns.

DO
- Offload blocking work: `await asyncio.to_thread(fn, *args)` (added 3.9) for the simple case.
- For a specific executor, `await loop.run_in_executor(executor, fn, *args)`; use a `ProcessPoolExecutor` for CPU-bound work (threads won't help under the GIL).
- Use async-native libraries for I/O (`aiohttp`/`httpx`, async DB drivers) inside coroutines.

DON'T
- DON'T call `time.sleep()`, `requests.get()`, blocking file/DB I/O, or heavy CPU loops directly in a coroutine. Use `asyncio.sleep()` and async clients.
- DON'T do blocking network logging on the loop thread.
- Note: `to_thread` is bounded by the GIL, so it is for I/O-bound work — not CPU parallelism (3.13 ships an *experimental* free-threaded build; don't assume it).

## Cancellation

`asyncio.CancelledError` subclasses `BaseException` (not `Exception`), so bare `except Exception` won't swallow it.

DO
- Clean up with `try/finally` around `await` points.
- If you catch `CancelledError` for cleanup, **re-raise it** — suppressing it breaks cancellation.
- Task-level introspection since 3.11: `Task.cancelling()`, `Task.uncancel()`; `cancel(msg=...)` message propagated since 3.11.
- Protect a critical awaitable from outer cancellation with `asyncio.shield(aw)` (keep a strong ref to it).

DON'T
- DON'T write `except:` or `except BaseException:` that eats `CancelledError`.
- DON'T assume `task.cancel()` guarantees the task stops — it requests cancellation at the next suspension; the coroutine can still finish.

## Async context managers & iterators

DO
- `async with` / `async for` require `__aenter__/__aexit__` and `__anext__`. Write reusable managers with `@contextlib.asynccontextmanager` (added 3.7).
- Use `contextlib.AsyncExitStack` (3.7) to compose a dynamic number of async managers; `contextlib.aclosing()` (3.10) to guarantee `aclose()` on async generators.

DON'T
- DON'T use plain `with`/`for` on async resources — the setup/teardown coroutines won't be awaited.
- DON'T leak async generators — close them (`aclosing`) so their `finally` runs on the loop.

## Version cheat-sheet (verified against docs.python.org)

- 3.7 — `asyncio.run`, `create_task`, `current_task`, `asynccontextmanager`, `AsyncExitStack`.
- 3.9 — `asyncio.to_thread`; `cancel(msg=)`.
- 3.10 — `wait_for`/`gather`/`shield` drop the `loop=` param; `aclosing`; `X | Y` unions; `match`.
- 3.11 — `TaskGroup`, `asyncio.timeout`/`timeout_at`, `Runner`, `Task.uncancel/cancelling`; `ExceptionGroup`/`except*` (PEP 654); `wait_for` raises builtin `TimeoutError`. Built-in generics `list[int]` since 3.9.
- 3.12 — `run(loop_factory=)`; eager task factory; PEP 695 type params.
- 3.13 — experimental free-threading (no-GIL) build; experimental JIT.
- 3.14 — `run`/`Runner.run` accept any awaitable; `create_task(eager_start=)`.

## Sources

- https://docs.python.org/3/library/asyncio.html
- https://docs.python.org/3/library/asyncio-task.html
- https://docs.python.org/3/library/asyncio-runner.html
- https://docs.python.org/3/library/asyncio-dev.html
- https://docs.python.org/3/library/contextlib.html
- https://peps.python.org/pep-0492/
