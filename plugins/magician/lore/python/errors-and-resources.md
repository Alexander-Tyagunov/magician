# Python — Errors & resources

Exception handling and deterministic cleanup. Version cues: `ExceptionGroup`/`except*` and `Exception.add_note()` are **3.11+** (PEP 654 / PEP 678); parenthesized multiple context managers are **3.10+**.

## DO — exceptions
- Raise the **most specific** built-in or a small custom exception subclass of `Exception` (never subclass `BaseException` directly). Group a library's errors under one base class so callers can catch the family.
- Chain with `raise NewError(...) from err` to set `__cause__` (shows "The above exception was the direct cause…"); use `from None` to deliberately suppress a noisy context.
- Prefer **EAFP** (`try: d[k] except KeyError:`) over LBYL (`if k in d:`) — avoids races and is idiomatic.
- Use `try/except/else/finally` precisely: put the *risky* call in `try`, the *success-only* code in `else`, cleanup in `finally` (runs even on `return`/exception).
- Attach context on the way up with `err.add_note("while parsing config")` (3.11+) instead of wrapping just to add a string.

```python
try:
    cfg = load(path)
except FileNotFoundError as e:
    raise ConfigError(f"missing config: {path}") from e
```

## DO — concurrent / multiple errors (3.11+)
- `asyncio.TaskGroup` and other concurrent APIs raise an **`ExceptionGroup`**. Catch subsets with `except*`:

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(a()); tg.create_task(b())
except* ValueError as eg:      # eg.exceptions holds the matching leaves
    handle(eg)
except* (OSError, TimeoutError) as eg:
    retry(eg)
```
- Pre-3.11: backport via the `exceptiongroup` PyPI package, or collect errors into a list yourself.

## DO — resources & cleanup
- Manage every external resource (files, sockets, locks, DB sessions) with a **context manager** (`with`), not manual `open`/`close` in `try/finally`.
- Multiple resources: parenthesized form (3.10+) `with (open(a) as f, open(b) as g):` — before 3.10 use nested `with` or `contextlib.ExitStack`.
- `contextlib` toolkit: `@contextmanager` (write one from a generator), `ExitStack` (dynamic/variable number of resources), `suppress(FileNotFoundError)` (intentional ignore), `closing(x)` (wrap `.close()`-only objects), `chdir` (3.11+).

```python
from contextlib import ExitStack
with ExitStack() as stack:
    files = [stack.enter_context(open(p)) for p in paths]   # all closed on exit
```

## DON'T
- DON'T write a bare `except:` or `except BaseException:` — they swallow `KeyboardInterrupt`/`SystemExit`. Catch `Exception` at most, and only where you can handle it.
- DON'T swallow silently (`except Exception: pass`). At minimum `logger.exception("...")` (records the traceback) — but don't log *and* re-raise the same error at every level (double logging).
- DON'T use exceptions for ordinary control flow in hot paths (raising is cheap to set up, costly when thrown en masse).
- DON'T `return` inside `finally` — it silently discards a propagating exception.
- DON'T catch an exception only to `raise Exception(str(e))` — you lose the type and traceback; re-raise (`raise`) or chain (`raise ... from e`).
- DON'T rely on `__del__` for cleanup — its timing is not guaranteed; use `with`/`close()`.

## Sources
- https://docs.python.org/3/tutorial/errors.html
- https://docs.python.org/3/library/exceptions.html
- https://docs.python.org/3/library/contextlib.html
- https://peps.python.org/pep-0654/ (Exception Groups & `except*`, 3.11)
- https://peps.python.org/pep-0678/ (`add_note()`, 3.11)
