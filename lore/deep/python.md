# Python — deep dive

> On-demand companion to `lore/python.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Language & idioms](#language-and-idioms) · [Type hints & static typing](#typing) · [asyncio & concurrency model](#asyncio) · [Errors & resources](#errors-and-resources) · [Performance, the GIL & concurrency](#performance-and-concurrency) · [Packaging & environments](#packaging-and-envs) · [Testing & tooling](#testing-and-tooling)

## Language & idioms <a id="language-and-idioms"></a>

Terse senior-reviewer checklist. Version markers are load-bearing: never claim a feature
earlier than the release listed. Target may be Python 3.8..3.14 — give modern + fallback.

### Comprehensions & generators
DO use comprehensions for map/filter over a loop that just `.append()`s.
```python
squares = [x*x for x in nums if x % 2 == 0]
by_id = {u.id: u for u in users}
seen = {t.kind for t in tokens}
```
DO use a generator expression (parens, not brackets) for large/streamed data — lazy, O(1) memory.
```python
total = sum(x*x for x in nums)        # no intermediate list
first = next(l for l in lines if l)   # short-circuits
```
DON'T nest more than ~2 `for` clauses — reach for a plain loop when it stops reading left-to-right.
DON'T build a list only to iterate once; pass the generator.

### Unpacking
DO star-unpack and swap without temps; DON'T index (`seq[0]`, `seq[1:]`) when unpacking reads.
```python
first, *rest = seq
head, *mid, tail = seq
a, b = b, a
merged = {**base, **override}   # override wins
combined = [*a, *b]
```

### Dataclasses vs attrs
DO reach for stdlib `@dataclass` (added 3.7) first — no dependency.
```python
from dataclasses import dataclass, field
@dataclass(frozen=True, slots=True)   # slots= added 3.10
class Point:
    x: float
    y: float
    tags: list[str] = field(default_factory=list)  # never mutable default
```
- `frozen=True` → immutable + hashable. `slots=True` (3.10) → less memory, no `__dict__`.
- `kw_only=True` and `KW_ONLY` sentinel: added 3.10. Derive fields in `__post_init__`.
- `field(default_factory=...)` is mandatory for mutable defaults; a bare `[]`/`{}` raises
  `ValueError` at class-definition time (3.11 broadened this to reject any unhashable default).
DO use `attrs` (third-party) only when you need validators/converters, `__slots__` on older
Pythons, or `@define` ergonomics. Otherwise dataclasses are enough.
DON'T hand-roll `__init__`/`__repr__`/`__eq__` for plain data holders.

### Enums
DO subclass `Enum`/`IntEnum`; use `auto()` for values you don't care about.
```python
from enum import Enum, auto
class Color(Enum):
    RED = auto(); GREEN = auto(); BLUE = auto()
```
- `StrEnum` added **3.11** (members are real `str`). Before 3.11 use `class C(str, Enum)`.
- Match on dotted names only (`case Color.RED`) — a bare name is a capture pattern.

### Structural pattern matching (match) — 3.10, PEP 634/635/636
DO use `match` for tagged/shape dispatch; it destructures.
```python
match command.split():
    case ["go", ("north" | "south") as d]:  # OR + AS patterns
        move(d)
    case ["drop", *items]:                   # sequence + star
        drop(items)
    case {"action": a, **rest}:              # mapping; extra keys ignored
        handle(a, rest)
    case Point(x=0, y=0):                    # class pattern (uses __match_args__)
        origin()
    case [x, y] if x == y:                   # guard, checked after binding
        diagonal(x)
    case _:                                   # wildcard, binds nothing
        unknown()
```
DON'T write `case somename:` expecting equality — bare names always capture (shadow), never compare.
DON'T use `match` where a dict lookup or `if/elif` is clearer. Requires 3.10+ — guard with a
version check or fall back to `if/elif`.

### Walrus `:=` — 3.8, PEP 572
DO assign-and-test in one place; DON'T overuse if it hurts readability.
```python
while (chunk := f.read(8192)):
    process(chunk)
if (m := pattern.search(line)) is not None:
    use(m.group(1))
```

### f-strings
DO use f-strings for all interpolation (3.6+). `=` for debug: `f"{value=}"` (3.8+).
```python
f"{name!r} took {elapsed:.2f}s"   # !r conversion, format spec
```
- **3.12 (PEP 701)** formalized the grammar: reuse the same quotes inside, arbitrary nesting,
  multi-line expressions, `#` comments, and backslashes (`f"{'\n'.join(xs)}"`) inside braces.
  On 3.8–3.11 those still raise `SyntaxError` — keep inner quotes different and pre-extract
  backslash strings for portability.
DON'T use `%`-formatting or `.format()` for new code. DON'T f-string log messages that may be
filtered out — use `logger.info("%s", x)` lazy args.

### Context managers
DO use `with` for anything with acquire/release (files, locks, connections).
```python
with open(path, encoding="utf-8") as f:   # always set encoding
    data = f.read()
```
DO group with parentheses (3.10+):
```python
with (open(a) as fa, open(b) as fb):
    ...
```
DO write your own with `@contextlib.contextmanager`; use `contextlib.suppress`, `closing`,
`ExitStack` (dynamic nesting), `chdir` (added **3.11**).
```python
from contextlib import suppress
with suppress(FileNotFoundError):
    os.remove(tmp)
```
DON'T open a file without `with` (leaks the handle).

