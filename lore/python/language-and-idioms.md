# Python — Language & idioms

Terse senior-reviewer checklist. Version markers are load-bearing: never claim a feature
earlier than the release listed. Target may be Python 3.8..3.14 — give modern + fallback.

## Comprehensions & generators
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

## Unpacking
DO star-unpack and swap without temps; DON'T index (`seq[0]`, `seq[1:]`) when unpacking reads.
```python
first, *rest = seq
head, *mid, tail = seq
a, b = b, a
merged = {**base, **override}   # override wins
combined = [*a, *b]
```

## Dataclasses vs attrs
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

## Enums
DO subclass `Enum`/`IntEnum`; use `auto()` for values you don't care about.
```python
from enum import Enum, auto
class Color(Enum):
    RED = auto(); GREEN = auto(); BLUE = auto()
```
- `StrEnum` added **3.11** (members are real `str`). Before 3.11 use `class C(str, Enum)`.
- Match on dotted names only (`case Color.RED`) — a bare name is a capture pattern.

## Structural pattern matching (match) — 3.10, PEP 634/635/636
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

## Walrus `:=` — 3.8, PEP 572
DO assign-and-test in one place; DON'T overuse if it hurts readability.
```python
while (chunk := f.read(8192)):
    process(chunk)
if (m := pattern.search(line)) is not None:
    use(m.group(1))
```

## f-strings
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

## Context managers
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

## pathlib over os.path
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

## EAFP over LBYL
DO try the operation and catch the specific failure — avoids TOCTOU races.
```python
try:
    return cache[key]
except KeyError:
    return compute(key)
```
DON'T pre-check with `if key in cache:` then access — racy and slower on the hot path. Reserve
LBYL for genuinely cheap, side-effect-free guards.

## Iterators & itertools
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

## Type hints (version-adaptive)
- `list[int]`, `dict[str, int]` built-ins as generics: **3.9** (PEP 585). Before 3.9 import
  `List`/`Dict` from `typing`.
- `X | Y` unions: **3.10** (PEP 604). Before 3.10 use `typing.Optional`/`Union`.
- `type Alias = ...` and `def f[T](...)` / `class C[T]` param syntax: **3.12** (PEP 695).
  Before 3.12 use `TypeVar` + `TypeAlias`.
- `Self` return type: **3.11** (PEP 673). `dict1 | dict2` merge: **3.9** (PEP 584).
DO add `from __future__ import annotations` to defer annotation evaluation on 3.8/3.9.

## Concurrency & tooling facts (do not misdate)
- `asyncio.TaskGroup` and `ExceptionGroup`/`except*`: **3.11** (PEP 654). `tomllib`: **3.11** (PEP 680).
- Free-threaded (no-GIL) build (PEP 703) and the JIT (PEP 744) are **experimental in 3.13**,
  off by default — do not assume they are on.

## Common AI mistakes — DON'T
- DON'T `def f(x=[])` / `def f(x={})` — the default is shared across calls. Use `x=None` then
  `x = [] if x is None else x`, or a dataclass `default_factory`.
- DON'T shadow builtins: `list`, `dict`, `id`, `type`, `input`, `str`, `sum`, `filter`. Rename.
- DON'T write bare `except:` or `except Exception:` swallowing everything — it eats
  `KeyboardInterrupt`/`SystemExit` (bare) and hides bugs. Catch the narrowest type; re-raise or log.
- DON'T mutate a list/dict while iterating it — iterate a copy (`list(d)`) or build a new one.
- DON'T compare with `==` to `None`/`True`/`False` — use `is`.
- DON'T use `assert` for runtime validation — it's stripped under `python -O`.

## Commands
test: `pytest` · lint: `ruff check .` · format: `ruff format .` · type-check: `mypy .`

## Sources
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
