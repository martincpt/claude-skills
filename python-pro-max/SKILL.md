---
name: python-pro-max
description: Use when building Python 3.11+ applications (new projects target 3.13) to the team's conventions — type-annotated, async-first code; Pydantic and pydantic-settings for models and config; uv packaging in a flat app layout; Fire CLIs; pytest with fixtures and mocking; and MongoDB via the Beanie ODM. Covers the repository/service split, dependency injection, and the core/domains package architecture. Validates with ruff, black, and mypy. Invoke for type hints, async patterns, data modeling, project/config scaffolding, CLI design, error handling, Mongo/Beanie integration, data-access layering, and project structure.
license: MIT
metadata:
    author: Martin Trapp
    version: "2.6.0"
    domain: language
    triggers: Python development, type hints, async Python, pytest, mypy, ruff, uv, Pydantic, pydantic-settings, Fire CLI, dataclasses, MongoDB, Beanie ODM, repository pattern, service layer, dependency injection, project structure, Python best practices
    role: specialist
    scope: implementation
    output-format: code
---

# Python Pro Max

Modern Python 3.11+ specialist focused on type-safe, async-first, production-ready code.

## When to Use This Skill

- Writing type-safe Python with complete type coverage
- Implementing async/await patterns for I/O operations
- Setting up pytest test suites with fixtures and mocking
- Creating Pythonic code with comprehensions, generators, context managers
- Building packages with uv and a flat project layout
- Integrating MongoDB via the Beanie ODM (async documents, connector, test fixtures)
- Performance optimization and profiling

## Core Workflow

1. **Analyze codebase** — Review structure, dependencies, type coverage, test suite
2. **Design interfaces** — Define protocols, Pydantic models (or dataclasses), type aliases
3. **Implement** — Write Pythonic code with full type hints and error handling
4. **Test** — Create comprehensive pytest suite with >90% coverage
5. **Validate** — Run `mypy`, `black`, `ruff` (or `pre-commit run --all-files`)
    - If mypy fails: fix type errors reported and re-run before proceeding
    - If tests fail: debug assertions, update fixtures, and iterate until green
    - If ruff/black reports issues: apply auto-fixes, then re-validate

## Reference Guide

Load detailed guidance based on context:

| Topic                   | Reference                                 | Load When                                                |
| ----------------------- | ----------------------------------------- | -------------------------------------------------------- |
| Type System             | `references/type-system.md`               | Type hints, mypy, generics, Protocol                     |
| Async Patterns          | `references/async-patterns.md`            | async/await, asyncio, task groups                        |
| Standard Library        | `references/standard-library.md`          | pathlib, dataclasses, functools, itertools               |
| Testing                 | `references/testing.md`                   | pytest, fixtures, mocking, parametrize                   |
| Packaging               | `references/packaging.md`                 | uv, pyproject.toml, flat/app layout, distribution        |
| Project Architecture    | `references/project-architecture.md`      | core/ vs domains/, module layout, layering, entry points |
| MongoDB / Beanie        | `references/mongo-beanie.md`              | MongoDB, Beanie ODM, async documents, test DB fixtures   |
| Repositories & Services | `references/repositories-and-services.md` | Data access, repository/service split, DI, write schemas |

## Constraints

### MUST DO: Core — correctness & typing

- Type hints on all function signatures and class attributes
- `X | None` instead of `Optional[X]` (Python 3.10+)
- Async/await for I/O-bound operations
- Pydantic models for validation and data transfer; dataclasses (over manual `__init__`) or `NamedTuple` for simple internal structures or when Pydantic is unavailable
- Strict, self-describing types for any data with a known shape — never a `dict`/`Mapping` when the keys are known; a plain `tuple[bool, str]` is fine for trivial returns (see Data Modeling & Dictionaries)
- Configuration via pydantic-settings — a `config.py` under the main package with a `Settings(BaseSettings)` class and an `lru_cache`d `get_settings()`
- Context managers for resource handling
- Test coverage exceeding 90% with pytest
- Data access through a repository per document type, with writes **opted into one operation at a time** (`Creatable`/`Updatable`/`Deletable`) and the writable field set declared as a Pydantic create/update schema (see Repositories & Services)
- Policy — guards, orderings, rollbacks, checks that read another document — in a **service** that composes repositories by constructor injection; never in the repository, never in the entry point