### pathlib over os.path
DO use `pathlib.Path` — objects, `/` operator, readable methods.
```python
from pathlib import Path
cfg = Path.home() / ".config" / "app.toml"
if cfg.exists():
    text = cfg.read_text(encoding="utf-8")
for py in Path("src").rglob("*.py"):
    ...
```
DON'T stringly-type paths with `os.path.join`/`os.path.exists` in new code. (Most stdlib and
libs accept `Path` directly; wrap in `str()` only at hard boundaries.)

### EAFP over LBYL
DO try the operation and catch the specific failure — avoids TOCTOU races.
```python
try:
    return cache[key]
except KeyError:
    return compute(key)
```
DON'T pre-check with `if key in cache:` then access — racy and slower on the hot path. Reserve
LBYL for genuinely cheap, side-effect-free guards.

### Iterators & itertools
DO use the stdlib building blocks instead of hand-rolled index math.
```python
import itertools as it
it.chain(a, b)            # flatten
it.islice(gen, 10)        # first N of an iterator
it.groupby(sorted(x, key=k), key=k)   # MUST pre-sort by same key
it.pairwise(seq)          # (s0,s1),(s1,s2)...  added 3.10
it.batched(seq, 3)        # fixed-size chunks   added 3.12
zip(a, b, strict=True)    # strict= added 3.10; raises on length mismatch
enumerate(seq, start=1)
```
DON'T re-implement `zip`/`enumerate`/`accumulate` with manual counters.

### Type hints (version-adaptive)
- `list[int]`, `dict[str, int]` built-ins as generics: **3.9** (PEP 585). Before 3.9 import
  `List`/`Dict` from `typing`.
- `X | Y` unions: **3.10** (PEP 604). Before 3.10 use `typing.Optional`/`Union`.
- `type Alias = ...` and `def f[T](...)` / `class C[T]` param syntax: **3.12** (PEP 695).
  Before 3.12 use `TypeVar` + `TypeAlias`.
- `Self` return type: **3.11** (PEP 673). `dict1 | dict2` merge: **3.9** (PEP 584).
DO add `from __future__ import annotations` to defer annotation evaluation on 3.8/3.9.

### Concurrency & tooling facts (do not misdate)
- `asyncio.TaskGroup` and `ExceptionGroup`/`except*`: **3.11** (PEP 654). `tomllib`: **3.11** (PEP 680).
- Free-threaded (no-GIL) build (PEP 703) and the JIT (PEP 744) are **experimental in 3.13**,
  off by default — do not assume they are on.

### Common AI mistakes — DON'T
- DON'T `def f(x=[])` / `def f(x={})` — the default is shared across calls. Use `x=None` then
  `x = [] if x is None else x`, or a dataclass `default_factory`.
- DON'T shadow builtins: `list`, `dict`, `id`, `type`, `input`, `str`, `sum`, `filter`. Rename.
- DON'T write bare `except:` or `except Exception:` swallowing everything — it eats
  `KeyboardInterrupt`/`SystemExit` (bare) and hides bugs. Catch the narrowest type; re-raise or log.
- DON'T mutate a list/dict while iterating it — iterate a copy (`list(d)`) or build a new one.
- DON'T compare with `==` to `None`/`True`/`False` — use `is`.
- DON'T use `assert` for runtime validation — it's stripped under `python -O`.

### Commands
test: `pytest` · lint: `ruff check .` · format: `ruff format .` · type-check: `mypy .`

### Sources
- https://docs.python.org/3/tutorial/
- https://docs.python.org/3/library/dataclasses.html
- https://docs.python.org/3/library/itertools.html
- https://docs.python.org/3/library/contextlib.html
- https://peps.python.org/pep-0636/ (pattern matching tutorial, 3.10)
- https://docs.python.org/3/whatsnew/3.9.html (PEP 585, PEP 584)
- https://docs.python.org/3/whatsnew/3.10.html (PEP 604, PEP 634/635/636)
- https://docs.python.org/3/whatsnew/3.11.html (PEP 654, 673, 680; StrEnum)
- https://docs.python.org/3/whatsnew/3.12.html (PEP 701, PEP 695)
- https://docs.python.org/3/whatsnew/3.13.html (PEP 703, PEP 744 — experimental)
- https://docs.astral.sh/ruff/ · https://docs.pytest.org/ · https://mypy.readthedocs.io/

## Type hints & static typing <a id="typing"></a>

Layers on the base python lore. Type hints are for static checkers (mypy/pyright), not runtime enforcement — CPython does not check them. Verified against docs.python.org, peps.python.org, mypy docs (see Sources). Never claim a feature earlier than the release noted.

### DO — built-in generics & unions (modern baseline)
- DO use built-in generics: `list[int]`, `dict[str, int]`, `tuple[str, ...]`, `type[C]` (PEP 585, **3.9**). Deprecates `typing.List/Dict/Tuple/Type`.
- DO write unions as `X | Y` and optionals as `X | None` (PEP 604, **3.10**). Valid in `isinstance(x, int | str)` too.
- DO import container ABCs from `collections.abc` (`Sequence`, `Mapping`, `Iterable`, `Callable`), not `typing`.
- DON'T use `typing.List`, `typing.Optional[X]`, `typing.Union[X, Y]` in new code — they're the pre-3.9/3.10 fallback only.

Fallback (target ≤3.8): `from typing import List, Dict, Optional, Union` — and add `from __future__ import annotations` so `list[int]` / `X | Y` parse as strings.

