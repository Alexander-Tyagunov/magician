# Python — Performance, the GIL & concurrency

Lore for an AI agent. Terse, version-adaptive (assume reader is on 3.8–3.14). Measure before you optimize. Verify feature availability at runtime, not from memory.

## The GIL — what it actually constrains

One lock per interpreter serializes bytecode execution: only one thread runs Python at a time in a standard CPython build. It is released around blocking I/O and inside many C extensions (numpy, `hashlib`, `zlib`).

- **DO** reach for threads when the bottleneck is I/O (network, disk, DB) — the GIL is dropped during the wait.
- **DON'T** expect threads to speed up pure-Python CPU work in a GIL build; you get concurrency, not parallelism.
- **DON'T** confuse the GIL with thread-safety. `+=`, `dict`/`list` mutation from multiple threads still needs `threading.Lock`. Even the free-threaded build advises explicit locks, not relying on built-in-type internal locks.

## Pick the right concurrency model

| Workload | Use | Module |
|---|---|---|
| I/O-bound, blocking libs | threads | `concurrent.futures.ThreadPoolExecutor` |
| I/O-bound, high fan-out | asyncio | `asyncio` |
| CPU-bound | processes | `concurrent.futures.ProcessPoolExecutor` / `multiprocessing` |
| CPU-bound, share large arrays | processes + shared mem | `multiprocessing.shared_memory` |

- **DO** default to the `concurrent.futures` executors; the `Executor` API is the same for threads and processes, so switching is a one-line change.
- **DON'T** hand-roll `threading.Thread` pools when a pool executor does it.

### CPU-bound → multiprocessing

```python
from concurrent.futures import ProcessPoolExecutor
with ProcessPoolExecutor() as ex:
    results = list(ex.map(cpu_fn, items))
```

- **DO** know the start method: macOS/Windows default to `spawn` (macOS since 3.8). On POSIX the default changed `fork` → `forkserver` in **3.14**; `fork` is no longer the default anywhere. `fork` in a multithreaded parent is unsafe.
- **DO** guard entry points: `if __name__ == "__main__":` is mandatory with `spawn`/`forkserver` or children re-import and re-run module code.
- **DO** keep payloads picklable and small; every arg/result is pickled across the process boundary. For big arrays use `multiprocessing.shared_memory` (3.8+) or memory-map.
- **DON'T** spawn a process per tiny task — pickling + startup cost dominates. Batch.

### I/O concurrency → asyncio

```python
import asyncio
async def main():
    async with asyncio.TaskGroup() as tg:   # 3.11+
        tg.create_task(fetch(u)) ...
asyncio.run(main())
```

- **DO** use `asyncio.TaskGroup` (**3.11+**) — structured, cancels siblings on failure, collects errors as an `ExceptionGroup`. On ≤3.10 fall back to `asyncio.gather(..., return_exceptions=...)`.
- **DO** offload blocking calls with `await asyncio.to_thread(fn, ...)` (**3.9+**) so one slow sync call doesn't stall the loop.
- **DON'T** call blocking I/O or `time.sleep` inside a coroutine — it freezes the whole loop. Use `await asyncio.sleep`.
- **DON'T** mix asyncio with CPU-bound loops; hand those to a process pool via `loop.run_in_executor`.

## Free-threaded (no-GIL) build — PEP 703

- **3.13**: experimental free-threaded build ships (`--disable-gil`, binary suffix `t`, e.g. `python3.13t`).
- **3.14**: **officially supported** (PEP 779) and the specializing adaptive interpreter is enabled in it. Still a separate build, not the default download.

```python
import sys, sysconfig
sysconfig.get_config_var("Py_GIL_DISABLED")  # 1 → build supports free threading
sys._is_gil_enabled()                        # runtime state (3.13+)
```

- **DO** feature-detect with the calls above before assuming parallelism; `-X gil=0/1` or `PYTHON_GIL=0/1` overrides at runtime, and importing a C extension not marked free-thread-safe silently re-enables the GIL (with a warning).
- **DON'T** assume free-threaded is faster single-threaded — expect ~5–10% overhead (3.14) and higher memory use.
- **DON'T** ship it to prod without checking your C-extension wheels support it.

## Sub-interpreters — per-interpreter GIL

- **3.12**: per-interpreter GIL (**PEP 684**) — C-API only (`Py_NewInterpreterFromConfig`, `own_gil`).
- **3.14**: exposed to Python via the `concurrent.interpreters` module (**PEP 734**) plus `concurrent.futures.InterpreterPoolExecutor`. True multi-core, isolated state, but slow startup and object sharing is limited (e.g. `memoryview`).
- **DON'T** reference these on ≤3.13 from Python; there was no stdlib module before 3.14.

## Experimental JIT — PEP 744

- **3.13**: copy-and-patch JIT merged, **experimental**, off by default, opt-in at build time. Roughly parity with the specializing interpreter today. Not for production.
- **3.14**: still experimental; now included in Windows/macOS binary releases. Don't depend on it for correctness or speed.

## Baseline speed — you get wins for free

- **3.11**: "Faster CPython" — ~**1.25x** average (10–60% range) over 3.10 via PEP 659 specializing adaptive interpreter. Each release since adds more. Upgrading the interpreter is often the cheapest optimization.

## Profile before optimizing

- **DO** measure first. Micro-bench with `timeit`; profile whole programs with `cProfile` + `pstats` (or `python -m cProfile -s cumtime script.py`).
- **DO** on Linux use `perf` support (**3.12+**): `-X perf`, `PYTHONPERFSUPPORT=1`, or `sys.activate_stack_trampoline("perf")` — makes Python frames visible in `perf` output.
- **DON'T** optimize on a hunch. Confirm the hot line, then act.

## Make the hot path cheap

- **DO** push numeric hot loops into vectorized `numpy` / C extensions — they run outside the GIL and beat Python loops by orders of magnitude.
- **DO** hoist attribute/global lookups out of loops; bind `meth = obj.method` before the loop.
- **DON'T** build large lists you only iterate once — use generators / generator expressions to stream and cap memory.
- **DO** add `__slots__` to hot, high-count classes to drop the per-instance `__dict__` (large memory + faster attribute access). Note it blocks arbitrary attrs and complicates multiple inheritance.
- **DO** prefer built-in/stdlib C paths (`str.join`, `dict`, `collections`, `itertools`, `functools.lru_cache`) over hand-rolled Python.

## Sources

- https://peps.python.org/pep-0703/ — Making the GIL Optional (free-threading, 3.13)
- https://docs.python.org/3/howto/free-threading-python.html — Free-threading HOWTO
- https://peps.python.org/pep-0684/ — Per-Interpreter GIL (3.12)
- https://peps.python.org/pep-0744/ — JIT Compilation (3.13)
- https://docs.python.org/3/whatsnew/3.14.html — PEP 779, `concurrent.interpreters` (PEP 734), forkserver default, tail-call interp
- https://docs.python.org/3/whatsnew/3.11.html — 1.25x speedup, TaskGroup, ExceptionGroup/except*, tomllib
- https://docs.python.org/3/library/multiprocessing.html — start methods, shared_memory
- https://docs.python.org/3/library/concurrent.futures.html — Thread/Process/InterpreterPoolExecutor
- https://docs.python.org/3/library/asyncio-task.html — TaskGroup, to_thread
- https://docs.python.org/3/howto/perf_profiling.html — Linux perf support (3.12)
- https://docs.python.org/3/library/profile.html — cProfile/pstats