### MUST DO: House style — lint & conventions

- PEP 8 + black formatting; code passes `ruff` and `mypy` (non-strict) clean
- Google-style docstrings — one line by default; full `Args`/`Returns`/`Raises` only on main components (see Docstring Style)
- CLIs built with the Fire package — a class-based launcher where each method is a subcommand (nested classes for command groups)
- Error messages on their own line — `message = "..."`, then `raise SomeError(message)`; no literal inside the `raise` (ruff EM101/EM102)
- Enum members are `lower_case`
- `__all__` references `obj.__name__` for objects that have one, a plain string only for values without one — fails fast on rename/typo (ruff PLE0604 ignored)
- pytest: parenthesized fixtures and marks, tuple `parametrize` names (ruff flake8-pytest-style)
- Declare every instance attribute at class level, annotation-only (`name: str`), then assign in `__init__` — the class header alone documents what state the object holds (see Instance Variables)
- `from __future__ import annotations` only when a forward reference actually needs it (self-returning method, mutually-referencing classes) — never as a blanket import; skip it entirely on Python 3.14+ where PEP 649 makes it unnecessary (see Forward References)
- Relative imports for a package's own modules — `from .config import get_settings`, never `from app.config import get_settings` from inside `app`; absolute for anything outside the current package, and never `..` upward (ruff TID252) (see Relative Imports)
- Breezy, visually grouped method bodies — blank lines separate logical groups (setup / main logic / return); never jam a `for`/`while`/`if` against the declarations it consumes (see Whitespace & Visual Grouping)
- No bare functions in utility modules — group related helpers as `@staticmethod`/`@classmethod` under a domain class (`AsyncUtils.execute_in_batches(...)`, not a naked `execute_in_batches(...)`) so call sites are self-documenting (see Grouping Functions Under Classes)
- Test directories mirror the source **packages** (not modules), files are named for the behaviour they prove, and every test directory carries an `__init__.py` (see Test Layout)
- An application with more than one business area splits `core/` (cross-cutting infrastructure, no business logic) from `domains/<area>/` (business logic, independent of each other), with `api/`/`workflows/`/`cli/` as thin entry points that hold none (see Project Architecture)
- Services named for the **workflow** they perform (`RegistryService`, `CurationService`); repositories named for the **document** they serve (`CategoryRepository`)
- Beanie queries built from **operators and comparison expressions**, never a hand-written mapping literal — `Set({Model.field: v})` not `{"$set": {...}}`, and `Model.field == v` never `Eq(...)`; the only exceptions are a field path assembled at runtime (passed *through* an operator) and an operation Beanie has no operator for (see MongoDB / Beanie)
- A method forwarding Beanie expressions types them as Beanie does — `*expressions: Mapping[Any, Any] | bool`, not `Any`; a standard-library type still constrains callers where the lint gate leaves `beanie` unresolved

### MUST NOT DO

- Skip type annotations on public APIs
- Use mutable default arguments
- Mix sync and async code improperly
- Use bare `except` clauses
- Hardcode secrets or configuration
- Use deprecated stdlib modules (use `pathlib`, not `os.path`)
- Use a `dict`/`Mapping` as an argument or return type when the keys are known ahead of time — model the data instead
- Return ambiguous, unstructured data when the shape can be specified
- Add `from __future__ import annotations` out of habit when nothing needs a forward reference
- Spell out the current package in its own imports (`from app.mongo.connector import ...` inside `app/mongo/`) or walk upward with `..` — use a single-dot relative import
- Leave standalone functions loose in a utility module — group them under a named domain class
- Leave instance attributes undeclared, discoverable only by reading `__init__` — annotate them at class level
- Assign a value to a class-level attribute annotation meant to be per-instance — that creates a shared class variable (use `ClassVar` only for genuine shared constants)
- Write dense, unbroken method bodies — separate setup, main logic, and return with blank lines
- Split tests into `unit/` and `integration/` trees, or name a test file after the module it covers (`test_models_content_hash.py`) — mirror packages and name for behaviour instead
- Leave a test directory without an `__init__.py` — collection breaks, and the error names an unrelated module
- Write a Mongo query or update as a mapping literal (`{"$set": ...}`, `{"$or": ...}`) when a Beanie operator or comparison expression expresses it — the mapping's field names are strings nothing resolves, so a rename leaves it matching nothing without raising
- Use the `Eq` operator where `Model.field == value` says the same thing
- Hand a repository every write operation by default, or let it decide anything — a guard, an ordering, a rollback, a reference check — that belongs to a service
- Accept `**fields` or maintain a `read_only_fields` list in place of a declared update schema — a runtime filter silently drops what it matches, whereas an omitted field is caught by mypy at the call site
- Call the ODM's own `insert()`/`delete()` from a service, or make a service inherit from a repository instead of composing it
- Put business logic in a route, worker task, CLI command, or dashboard page
- Import `domains/` from `core/`, import one domain from another, or collect helpers into a `utils.py` grab bag
- Ignore `ruff` or `mypy` errors