### DO — precise types, not `Any`
- DO reach for the narrowest type. `Any` disables checking and is contagious — treat it as "unchecked". Prefer `object` (then narrow) when the type is truly unknown.
- DON'T sprinkle `Any` to silence errors. DON'T leave `# type: ignore` bare — scope it: `# type: ignore[arg-type]`.
- DO annotate every public function signature (params + return). Let locals infer.

### DO — Protocol (structural typing)
- DO define interfaces with `Protocol` (PEP 544, **3.8**) for duck typing — no explicit subclassing needed:
```python
from typing import Protocol
class Reader(Protocol):
    def read(self, n: int) -> bytes: ...
def consume(r: Reader) -> None: ...   # any object with matching read() fits
```
- DO add `@runtime_checkable` only if you need `isinstance` against it (checks method presence, not signatures).
- DON'T reach for a nominal ABC when a Protocol expresses the contract without coupling.

### DO — TypedDict, Literal, Final, Annotated
- DO type dict-shaped payloads with `TypedDict` (**3.8**). Mark optional keys with `NotRequired`, mandatory-in-`total=False` with `Required` (PEP 655, **3.11**); `ReadOnly` (PEP 705, **3.13**).
```python
from typing import TypedDict, NotRequired
class User(TypedDict):
    id: int
    name: str
    nickname: NotRequired[str]
```
- DO constrain to exact values with `Literal["r","w"]` (PEP 586, **3.8**).
- DO mark constants `Final` (PEP 591, **3.8**): `MAX: Final = 100`.
- DO attach metadata with `Annotated[int, Gt(0)]` (PEP 593, **3.9**) — used by pydantic/FastAPI; type checkers see the first arg.
- DON'T model a fixed-key record as `dict[str, Any]` — use `TypedDict` or a `@dataclass`.

### DO — generics
- DO use PEP 695 syntax on **3.12+** — no `TypeVar` import, no `Generic` base:
```python
def first[T](xs: list[T]) -> T: ...
class Box[T]:
    def __init__(self, v: T) -> None: self.v = v
type IntBox = Box[int]                 # `type` statement → TypeAliasType, lazily evaluated
```
- DO use `TypeVar` defaults (PEP 696, **3.13**): `class Box[T = int]: ...`.
- Fallback (≤3.11): classic `TypeVar` + `Generic`:
```python
from typing import TypeVar, Generic
T = TypeVar("T")
class Box(Generic[T]):
    def __init__(self, v: T) -> None: self.v = v
```
- DON'T mix a naked `TypeVar` used once — that's just `object`/`Any` in disguise; a TypeVar must appear ≥2 times to relate inputs/outputs.

### DO — Self & overload
- DO return `Self` (PEP 673, **3.11**) for fluent builders / `__enter__` / alternative constructors — not the concrete class name (breaks subclasses):
```python
from typing import Self
class Q:
    def where(self, c: str) -> Self: ...   # subclass returns subclass
```
- Fallback (≤3.10): a bound `TypeVar("T", bound="Q")`.
- DO use `@overload` (**3.5**) for signatures whose return type depends on argument types; the implementation follows unannotated-to-callers:
```python
from typing import overload
@overload
def get(k: str) -> str: ...
@overload
def get(k: str, default: T) -> str | T: ...
def get(k, default=None): ...
```
- DON'T write overloads that a single union return already expresses.

### DO — narrowing helpers
- DO end unreachable branches with `assert_never(x)` (**3.11**) for exhaustive `match`/`if` over unions/Literals — a missed case becomes a type error.
- DO use `Never`/`NoReturn` for functions that never return (`Never` **3.11**, `NoReturn` 3.6.2).
- DO use `@override` (PEP 698, **3.12**) on methods meant to override a base — catches renamed/removed parents.
- DO debug with `reveal_type(x)` (**3.11**; checkers understand it without import).

### DON'T — annotation runtime pitfalls
- DON'T assume annotations are evaluated eagerly. Add `from __future__ import annotations` (PEP 563, **3.7**) to defer them to strings → forward refs work without quotes, no import-time cost. Read them via `typing.get_type_hints()`.
- Note: **3.14** makes deferred (lazy) annotations the default via PEP 649 — inspect through the new `annotationlib` (behavior differs from PEP 563 stringification).
- DON'T use `typing.TypeAlias` on 3.12+ — deprecated in favor of the `type` statement. Old alias: `Vector: TypeAlias = list[float]`.

### DO — enforce in CI (types are worthless unchecked)
- DO run a checker on every PR. mypy: `mypy --strict src/` (bundles `disallow-untyped-defs`, `warn-return-any`, `warn-unused-ignores`, `strict-equality`, …). Or pyright: `pyright`.
- DO configure in `pyproject.toml`:
```toml
[tool.mypy]
strict = true
warn_unused_ignores = true
```
- DO gate: fail CI on any error. DON'T let `# type: ignore` accumulate — `warn_unused_ignores` prunes stale ones.
- DON'T rely on hints at runtime for validation — use pydantic/attrs if you need enforced data. Hints alone are advisory.

### Version cue
3.7 `from __future__ import annotations` · 3.8 Protocol/TypedDict/Literal/Final · 3.9 `list[int]`/Annotated · 3.10 `X|Y`/`X|None` · 3.11 Self/Required·NotRequired/assert_never/Never · 3.12 PEP 695 `class C[T]`+`type` statement/@override · 3.13 TypeVar defaults/ReadOnly · 3.14 PEP 649 lazy annotations default.

