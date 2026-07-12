# Python — Type hints & static typing

Layers on the base python lore. Type hints are for static checkers (mypy/pyright), not runtime enforcement — CPython does not check them. Verified against docs.python.org, peps.python.org, mypy docs (see Sources). Never claim a feature earlier than the release noted.

## DO — built-in generics & unions (modern baseline)
- DO use built-in generics: `list[int]`, `dict[str, int]`, `tuple[str, ...]`, `type[C]` (PEP 585, **3.9**). Deprecates `typing.List/Dict/Tuple/Type`.
- DO write unions as `X | Y` and optionals as `X | None` (PEP 604, **3.10**). Valid in `isinstance(x, int | str)` too.
- DO import container ABCs from `collections.abc` (`Sequence`, `Mapping`, `Iterable`, `Callable`), not `typing`.
- DON'T use `typing.List`, `typing.Optional[X]`, `typing.Union[X, Y]` in new code — they're the pre-3.9/3.10 fallback only.

Fallback (target ≤3.8): `from typing import List, Dict, Optional, Union` — and add `from __future__ import annotations` so `list[int]` / `X | Y` parse as strings.

## DO — precise types, not `Any`
- DO reach for the narrowest type. `Any` disables checking and is contagious — treat it as "unchecked". Prefer `object` (then narrow) when the type is truly unknown.
- DON'T sprinkle `Any` to silence errors. DON'T leave `# type: ignore` bare — scope it: `# type: ignore[arg-type]`.
- DO annotate every public function signature (params + return). Let locals infer.

## DO — Protocol (structural typing)
- DO define interfaces with `Protocol` (PEP 544, **3.8**) for duck typing — no explicit subclassing needed:
```python
from typing import Protocol
class Reader(Protocol):
    def read(self, n: int) -> bytes: ...
def consume(r: Reader) -> None: ...   # any object with matching read() fits
```
- DO add `@runtime_checkable` only if you need `isinstance` against it (checks method presence, not signatures).
- DON'T reach for a nominal ABC when a Protocol expresses the contract without coupling.

## DO — TypedDict, Literal, Final, Annotated
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

## DO — generics
- DO use PEP 695 syntax on **3.12+** — no `TypeVar` import, no `Generic` base:
```python
def first[T](xs: list[T]) -> T: ...
class Box[T]:
    def __init__(self, v: T) -> None: self.v = v
type IntBox = Box[int]                 # `type` statement → TypeAliasType, lazy eval
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

## DO — Self & overload
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

## DO — narrowing helpers
- DO end unreachable branches with `assert_never(x)` (**3.11**) for exhaustive `match`/`if` over unions/Literals — a missed case becomes a type error.
- DO use `Never`/`NoReturn` for functions that never return (`Never` **3.11**, `NoReturn` 3.6.2).
- DO use `@override` (PEP 698, **3.12**) on methods meant to override a base — catches renamed/removed parents.
- DO debug with `reveal_type(x)` (**3.11**; checkers understand it without import).

## DON'T — annotation runtime pitfalls
- DON'T assume annotations are evaluated eagerly. Add `from __future__ import annotations` (PEP 563, **3.7**) to defer them to strings → forward refs work without quotes, no import-time cost. Read them via `typing.get_type_hints()`.
- Note: **3.14** makes deferred (lazy) annotations the default via PEP 649 — inspect through the new `annotationlib` (behavior differs from PEP 563 stringification).
- DON'T use `typing.TypeAlias` on 3.12+ — deprecated in favor of the `type` statement. Old alias: `Vector: TypeAlias = list[float]`.

## DO — enforce in CI (types are worthless unchecked)
- DO run a checker on every PR. mypy: `mypy --strict src/` (bundles `disallow-untyped-defs`, `warn-return-any`, `warn-unused-ignores`, `strict-equality`, …). Or pyright: `pyright`.
- DO configure in `pyproject.toml`:
```toml
[tool.mypy]
strict = true
warn_unused_ignores = true
```
- DO gate: fail CI on any error. DON'T let `# type: ignore` accumulate — `warn_unused_ignores` prunes stale ones.
- DON'T rely on hints at runtime for validation — use pydantic/attrs if you need enforced data. Hints alone are advisory.

## Version cue
3.7 `from __future__ import annotations` · 3.8 Protocol/TypedDict/Literal/Final · 3.9 `list[int]`/Annotated · 3.10 `X|Y`/`X|None` · 3.11 Self/Required·NotRequired/assert_never/Never · 3.12 PEP 695 `class C[T]`+`type` statement/@override · 3.13 TypeVar defaults/ReadOnly · 3.14 PEP 649 lazy annotations default.

## Sources
- https://docs.python.org/3/library/typing.html
- https://peps.python.org/pep-0585/ (built-in generics, 3.9)
- https://peps.python.org/pep-0604/ (X|Y unions, 3.10)
- https://peps.python.org/pep-0695/ (type params + `type` statement, 3.12)
- https://mypy.readthedocs.io/en/stable/command_line.html
- https://docs.python.org/3/reference/simple_stmts.html (PEP 563/649 annotations)