## Docstring Style

Google style, but lean. Let descriptive names and type hints carry the weight.

- **Default to one line.** When the name is well understood and descriptive (which it should be), a single summary line is enough. The type hints already document the parameters and return type.
- **Full `Args`/`Returns`/`Raises` only on main or most important components** — primary entry points, public APIs, and functions with non-obvious behavior, edge cases, or raised exceptions worth calling out.
- **Document every method, including dunders** — but keep trivial dunders' docstrings _generic and maintenance-free_ so they never go stale as the body changes. Name the class in `__init__` (`"""Initialize the AppConfig instance."""`, not the body-specific `"""Store the host and port."""`); use `"""Return the string representation."""` for `__repr__`, `"""Enter the async context."""` for `__aenter__`, and so on. Named functions and methods get an intent-describing one-liner, which is name-derived and stays stable anyway.

```python
# One line — the name and signature say the rest:
def slugify(title: str) -> str:
    """Convert a title into a URL-safe slug."""
    ...

# Full form — reserved for important components with edge cases worth documenting:
def read_config(path: Path) -> AppConfig:
    """Read configuration from a file.

    Args:
        path: Path to the configuration file.

    Returns:
        The parsed application configuration.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If a line cannot be parsed.
    """
    ...
```

## Data Modeling & Dictionaries

Data with a known shape gets a type that describes it. Dictionaries are too loose — relying on specific keys defeats type checking and hides the contract.

- **Prefer Pydantic models.** Use Pydantic over dataclasses whenever it's available: it gives runtime validation, richer validators, and first-class support in modern frameworks (FastAPI, etc.). Reach for a dataclass or `NamedTuple` only for simple internal structures or when Pydantic isn't a dependency.
- **Use a transfer model for anything crossing a boundary** (function returns, API payloads, service-to-service data). Never hand back a bare `dict` when the attributes and types can be named.
- **Tuples for trivial returns.** A `tuple[bool, str]` (e.g. `(ok, message)`) is enough when there are only a couple of unnamed values; promote to a model once the shape grows or the fields deserve names.
- **Dicts/Mappings only for genuinely dynamic data** — keys that aren't known ahead of time and are computed at runtime: language→translation maps or id→object lookups built for optimization. If you ever rely on a specific literal key, it should have been a model.
- **Inbound dicts are fine — validate them into a model immediately.** Data arriving as a `dict` from an API, JSON, a config file, or a generic DB-row handler is expected; parse it straight into a model (`MyModel(**values)` or `MyModel.model_validate(values)`) instead of passing the raw dict around or relying on its keys downstream.

```python
from typing import Any

from pydantic import BaseModel

# Bad — known keys hidden in a dict; no validation, no autocomplete:
def get_user(user_id: int) -> dict[str, Any]:
    """Load a user by id."""
    return {"id": user_id, "name": "Ada", "active": True}

# Good — the shape is explicit, validated, and self-documenting:
class User(BaseModel):
    """A user record."""

    id: int
    name: str
    active: bool = True

def get_user(user_id: int) -> User:
    """Load a user by id."""
    return User(id=user_id, name="Ada")

# Fine — a trivial two-value return needs no model:
def validate(value: str) -> tuple[bool, str]:
    """Return whether the value is valid and a human-readable reason."""
    if not value:
        return False, "value is empty"
    return True, "ok"

# Fine — keys are genuinely dynamic (unknown languages at design time):
def load_translations(locale: str) -> dict[str, str]:
    """Return the message-key to translated-string map for a locale."""
    ...

# Fine — receive an external dict, but validate it into a model right away:
def parse_user(payload: dict[str, Any]) -> User:
    """Validate an inbound API/JSON payload into a User."""
    return User(**payload)  # or: User.model_validate(payload)
```