### Sources
- https://docs.python.org/3/library/typing.html
- https://peps.python.org/pep-0585/ (built-in generics, 3.9)
- https://peps.python.org/pep-0604/ (X|Y unions, 3.10)
- https://peps.python.org/pep-0695/ (type params + `type` statement, 3.12)
- https://mypy.readthedocs.io/en/stable/command_line.html
- https://docs.python.org/3/reference/simple_stmts.html (PEP 563/649 annotations)

## asyncio & concurrency model <a id="asyncio"></a>

Lore for an AI agent writing async Python. Terse, version-adaptive. Assume the reader targets some Python in 3.8..3.14. Give the modern form AND the fallback; never claim a feature earlier than the release that shipped it.

`async`/`await` syntax: PEP 492, Python 3.5. Async generators: PEP 525, Python 3.6. One event loop runs per thread; while a Task runs, no other Task runs until it hits an `await` suspension point.

### Entrypoint — asyncio.run

DO
- Use `asyncio.run(main())` as the single top-level entrypoint (added 3.7). It creates a fresh loop, runs the coroutine, and closes the loop.
- `loop_factory=` param exists since 3.12 if you must configure the loop. In the `python -m asyncio` REPL, `await` directly — no `run()`.

DON'T
- DON'T call `asyncio.run()` more than once or from inside a running loop — it raises `RuntimeError`.
- DON'T reach for `loop.run_until_complete()` / `get_event_loop()` / manual loop management in new code. Those are low-level, library-author APIs.
- DON'T rely on the deprecated policy system — it is slated for removal in 3.16.

### await vs create_task — concurrency is opt-in

DO
- Directly `await coro()` when you need the result *now*, sequentially.
- Use `asyncio.create_task(coro)` (3.7) to start work concurrently; `await` the task later. This is the only way multiple coroutines make progress together.
- Keep a strong reference to every task (`tasks = [...]` or a set). The loop holds only weak refs; an un-referenced task can be GC'd mid-flight.

DON'T
- DON'T assume `await a(); await b()` runs concurrently — it does not. It is strictly sequential.
- DON'T fire-and-forget without storing the task object.

### Structured concurrency — TaskGroup (3.11+) over gather

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

### Timeouts — asyncio.timeout (3.11+) vs wait_for

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

### Never block the loop

A single blocking/CPU-bound call stalls **every** Task and I/O on that loop's thread until it returns.

