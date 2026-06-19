# Type System Mastery

## Basic Type Annotations

```python
from typing import Any
from collections.abc import Sequence, Mapping
from pydantic import BaseModel

# Model the data instead of returning bare dicts with known keys
class User(BaseModel):
    """A user record."""

    name: str
    age: int
    active: bool = True

# Function signatures
def process_user(name: str, age: int, active: bool = True) -> User:
    """Build a user record from individual fields."""
    return User(name=name, age=age, active=active)

# Use | for unions (Python 3.10+)
def find_user(user_id: int | str) -> User | None:
    """Look up a user by id, returning None if absent."""
    if isinstance(user_id, int):
        return User(name="Ada", age=36)
    return None

# Collections - prefer collections.abc
def process_items(items: Sequence[str]) -> list[str]:
    """Accepts list, tuple, or any sequence."""
    return [item.upper() for item in items]

def merge_configs(base: Mapping[str, int], override: dict[str, int]) -> dict[str, int]:
    """Mapping for read-only, dict for mutable."""
    return {**base, **override}
```

## Generic Types

```python
from typing import TypeVar, Generic, Protocol
from collections.abc import Callable

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# Generic function
def first_element(items: Sequence[T]) -> T | None:
    """Return the first element, or None if empty."""
    return items[0] if items else None

# Generic class
class Cache(Generic[K, V]):
    """Simple in-memory key-value cache."""

    def __init__(self) -> None:
        """Initialize the Cache instance."""
        self._data: dict[K, V] = {}

    def get(self, key: K) -> V | None:
        """Return the cached value for a key, or None."""
        return self._data.get(key)

    def set(self, key: K, value: V) -> None:
        """Store a value under a key."""
        self._data[key] = value

# Usage
user_cache: Cache[int, str] = Cache()
user_cache.set(1, "Alice")

# Constrained TypeVar
from numbers import Number
NumT = TypeVar('NumT', bound=Number)

def add_numbers(a: NumT, b: NumT) -> NumT:
    """Add two numbers of the same type."""
    return a + b  # type: ignore[return-value]
```

## Protocol for Structural Typing

```python
from typing import Protocol, runtime_checkable

# Define interface without inheritance
class Drawable(Protocol):
    """Anything that can be drawn and exposes a color."""

    def draw(self) -> str:
        ...

    @property
    def color(self) -> str:
        ...

class Circle:
    """A drawable circle."""

    def __init__(self, radius: float, color: str) -> None:
        """Initialize the Circle instance."""
        self.radius = radius
        self._color = color

    def draw(self) -> str:
        """Return a description of the drawn circle."""
        return f"Drawing {self._color} circle"

    @property
    def color(self) -> str:
        """The circle's color."""
        return self._color

# Circle implements Drawable without inheriting
def render(shape: Drawable) -> str:
    """Render any drawable shape."""
    return shape.draw()

# Runtime checkable protocol
@runtime_checkable
class Closeable(Protocol):
    """Anything with a close() method."""

    def close(self) -> None:
        ...

def cleanup(resource: Closeable) -> None:
    """Close the resource if it is closeable."""
    if isinstance(resource, Closeable):
        resource.close()
```

## Advanced Type Features

```python
from typing import Literal, TypeAlias, TypedDict, NotRequired, Self, overload

# Literal types for constants
Mode = Literal["read", "write", "append"]

def open_file(path: str, mode: Mode) -> None:
    """Open a file in the given mode."""
    ...

# Type aliases for complex types
JsonDict: TypeAlias = dict[str, Any]
UserId: TypeAlias = int | str

# TypedDict types dict-shaped data you don't control (e.g. external JSON).
# For data you create, pass around, or validate, prefer a Pydantic model.
class UserDict(TypedDict):
    """Structured shape for a user payload."""

    id: int
    name: str
    email: str
    age: NotRequired[int]  # Optional field

def create_user(data: UserDict) -> None:
    """Create a user from a typed dict."""
    print(data["name"])  # Type-safe access

# Self type for method chaining
class Builder:
    """Fluent builder for an integer value."""

    def __init__(self) -> None:
        """Initialize the Builder instance."""
        self._value = 0

    def add(self, n: int) -> Self:
        """Add to the running value and return self."""
        self._value += n
        return self

    def multiply(self, n: int) -> Self:
        """Multiply the running value and return self."""
        self._value *= n
        return self

# Overload for different signatures
@overload
def process(data: str) -> str: ...

@overload
def process(data: int) -> int: ...

def process(data: str | int) -> str | int:
    """Transform a string or int payload."""
    if isinstance(data, str):
        return data.upper()
    return data * 2
```

## Callable Types

```python
from collections.abc import Callable
from typing import ParamSpec, Concatenate

# Basic callable
def apply(func: Callable[[int, int], int], a: int, b: int) -> int:
    """Apply a binary function to two integers."""
    return func(a, b)

# ParamSpec for preserving signatures
P = ParamSpec('P')
R = TypeVar('R')

def logging_decorator(func: Callable[P, R]) -> Callable[P, R]:
    """Log each call to the wrapped function."""

    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        """Log the call, then invoke the wrapped function."""
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

# Concatenate for dependency injection
def with_connection(
    func: Callable[Concatenate[Connection, P], R]
) -> Callable[P, R]:
    """Inject a connection as the first argument of the wrapped function."""

    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        """Acquire a connection, then invoke the wrapped function."""
        conn = get_connection()
        return func(conn, *args, **kwargs)
    return wrapper

# Usage
@with_connection
def query_user(conn: Connection, user_id: int) -> User:
    """Fetch a user row over the injected connection."""
    return conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

## Mypy Configuration

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
disallow_subclassing_any = true
disallow_untyped_calls = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[[tool.mypy.overrides]]
module = "third_party.*"
ignore_missing_imports = true
```

## Common Type Patterns

```python
# Result type pattern
from dataclasses import dataclass

@dataclass
class Success(Generic[T]):
    """Successful result carrying a value."""

    value: T

@dataclass
class Error:
    """Failed result carrying an error message."""

    message: str

Result = Success[T] | Error

def divide(a: int, b: int) -> Result[float]:
    """Divide a by b, returning a Result instead of raising."""
    if b == 0:
        return Error("Division by zero")
    return Success(a / b)

# Option/Maybe type
def safe_get(items: Sequence[T], index: int) -> T | None:
    """Return the item at index, or None if out of range."""
    try:
        return items[index]
    except IndexError:
        return None

# Sentinel value with typing
from typing import Final

MISSING: Final = object()

def get_value(key: str, default: T | type[MISSING] = MISSING) -> T:
    """Return the default, or raise if no default was supplied."""
    if default is MISSING:
        raise KeyError(key)
    return default  # type: ignore[return-value]
```

## Type Narrowing

```python
from typing import assert_type, assert_never

def process_value(value: int | str | None) -> str:
    """Render an optional int-or-str value as a string."""
    # Type guards
    if value is None:
        return "null"

    if isinstance(value, int):
        # Type narrowed to int
        return str(value * 2)

    # Type narrowed to str
    return value.upper()

# Exhaustiveness checking
def handle_mode(mode: Literal["read", "write"]) -> str:
    """Dispatch on a read/write mode, exhaustively."""
    if mode == "read":
        return "Reading"
    elif mode == "write":
        return "Writing"
    else:
        # Mypy will error if mode can be anything else
        assert_never(mode)

# Custom type guard
def is_string_list(val: list[Any]) -> bool:
    """Runtime check for list of strings."""
    return all(isinstance(x, str) for x in val)
```