## Instance Variables

Declare every instance attribute at class level as an annotation-only line, then assign it in `__init__` (or wherever it's set). The class header becomes a single, honest inventory of the object's state — no reading through method bodies to discover what `self.*` attributes exist. Pydantic models and dataclasses already do this by construction; the convention matters for plain classes with an `__init__`.

Keep the class-level line **annotation-only** — no value. A bare `name: str` declares an *instance* variable; adding a value (`name: str = ...`) creates a *class* variable shared across all instances, which is almost never what you want for per-instance state (and is a mutable-default trap). Assign the real value in `__init__`.

```python
import asyncio

# Bad — attributes only discoverable by reading __init__; state is implicit:
class BackgroundTaskManager:
    """Track background tasks for coordinated shutdown."""

    def __init__(self) -> None:
        """Initialize the BackgroundTaskManager instance."""
        self._tasks = set()

# Good — the header lists every attribute and its type up front:
class BackgroundTaskManager:
    """Track background tasks for coordinated shutdown."""

    _tasks: set[asyncio.Task[None]]

    def __init__(self) -> None:
        """Initialize the BackgroundTaskManager instance."""
        self._tasks = set()

# Wrong — a value at class level makes _tasks a *shared* class variable,
# so every instance mutates the same set:
class BackgroundTaskManager:
    """Track background tasks for coordinated shutdown."""

    _tasks: set[asyncio.Task[None]] = set()  # ← shared across all instances

    def __init__(self) -> None:
        """Initialize the BackgroundTaskManager instance."""
        ...
```

Genuine class-level constants (shared, not per-instance) are the exception — annotate them `ClassVar` so the distinction is explicit:

```python
from typing import ClassVar

class ApiClient:
    """Client for the example API."""

    BASE_URL: ClassVar[str] = "https://api.example.com"  # shared constant
    timeout: int                                          # per-instance state

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the ApiClient instance."""
        self.timeout = timeout
```

## Forward References

Don't add `from __future__ import annotations` as a blanket import. Reach for it only when a forward reference genuinely needs it — a method that returns its own class, or two classes that reference each other. Otherwise omit it; the extra line is just noise. On projects that target **Python 3.14+ only**, skip it entirely — PEP 649 defers annotation evaluation, so forward references resolve without it.

```python
# Needed — the return annotation names the class before its body is complete:
from __future__ import annotations

class Node:
    """A singly linked-list node."""

    value: int
    next: Node | None

    def __init__(self, value: int) -> None:
        """Initialize the Node instance."""
        self.value = value
        self.next = None

    def append(self, value: int) -> Node:
        """Append a value after this node and return the new node."""
        self.next = Node(value)
        return self.next

# Not needed — no forward reference anywhere, so leave the import out:
from pydantic import BaseModel

class Point(BaseModel):
    """Immutable 2D point."""

    x: float
    y: float
```

> For a method that returns *its own* class, `typing.Self` is often cleaner than a forward reference and needs no future import — prefer it where it fits (see `references/type-system.md`).

## Relative Imports

Import a package's own modules relatively: `from .connector import MongoWithBeanie`, not
`from app.mongo.connector import MongoWithBeanie` from inside `app/mongo`. The single dot
marks the import as internal at a glance, keeps the line short, and survives a package
rename. Everything outside the current package stays absolute, and imports never walk
upward — `..` and higher are banned (ruff TID252, enabled by `select = ["ALL"]`).

```python
# app/mongo/__init__.py — connector.py is a direct child, so import it relatively:
from .connector import MongoWithBeanie

# app/mongo/fixtures.py — siblings relative, everything else absolute:
from app.config import settings

from .connector import MongoWithBeanie
from .mock import MongomockCompat

# Bad — the current package spelled out in full:
from app.mongo.connector import MongoWithBeanie

# Bad — walking up and out of the package:
from ..config import settings
```

A nested target reached through a direct child keeps the single dot too — `from
.models.user import User` in `app/__init__.py`. Import order is unchanged: ruff/isort
already sorts the relative block last, separated by a blank line.

## Whitespace & Visual Grouping

Give executable code room to breathe. Inside a function or method body, separate logical groups of statements with blank lines the way you'd separate paragraphs — setup, main logic, and cleanup/return each stand apart. Favor scannability over compactness; err toward more whitespace, not less. In particular, never jam a `for`/`while`/`if` directly against the declarations it consumes.

```python
# Dense — everything crammed together, hard to scan:
def summarize(rows: list[Row]) -> Summary:
    """Summarize a batch of rows."""
    total = 0
    errors: list[str] = []
    seen: set[int] = set()
    for row in rows:
        if row.id in seen:
            errors.append(f"duplicate id {row.id}")
            continue
        seen.add(row.id)
        total += row.amount
    return Summary(total=total, errors=errors)

# Breezy — setup, main loop, and return read as distinct groups:
def summarize(rows: list[Row]) -> Summary:
    """Summarize a batch of rows."""
    total = 0
    errors: list[str] = []
    seen: set[int] = set()

    for row in rows:
        if row.id in seen:
            errors.append(f"duplicate id {row.id}")
            continue

        seen.add(row.id)
        total += row.amount

    return Summary(total=total, errors=errors)
```

## Grouping Functions Under Classes

A utility module shouldn't be a bag of loose functions. Group related helpers as `@staticmethod` or `@classmethod` under an appropriately named class, so the class prefix documents where each call comes from and what domain it belongs to. `AsyncUtils.execute_in_batches(...)` announces its origin at the call site; a naked `execute_in_batches(...)` could come from anywhere.

```python
import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

# Bad — async_utils.py as a pile of bare module-level functions:
async def execute_in_batches(items, batch_size, handler): ...
async def gather_with_limit(coros, limit): ...

# Good — grouped under a domain class; call sites read as AsyncUtils.execute_in_batches(...):
class AsyncUtils:
    """Helpers for running coroutines with bounded concurrency."""

    @staticmethod
    async def execute_in_batches(
        items: Sequence[T],
        batch_size: int,
        handler: Callable[[T], Awaitable[R]],
    ) -> list[R]:
        """Run handler over items in fixed-size batches, preserving order."""
        results: list[R] = []

        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            results.extend(await asyncio.gather(*(handler(item) for item in batch)))

        return results

    @staticmethod
    async def gather_with_limit(
        coros: Sequence[Awaitable[R]],
        limit: int,
    ) -> list[R]:
        """Await all coroutines, running at most `limit` concurrently."""
        semaphore = asyncio.Semaphore(limit)

        async def _run(coro: Awaitable[R]) -> R:
            """Await a single coroutine while holding the semaphore."""
            async with semaphore:
                return await coro

        return await asyncio.gather(*(_run(coro) for coro in coros))
```

## Test Layout

Mirror the source **packages** in the test tree, but name files for the **behaviour** they prove.
Those two rules pull in different directions on purpose: the directory answers "where do I put this?",
the filename answers "what does this prove?".

```
app/                                tests/
  core/                               __init__.py          ← required, see below
    mongo/                            conftest.py
      links.py                        test_architecture.py ← codebase-wide guards
      repository.py                   core/
  domains/                              __init__.py
    orders/                             mongo/
      models.py                           __init__.py
      services.py                         test_links.py
                                          test_repository.py
                                      domains/
                                        orders/
                                          test_models.py
                                          test_pricing.py   ← behaviour, not a module
                                          test_services.py
```

**Stop the mirror at package level, not one file per module.** One module is often covered by several
behaviours (`test_pricing.py` and `test_discounts.py` may both exercise `models.py`); forcing them
into a single `test_models.py` loses the naming that makes them findable, and keeping both breaks a
module-level mirror anyway.

**Never prefix a filename with its module** (`test_models_pricing.py`). That re-couples the name to a
module boundary one level below where the mirror stops, so moving code between modules falsifies the
filename — and it cannot express a behaviour spanning several modules. Put the subject in the module
docstring instead, where it stays accurate and costs one line to update:

```python
"""Tests for order pricing, including bulk discounts.

Subject: domains/orders/models.py, domains/orders/services.py
"""
```

**Every test directory needs an `__init__.py`, including `tests/` itself.** This is correctness, not
style. Under pytest's default prepend import mode a module's importable name comes from walking up
while `__init__.py` files exist, and the directory where that walk stops goes on `sys.path`:

- Missing at `tests/` → the project root never reaches `sys.path`; collection dies at `conftest.py`
  with `ModuleNotFoundError: No module named 'app'`.
- Missing on a nested directory → module names truncate to the part below the gap, so
  `tests/core/email/test_client.py` imports as `email.test_client`, a top-level package named
  `email` that collides with the standard library.

Both failures name something other than the missing file, which is why the rule is worth stating
rather than rediscovering. The same fully-qualified naming is what lets two `test_models.py` files in
different directories coexist.

**Do not mirror thin entry points.** CLI, API, and worker packages hold no logic worth unit-testing;
what they invoke is tested where it lives. The absent directory documents the decision.

**Guard tests need their own guard.** A test that reads source files (import-cycle checks, layering
rules) must resolve paths from `__file__`, never the working directory — a cwd-relative path that
resolves to nothing passes vacuously. Assert the paths exist:

```python
ROOT = Path(__file__).resolve().parents[1]

def test_guarded_modules_exist() -> None:
    """The guarded paths must resolve, or every guard below passes on nothing."""
    missing = [p for p in GUARDED_MODULES if not p.is_file()]

    assert not missing, f"guarded modules not found: {missing}"
```

## Code Examples

### Pydantic model with validation

```python
from pydantic import BaseModel, Field, field_validator

class AppConfig(BaseModel):
    """Application configuration with validation."""

    host: str
    port: int = Field(ge=1, le=65535)
    debug: bool = False
    allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("host", mode="after")
    @classmethod
    def strip_host(cls, value: str) -> str:
        """Normalize the host by stripping surrounding whitespace."""
        return value.strip()
```

### Type-annotated function with error handling

```python
from pathlib import Path

def read_config(path: Path) -> AppConfig:
    """Read configuration from a file.

    Args:
        path: Path to the configuration file.

    Returns:
        The parsed and validated application configuration.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If a line cannot be parsed.
    """
    # A dict is fine as an intermediate for genuinely dynamic input...
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if not sep:
            message = f"Invalid config line: {line!r}"
            raise ValueError(message)
        values[key.strip()] = value.strip()

    # ...but hand back a validated model, never the raw dict.
    return AppConfig(**values)
```

### Async pattern

```python
import asyncio
import httpx

async def fetch_all(urls: list[str]) -> list[bytes]:
    """Fetch multiple URLs concurrently."""
    async with httpx.AsyncClient() as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        return [r.content for r in responses]
```

### pytest fixture and parametrize

```python
import pytest
from pathlib import Path
from pydantic import ValidationError

@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    """Write a minimal config file and return its path."""
    cfg = tmp_path / "config.txt"
    cfg.write_text("host=localhost\nport=8080\n")
    return cfg

@pytest.mark.parametrize(("port", "valid"), [(8080, True), (0, False), (99999, False)])
def test_app_config_port_validation(port: int, valid: bool) -> None:
    """Reject ports outside the valid 1-65535 range."""
    if valid:
        AppConfig(host="localhost", port=port)
    else:
        with pytest.raises(ValidationError):
            AppConfig(host="localhost", port=port)
```

### mypy configuration (pyproject.toml)

```toml
[tool.mypy]
python_version = "3.13"
ignore_missing_imports = true
```

Clean `mypy` output looks like:

```
Success: no issues found in 12 source files
```

Any reported error (e.g., `error: Function is missing a return type annotation`) must be resolved before the implementation is considered complete.

## Output Templates

When implementing Python features, provide:

1. Module file with complete type hints
2. Test file with pytest fixtures
3. Type checking confirmation (mypy passes)
4. Brief explanation of Pythonic patterns used

## Knowledge Reference

Python 3.11+, typing module, mypy, pytest, black, ruff, dataclasses, async/await, asyncio, pathlib, functools, itertools, uv, Pydantic, pydantic-settings, Fire, Beanie, MongoDB, mongomock-motor, contextlib, collections.abc, Protocol

A complete, runnable reference scaffold (flat app layout, uv, config, Fire CLI, Beanie/Mongo, tests) lives in `examples/`.