DO
- Offload blocking work: `await asyncio.to_thread(fn, *args)` (added 3.9) for the simple case.
- For a specific executor, `await loop.run_in_executor(executor, fn, *args)`; use a `ProcessPoolExecutor` for CPU-bound work (threads won't help under the GIL).
- Use async-native libraries for I/O (`aiohttp`/`httpx`, async DB drivers) inside coroutines.

DON'T
- DON'T call `time.sleep()`, `requests.get()`, blocking file/DB I/O, or heavy CPU loops directly in a coroutine. Use `asyncio.sleep()` and async clients.
- DON'T do blocking network logging on the loop thread.
- Note: `to_thread` is bounded by the GIL, so it is for I/O-bound work — not CPU parallelism (3.13 ships an *experimental* free-threaded build; don't assume it).

### Cancellation

`asyncio.CancelledError` subclasses `BaseException` (not `Exception`), so bare `except Exception` won't swallow it.

DO
- Clean up with `try/finally` around `await` points.
- If you catch `CancelledError` for cleanup, **re-raise it** — suppressing it breaks cancellation.
- Task-level introspection since 3.11: `Task.cancelling()`, `Task.uncancel()`; `cancel(msg=...)` message propagated since 3.11.
- Protect a critical awaitable from outer cancellation with `asyncio.shield(aw)` (keep a strong ref to it).

DON'T
- DON'T write `except:` or `except BaseException:` that eats `CancelledError`.
- DON'T assume `task.cancel()` guarantees the task stops — it requests cancellation at the next suspension; the coroutine can still finish.

### Async context managers & iterators

DO
- `async with` / `async for` require `__aenter__/__aexit__` and `__anext__`. Write reusable managers with `@contextlib.asynccontextmanager` (added 3.7).
- Use `contextlib.AsyncExitStack` (3.7) to compose a dynamic number of async managers; `contextlib.aclosing()` (3.10) to guarantee `aclose()` on async generators.

DON'T
- DON'T use plain `with`/`for` on async resources — the setup/teardown coroutines won't be awaited.
- DON'T leak async generators — close them (`aclosing`) so their `finally` runs on the loop.

### Version cheat-sheet (verified against docs.python.org)

- 3.7 — `asyncio.run`, `create_task`, `current_task`, `asynccontextmanager`, `AsyncExitStack`.
- 3.9 — `asyncio.to_thread`; `cancel(msg=)`.
- 3.10 — `wait_for`/`gather`/`shield` drop the `loop=` param; `aclosing`; `X | Y` unions; `match`.
- 3.11 — `TaskGroup`, `asyncio.timeout`/`timeout_at`, `Runner`, `Task.uncancel/cancelling`; `ExceptionGroup`/`except*` (PEP 654); `wait_for` raises builtin `TimeoutError`. Built-in generics `list[int]` since 3.9.
- 3.12 — `run(loop_factory=)`; eager task factory; PEP 695 type params.
- 3.13 — experimental free-threading (no-GIL) build; experimental JIT.
- 3.14 — `run`/`Runner.run` accept any awaitable; `create_task(eager_start=)`.

### Sources

- https://docs.python.org/3/library/asyncio.html
- https://docs.python.org/3/library/asyncio-task.html
- https://docs.python.org/3/library/asyncio-runner.html
- https://docs.python.org/3/library/asyncio-dev.html
- https://docs.python.org/3/library/contextlib.html
- https://peps.python.org/pep-0492/

## Errors & resources <a id="errors-and-resources"></a>

Exception handling and deterministic cleanup. Version cues: `ExceptionGroup`/`except*` and `Exception.add_note()` are **3.11+** (PEP 654 / PEP 678); parenthesized multiple context managers are **3.10+**.

### DO — exceptions
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

### DO — concurrent / multiple errors (3.11+)
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

### DO — resources & cleanup
- Manage every external resource (files, sockets, locks, DB sessions) with a **context manager** (`with`), not manual `open`/`close` in `try/finally`.
- Multiple resources: parenthesized form (3.10+) `with (open(a) as f, open(b) as g):` — before 3.10 use nested `with` or `contextlib.ExitStack`.
- `contextlib` toolkit: `@contextmanager` (write one from a generator), `ExitStack` (dynamic/variable number of resources), `suppress(FileNotFoundError)` (intentional ignore), `closing(x)` (wrap `.close()`-only objects), `chdir` (3.11+).

```python
from contextlib import ExitStack
with ExitStack() as stack:
    files = [stack.enter_context(open(p)) for p in paths]   # all closed on exit
```

### DON'T
- DON'T write a bare `except:` or `except BaseException:` — they swallow `KeyboardInterrupt`/`SystemExit`. Catch `Exception` at most, and only where you can handle it.
- DON'T swallow silently (`except Exception: pass`). At minimum `logger.exception("...")` (records the traceback) — but don't log *and* re-raise the same error at every level (double logging).
- DON'T use exceptions for ordinary control flow in hot paths (raising is cheap to set up, costly when thrown en masse).
- DON'T `return` inside `finally` — it silently discards a propagating exception.
- DON'T catch an exception only to `raise Exception(str(e))` — you lose the type and traceback; re-raise (`raise`) or chain (`raise ... from e`).
- DON'T rely on `__del__` for cleanup — its timing is not guaranteed; use `with`/`close()`.

### Sources
- https://docs.python.org/3/tutorial/errors.html
- https://docs.python.org/3/library/exceptions.html
- https://docs.python.org/3/library/contextlib.html
- https://peps.python.org/pep-0654/ (Exception Groups & `except*`, 3.11)
- https://peps.python.org/pep-0678/ (`add_note()`, 3.11)

## Performance, the GIL & concurrency <a id="performance-and-concurrency"></a>

Lore for an AI agent. Terse, version-adaptive (assume reader is on 3.8–3.14). Measure before you optimize. Verify feature availability at runtime, not from memory.

### The GIL — what it actually constrains

One lock per interpreter serializes bytecode execution: only one thread runs Python at a time in a standard CPython build. It is released around blocking I/O and inside many C extensions (numpy, `hashlib`, `zlib`).

- **DO** reach for threads when the bottleneck is I/O (network, disk, DB) — the GIL is dropped during the wait.
- **DON'T** expect threads to speed up pure-Python CPU work in a GIL build; you get concurrency, not parallelism.
- **DON'T** confuse the GIL with thread-safety. `+=`, `dict`/`list` mutation from multiple threads still needs `threading.Lock`. Even the free-threaded build advises explicit locks, not relying on built-in-type internal locks.

### Pick the right concurrency model

| Workload | Use | Module |
|---|---|---|
| I/O-bound, blocking libs | threads | `concurrent.futures.ThreadPoolExecutor` |
| I/O-bound, high fan-out | asyncio | `asyncio` |
| CPU-bound | processes | `concurrent.futures.ProcessPoolExecutor` / `multiprocessing` |
| CPU-bound, share large arrays | processes + shared mem | `multiprocessing.shared_memory` |

- **DO** default to the `concurrent.futures` executors; the `Executor` API is the same for threads and processes, so switching is a one-line change.
- **DON'T** hand-roll `threading.Thread` pools when a pool executor does it.

#### CPU-bound → multiprocessing

```python
from concurrent.futures import ProcessPoolExecutor
with ProcessPoolExecutor() as ex:
    results = list(ex.map(cpu_fn, items))
```

- **DO** know the start method: macOS/Windows default to `spawn` (macOS since 3.8). On POSIX the default changed `fork` → `forkserver` in **3.14**; `fork` is no longer the default anywhere. `fork` in a multithreaded parent is unsafe.
- **DO** guard entry points: `if __name__ == "__main__":` is mandatory with `spawn`/`forkserver` or children re-import and re-run module code.
- **DO** keep payloads picklable and small; every arg/result is pickled across the process boundary. For big arrays use `multiprocessing.shared_memory` (3.8+) or memory-map.
- **DON'T** spawn a process per tiny task — pickling + startup cost dominates. Batch.

#### I/O concurrency → asyncio

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

### Free-threaded (no-GIL) build — PEP 703

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

### Sub-interpreters — per-interpreter GIL

- **3.12**: per-interpreter GIL (**PEP 684**) — C-API only (`Py_NewInterpreterFromConfig`, `own_gil`).
- **3.14**: exposed to Python via the `concurrent.interpreters` module (**PEP 734**) plus `concurrent.futures.InterpreterPoolExecutor`. True multi-core, isolated state, but slow startup and object sharing is limited (e.g. `memoryview`).
- **DON'T** reference these on ≤3.13 from Python; there was no stdlib module before 3.14.

### Experimental JIT — PEP 744

- **3.13**: copy-and-patch JIT merged, **experimental**, off by default, opt-in at build time. Roughly parity with the specializing interpreter today. Not for production.
- **3.14**: still experimental; now included in Windows/macOS binary releases. Don't depend on it for correctness or speed.

### Baseline speed — you get wins for free

- **3.11**: "Faster CPython" — ~**1.25x** average (10–60% range) over 3.10 via PEP 659 specializing adaptive interpreter. Each release since adds more. Upgrading the interpreter is often the cheapest optimization.

### Profile before optimizing

- **DO** measure first. Micro-bench with `timeit`; profile whole programs with `cProfile` + `pstats` (or `python -m cProfile -s cumtime script.py`).
- **DO** on Linux use `perf` support (**3.12+**): `-X perf`, `PYTHONPERFSUPPORT=1`, or `sys.activate_stack_trampoline("perf")` — makes Python frames visible in `perf` output.
- **DON'T** optimize on a hunch. Confirm the hot line, then act.

### Make the hot path cheap

- **DO** push numeric hot loops into vectorized `numpy` / C extensions — they run outside the GIL and beat Python loops by orders of magnitude.
- **DO** hoist attribute/global lookups out of loops; bind `meth = obj.method` before the loop.
- **DON'T** build large lists you only iterate once — use generators / generator expressions to stream and cap memory.
- **DO** add `__slots__` to hot, high-count classes to drop the per-instance `__dict__` (large memory + faster attribute access). Note it blocks arbitrary attrs and complicates multiple inheritance.
- **DO** prefer built-in/stdlib C paths (`str.join`, `dict`, `collections`, `itertools`, `functools.lru_cache`) over hand-rolled Python.

### Sources

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

## Packaging & environments <a id="packaging-and-envs"></a>

`pyproject.toml` is the single config file (PEP 621 `[project]` metadata + PEP 517/518 `[build-system]`). `uv` is the modern default toolchain; `pip`+`venv` is the always-available baseline. Never install into system Python; never commit code without a lockfile.

### DO — modern default (uv)
- DO use `uv` — one Rust tool replacing `pip`, `pip-tools`, `pipx`, `poetry`, `pyenv`, `virtualenv`, `twine`. It manages the interpreter, the `.venv`, and the lockfile.
- DO scaffold with `uv init` (app) / `uv init --package` (distributable, wires the `uv_build` backend). It writes `pyproject.toml` + `.python-version`.
- DO add deps with `uv add httpx` (writes to `[project].dependencies` with a bound + updates `uv.lock`); remove with `uv remove`. Constrain inline: `uv add "httpx>=0.27"`.
- DO run everything through `uv run <cmd>` — it auto-locks and auto-syncs the env first, so it is always current. No manual activate needed.
- DO commit `uv.lock` (a universal, cross-platform lockfile). In CI use `uv sync --locked` (errors if the lock is stale) or `--frozen` (use lock as-is, no check).
- DO refresh explicitly: `uv lock --upgrade` (uv never auto-upgrades on new releases). Verify with `uv lock --check`.
- DO manage interpreters with uv: `uv python install 3.12`, `uv python pin 3.12`.

### DO — baseline (pip + venv), no uv
- DO create/activate a venv (stdlib `venv`, Python 3.3+):
  ```bash
  python -m venv .venv
  source .venv/bin/activate      # Windows: .venv\Scripts\activate
  python -m pip install -U pip
  ```
- DO invoke pip as `python -m pip` (targets the active interpreter unambiguously).
- DO pin transitively. `pip freeze > requirements.txt` captures the flat set; better, use `pip-tools`: hand-author `requirements.in`, compile `pip-compile` → hashed `requirements.txt`, install `pip-sync`. Commit the compiled file.
- DO recreate venvs, never move/copy them (shebangs hold absolute paths). Since Python 3.13 `venv` writes a `.gitignore` automatically.

### DON'T
- DON'T `pip install` into system/OS Python or globally. Always a venv (or `uv`/`pipx`). On externally-managed distros pip refuses this by default (PEP 668) — respect it, don't `--break-system-packages`.
- DON'T commit `.venv/` — it's disposable and non-portable.
- DON'T ship an app without a committed lockfile (`uv.lock` / `poetry.lock` / compiled `requirements.txt`). Loose ranges = non-reproducible builds.
- DON'T hand-edit `uv.lock`. Regenerate via `uv lock`/`uv add`.
- DON'T use bare `requirements.txt` from `pip freeze` as your source of truth — it flattens direct vs. transitive and loses intent.

### pyproject.toml — the contract
```toml
[project]                                   # PEP 621, static metadata
name = "mypkg"
version = "0.1.0"                            # or: dynamic = ["version"]
requires-python = ">=3.9"
dependencies = ["httpx>=0.27", "rich"]      # PEP 508 specifiers

[project.optional-dependencies]             # extras: published, install via mypkg[plot]
plot = ["matplotlib"]

[project.scripts]                           # console entry point
mycli = "mypkg.cli:main"

[dependency-groups]                         # PEP 735 (Final, 2024), local-only, NOT published
dev = ["pytest", "mypy", "ruff"]
lint = ["ruff"]
test = ["pytest", {include-group = "lint"}] # groups can include other groups

[build-system]                              # PEP 518 requires + PEP 517 backend
requires = ["hatchling"]
build-backend = "hatchling.build"
```
- Extras (`optional-dependencies`) vs. dependency groups (`[dependency-groups]`): extras are **published** package metadata and require building a dist; groups are **dev-time only**, never appear in the wheel/sdist, and work for non-package projects. Use groups for test/lint/typecheck tooling.
- uv maps `uv add --dev X` → `dev` group; `uv add --group lint X` → named group; `uv sync` includes `dev` by default (`--no-dev` / `--only-group` / `--all-groups` to control). The legacy `[tool.uv] dev-dependencies` is deprecated — use `[dependency-groups]`.

### Build backends (PEP 517)
Choose one; declared in `[build-system]`:
- `hatchling` → `hatchling.build` — modern, common default.
- `setuptools` → `setuptools.build_meta` — legacy/extension modules (C).
- `flit_core` → `flit_core.buildapi` — minimal pure-Python.
- `pdm-backend` → `pdm.backend`.
- `uv_build` → `"uv_build"` — uv's own, fast, **pure-Python only** (use hatchling/setuptools for native extensions).

### Editable installs (dev the package while it changes)
- uv: `uv add --editable ./libs/foo`, or `uv pip install -e .`. Workspace members are editable by default.
- pip: `pip install -e .` (installs a `.pth` link; source edits take effect without reinstall).

### Poetry (alternative)
- `poetry init` / `poetry add pkg` / `poetry install`; lock in `poetry.lock` (commit it); `poetry run <cmd>`.
- Modern Poetry (2.x) reads standard PEP 621 `[project]`; older configs used `[tool.poetry]` tables. Prefer standard `[project]` for portability.

### Reading pyproject.toml in code
- Python 3.11+: stdlib `tomllib` (read-only, open file `"rb"`). Older: `tomli` (same API). Compat shim:
  ```python
  try:
      import tomllib          # 3.11+
  except ModuleNotFoundError:
      import tomli as tomllib # <=3.10
  ```

### Version cues
- `venv` stdlib 3.3+; auto-`.gitignore` in the venv 3.13+.
- `tomllib` stdlib 3.11+ (else `tomli`).
- PEP 668 externally-managed-environment marker (system pip refuses global installs) — mainstream since ~2023 (Python 3.11+ era distros).
- PEP 735 dependency groups — Final Oct 2024; needs current uv / pip 25.1+ (`pip install --group`) / tooling that adopted it.
- `requires-python` gates installs — set it to your real floor (3.9..3.14).

Commands: setup `uv sync` (or `python -m venv .venv && pip install -e ".[dev]"`); add dep `uv add X`; lock check `uv lock --check`; run `uv run pytest`.

### Sources
- https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- https://packaging.python.org/en/latest/specifications/pyproject-toml/
- https://packaging.python.org/en/latest/tutorials/managing-dependencies/
- https://peps.python.org/pep-0621/
- https://peps.python.org/pep-0735/
- https://docs.astral.sh/uv/
- https://docs.astral.sh/uv/concepts/projects/dependencies/
- https://docs.astral.sh/uv/concepts/projects/sync/
- https://docs.astral.sh/uv/concepts/build-backend/
- https://docs.python.org/3/library/venv.html
- https://docs.python.org/3/library/tomllib.html

## Testing & tooling <a id="testing-and-tooling"></a>

Modern stack (2026): **pytest** for tests, **ruff** for lint+format, **mypy** or **pyright** for types, **coverage.py** for coverage, **nox/tox** for matrices, **pre-commit** for gates. Prefer these over stdlib `unittest` boilerplate when they are available.

Current versions: pytest 9.x, ruff 0.15.x, mypy 2.x, pyright 1.1.x, coverage 7.15.x, tox 4.x, nox, pre-commit 4.x. Version floors matter: pytest 9, mypy 2, coverage 7.15, tox, nox, and pre-commit all require **Python 3.10+**. On Python 3.9 pin `pytest<9` and `mypy<2`; Python 3.8 is EOL and needs older still (`pytest<8.4` — 8.4 dropped 3.8). ruff and pyright run on 3.7+.

### pytest

DO
- Write plain functions named `test_*` with bare `assert`; pytest rewrites asserts to show rich diffs. No `self.assertEqual`.
- Use **fixtures** for setup/teardown. `yield` splits setup from teardown; the code after `yield` runs even if the test fails.
- Scope fixtures: `@pytest.fixture(scope="function"|"class"|"module"|"session")`. Default is `function`.
- Put shared fixtures in **`conftest.py`** — auto-discovered up the directory tree, no import needed.
- Parametrize with `@pytest.mark.parametrize("a,b,expected", [(1,2,3),(4,5,9)])`; add `ids=...` for readable case names. Stack decorators for a cross product.
- Use built-in fixtures: **`tmp_path`** (a `pathlib.Path`, per-test temp dir), `tmp_path_factory` (session scope), `capsys`/`capfd` (capture output), `caplog` (assert log records).
- Use **`monkeypatch`** for scoped patching — auto-undone: `setattr`, `setenv`, `delenv(raising=False)`, `setitem`, `chdir`, `syspath_prepend`.
- Assert exceptions with the context manager and a regex: `with pytest.raises(ValueError, match="bad input"):`. Inspect via `excinfo.value`.
- Register custom markers in config (`[tool.pytest.ini_options] markers=[...]`) to avoid `PytestUnknownMarkWarning`; select with `pytest -m "slow and not flaky"`.
- Configure once in `pyproject.toml` under `[tool.pytest.ini_options]` (`testpaths`, `addopts`, `markers`).

DON'T
- Don't share mutable state across tests via module globals — use a fresh fixture.
- Don't `os.chdir`/`os.environ[...]=` manually — use `monkeypatch` so it's reverted.
- Don't write to the repo tree or `/tmp` by hand — use `tmp_path`.
- Don't put a bare `pytest.raises(Exception)` with no `match` — it hides the wrong error.
- Don't overuse `autouse=True` fixtures; they run everywhere and hide dependencies.

```python
import pytest

@pytest.fixture
def client(tmp_path):
    db = tmp_path / "test.db"
    c = make_client(db)
    yield c
    c.close()                      # teardown after yield

@pytest.mark.parametrize("n,expected", [(0, 1), (5, 120)], ids=["zero", "five"])
def test_factorial(n, expected):
    assert factorial(n) == expected

def test_rejects_negative():
    with pytest.raises(ValueError, match="negative"):
        factorial(-1)

def test_env(monkeypatch):
    monkeypatch.setenv("MODE", "test")
    assert load_config().mode == "test"
```

### ruff — one tool for lint + format

DO
- Use `ruff` to replace black + flake8 + isort + pyupgrade (and dozens of plugins) — 10–100x faster.
- Lint: `ruff check .`  ·  auto-fix: `ruff check --fix .`  ·  format: `ruff format .`.
- CI-safe format check: `ruff format --check .`.
- Configure in `pyproject.toml`; set `target-version` so pyupgrade/syntax rules match your floor.

```toml
[tool.ruff]
line-length = 88
target-version = "py310"          # gate rules to your minimum Python

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]  # pycodestyle, pyflakes, isort, pyupgrade, bugbear
ignore = ["E501"]                    # line length handled by formatter
```

DON'T
- Don't run black/isort/flake8 alongside ruff — redundant and conflicting. Pick ruff.
- Don't hand-sort imports — ruff's `I` rules do it.
- Don't skip `target-version`; without it `UP` rules may rewrite to syntax your runtime lacks.

### Types — mypy or pyright

DO
- Type public functions; run `mypy .` or `pyright` in CI. Start lax, ratchet up.
- Enable strictness gradually: `[tool.mypy] strict = true` (or per-flag) once clean.
- Match `python_version` to your floor so version-specific type checks apply.

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_unused_ignores = true
```

DON'T
- Don't sprinkle `# type: ignore` without a code — use `# type: ignore[arg-type]`.
- Don't use pre-3.9 `typing.List/Dict/Optional` on new code when your floor allows built-ins (see version notes).

### coverage.py

DO
- Run through coverage: `coverage run -m pytest` then `coverage report -m` (`-m` shows missing lines); `coverage html` for `htmlcov/`.
- Enable **branch coverage** and fail-under threshold in config.

```toml
[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
show_missing = true
fail_under = 85
```

DON'T
- Don't chase 100% — assert branches and error paths, not trivial getters.
- `pytest-cov` (`pytest --cov=src`) is convenient but usually unnecessary; plain `coverage run -m pytest` works.

### Matrices — nox / tox

DO
- Use **tox** (declarative, `tox.ini`/`pyproject.toml`) or **nox** (Python-scripted `noxfile.py`) to test across interpreters/deps.
- Reserve them for real matrices; a single-env project just runs `pytest`.

```python
# noxfile.py
import nox
@nox.session(python=["3.10", "3.11", "3.12", "3.13"])
def tests(session):
    session.install(".[test]")
    session.run("pytest")
```

### pre-commit

DO
- Add a `.pre-commit-config.yaml` with ruff (lint + format) hooks; run `pre-commit install` once, `pre-commit run --all-files` to backfill. Pin `rev:` to a released tag.

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.21
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

DON'T
- Don't leave `rev:` unpinned or floating — reproducibility breaks.

### Version-adaptive reminders (affect type hints & syntax in tests)

- **3.9**: built-in generics `list[int]`, `dict[str, int]` (no `typing.List`).
- **3.10**: `X | Y` unions (`int | None` over `Optional[int]`), structural `match`.
- **3.11**: `ExceptionGroup`/`except*`, `asyncio.TaskGroup`, `tomllib` (read TOML config without a dep). pytest 8+ supports asserting `ExceptionGroup`.
- **3.12**: PEP 695 `type` aliases and `def f[T](...)` generics; improved f-string grammar.
- **3.13**: experimental free-threaded (no-GIL) build and experimental JIT — coverage 7.15 supports free-threading; expect flakier third-party support.
Give the modern form when the target allows it, the older fallback otherwise — never emit syntax newer than the project's `target-version`/`python_version`.

### Sources
- pytest — https://docs.pytest.org/en/stable/
- pytest monkeypatch — https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- ruff — https://docs.astral.sh/ruff/
- ruff configuration — https://docs.astral.sh/ruff/configuration/
- coverage.py — https://coverage.readthedocs.io/en/latest/
- mypy — https://mypy.readthedocs.io/en/stable/
- pyright — https://microsoft.github.io/pyright/
- nox — https://nox.thea.codes/  · tox — https://tox.wiki/
- pre-commit — https://pre-commit.com/  · ruff-pre-commit — https://github.com/astral-sh/ruff-pre-commit
- PyPI release metadata (versions/requires-python) — https://pypi.org/
- Python version features — https://docs.python.org/3/whatsnew/  · PEP 695 — https://peps.python.org/pep-0695/
