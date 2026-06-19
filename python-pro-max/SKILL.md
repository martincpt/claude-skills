---
name: python-pro-max
description: Use when building Python 3.11+ applications requiring type safety, async programming, or robust error handling. Generates type-annotated Python code, configures mypy in strict mode, writes pytest test suites with fixtures and mocking, and validates code with black and ruff. Invoke for type hints, async/await patterns, dataclasses, dependency injection, logging configuration, and structured error handling.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.0"
  domain: language
  triggers: Python development, type hints, async Python, pytest, mypy, dataclasses, Python best practices, Pythonic code, MongoDB, Beanie ODM
  role: specialist
  scope: implementation
  output-format: code
  related-skills: fastapi-expert, devops-engineer
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
5. **Validate** — Run `mypy --strict`, `black`, `ruff`
   - If mypy fails: fix type errors reported and re-run before proceeding
   - If tests fail: debug assertions, update fixtures, and iterate until green
   - If ruff/black reports issues: apply auto-fixes, then re-validate

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Type System | `references/type-system.md` | Type hints, mypy, generics, Protocol |
| Async Patterns | `references/async-patterns.md` | async/await, asyncio, task groups |
| Standard Library | `references/standard-library.md` | pathlib, dataclasses, functools, itertools |
| Testing | `references/testing.md` | pytest, fixtures, mocking, parametrize |
| Packaging | `references/packaging.md` | uv, pyproject.toml, flat/app layout, distribution |
| MongoDB / Beanie | `references/mongo-beanie.md` | MongoDB, Beanie ODM, async documents, test DB fixtures |

## Constraints

### MUST DO
- Type hints for all function signatures and class attributes
- PEP 8 compliance with black formatting
- Google-style docstrings — one line by default; full `Args`/`Returns`/`Raises` only on main components (see Docstring Style)
- Test coverage exceeding 90% with pytest
- Use `X | None` instead of `Optional[X]` (Python 3.10+)
- Async/await for I/O-bound operations
- Pydantic models for validation and data transfer; dataclasses (over manual `__init__`) for simple internal structures or when Pydantic is unavailable
- Strict, self-describing types for any data with a known shape — a Pydantic model, dataclass, or `NamedTuple`; a plain `tuple[bool, str]` is fine for trivial returns
- Context managers for resource handling
- CLIs built with the Fire package — a class-based launcher where each method is a subcommand (nested classes for command groups)
- Error messages on their own line — assign `message = "..."`, then `raise SomeError(message)`; never a string/f-string literal inside the `raise` call (ruff EM101/EM102)
- String-valued enums subclass `(str, Enum)`; enum members are `lower_case`
- In `__all__`, reference `obj.__name__` for objects that have one (classes, functions) and a plain string only for values without one — a rename/typo then fails fast (requires ignoring ruff PLE0604)

### MUST NOT DO
- Skip type annotations on public APIs
- Use mutable default arguments
- Mix sync and async code improperly
- Ignore mypy errors in strict mode
- Use bare except clauses
- Hardcode secrets or configuration
- Use deprecated stdlib modules (use pathlib not os.path)
- Use a `dict`/`Mapping` as an argument or return type when the keys are known ahead of time — model the data instead (see Data Modeling & Dictionaries)
- Return ambiguous, unstructured data when the shape can be specified

## Docstring Style

Google style, but lean. Let descriptive names and type hints carry the weight.

- **Default to one line.** When the name is well understood and descriptive (which it should be), a single summary line is enough. The type hints already document the parameters and return type.
- **Full `Args`/`Returns`/`Raises` only on main or most important components** — primary entry points, public APIs, and functions with non-obvious behavior, edge cases, or raised exceptions worth calling out.
- **Document every method, including dunders** — but keep trivial dunders' docstrings *generic and maintenance-free* so they never go stale as the body changes. Name the class in `__init__` (`"""Initialize the AppConfig instance."""`, not the body-specific `"""Store the host and port."""`); use `"""Return the string representation."""` for `__repr__`, `"""Enter the async context."""` for `__aenter__`, and so on. Named functions and methods get an intent-describing one-liner, which is name-derived and stays stable anyway.

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

### mypy strict configuration (pyproject.toml)
```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

Clean `mypy --strict` output looks like:
```
Success: no issues found in 12 source files
```
Any reported error (e.g., `error: Function is missing a return type annotation`) must be resolved before the implementation is considered complete.

## Output Templates

When implementing Python features, provide:
1. Module file with complete type hints
2. Test file with pytest fixtures
3. Type checking confirmation (mypy --strict passes)
4. Brief explanation of Pythonic patterns used

## Knowledge Reference

Python 3.11+, typing module, mypy, pytest, black, ruff, dataclasses, async/await, asyncio, pathlib, functools, itertools, uv, Pydantic, Fire, Beanie, MongoDB, mongomock-motor, contextlib, collections.abc, Protocol

[Documentation](https://jeffallan.github.io/claude-skills/skills/language/python-pro-max/)
