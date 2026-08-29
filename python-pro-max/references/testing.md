# Testing with Pytest

## Basic Pytest Structure

```python
# test_user.py
import pytest
from myapp.user import User, UserService

# Simple test function
def test_user_creation() -> None:
    """Create a user with valid fields."""
    user = User(id=1, name="Alice", email="alice@example.com")
    assert user.name == "Alice"
    assert user.is_active is True

# Test with multiple assertions
def test_user_validation() -> None:
    """Reject an invalid email."""
    with pytest.raises(ValueError, match="Invalid email"):
        User(id=1, name="Alice", email="invalid")

# Test class for grouping
class TestUserService:
    """Tests for UserService."""

    def test_find_user(self) -> None:
        """Find an existing user by id."""
        service = UserService()
        user = service.find(1)
        assert user is not None

    def test_create_user(self) -> None:
        """Create a user through the service."""
        service = UserService()
        user = service.create(name="Bob", email="bob@example.com")
        assert user.id > 0
```

## Fixtures for Setup/Teardown

> Always call the decorator with parentheses — `@pytest.fixture()`, never bare `@pytest.fixture` (ruff `flake8-pytest-style`, `fixture-parentheses = true`).

```python
# conftest.py - shared fixtures
import pytest
from typing import Iterator
from myapp.database import Database, Session

@pytest.fixture()
def db() -> Iterator[Database]:
    """Provide database instance with cleanup."""
    database = Database("test.db")
    database.create_tables()
    yield database
    database.drop_tables()
    database.close()

@pytest.fixture()
def db_session(db: Database) -> Iterator[Session]:
    """Provide database session with rollback."""
    session = db.create_session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture()
def sample_user() -> User:
    """Provide test user."""
    return User(id=1, name="Test User", email="test@example.com")

# Using fixtures in tests
def test_user_creation(db_session: Session, sample_user: User) -> None:
    """Persist and retrieve a user."""
    db_session.add(sample_user)
    db_session.commit()

    retrieved = db_session.query(User).filter_by(id=1).first()
    assert retrieved.name == "Test User"

# Fixture with parameters
@pytest.fixture(params=["sqlite", "postgresql", "mysql"])
def db_engine(request: pytest.FixtureRequest) -> str:
    """Provide each database engine name in turn."""
    return request.param

def test_connection(db_engine: str) -> None:
    """Connect with each database engine."""
    # Test runs 3 times with different engines
    assert create_connection(db_engine)

# Autouse fixture (runs automatically)
@pytest.fixture(autouse=True)
def reset_state() -> Iterator[None]:
    """Reset global state before each test."""
    clear_caches()
    yield
    cleanup_temp_files()
```

## Parametrize for Multiple Cases

> Pass the argument names as a **tuple of strings** — `parametrize(("input", "expected"), ...)` — not a comma-separated `"input,expected"` string. A single argument name stays a plain string (`parametrize("name", ...)`). (ruff `flake8-pytest-style`, PT006.)

```python
import pytest

# Parametrize test function
@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (2, 4),
        (3, 9),
        (4, 16),
        (-2, 4),
    ]
)
def test_square(input: int, expected: int) -> None:
    """Square various integers."""
    assert square(input) == expected

# Multiple parameters
@pytest.mark.parametrize("base", [2, 10])
@pytest.mark.parametrize("exponent", [0, 1, 2])
def test_power(base: int, exponent: int) -> None:
    """Raise bases to non-negative powers."""
    result = base ** exponent
    assert result >= 0

# Parametrize with IDs
@pytest.mark.parametrize(
    ("email", "valid"),
    [
        ("user@example.com", True),
        ("invalid", False),
        ("@example.com", False),
        ("user@", False),
    ],
    ids=["valid", "no_at", "no_user", "no_domain"]
)
def test_email_validation(email: str, valid: bool) -> None:
    """Validate emails across edge cases."""
    assert is_valid_email(email) == valid

# Parametrize with fixtures
@pytest.fixture()
def user_factory():
    """Provide a factory that builds users."""

    def _make_user(name: str, active: bool = True) -> User:
        """Build a user with the given name."""
        return User(name=name, active=active)
    return _make_user

@pytest.mark.parametrize("name", ["Alice", "Bob", "Charlie"])
def test_user_names(user_factory, name: str) -> None:
    """Build users with various names."""
    user = user_factory(name)
    assert user.name == name
```

## Mocking and Patching

```python
from unittest.mock import Mock, MagicMock, patch, AsyncMock, call
import pytest

# Mock object
def test_api_call_with_mock() -> None:
    """Fetch data through a mocked client."""
    mock_client = Mock()
    mock_client.get.return_value = {"status": "ok"}

    service = ApiService(mock_client)
    result = service.fetch_data()

    mock_client.get.assert_called_once_with("/api/data")
    assert result["status"] == "ok"

# Patch function/method
def test_database_call() -> None:
    """Connect using a patched connector."""
    with patch("myapp.database.connect") as mock_connect:
        mock_connect.return_value = Mock()

        db = Database()
        db.connect()

        mock_connect.assert_called_once()

# Patch as decorator
@patch("myapp.user.send_email")
def test_user_registration(mock_send_email: Mock) -> None:
    """Send a welcome email on registration."""
    service = UserService()
    service.register("user@example.com")

    mock_send_email.assert_called_with(
        to="user@example.com",
        subject="Welcome"
    )

# Multiple patches
@patch("myapp.api.requests.get")
@patch("myapp.api.cache.get")
def test_cached_api(mock_cache: Mock, mock_requests: Mock) -> None:
    """Fall back to the API on a cache miss."""
    mock_cache.return_value = None
    mock_requests.return_value.json.return_value = {"data": "value"}

    result = fetch_with_cache("key")

    mock_cache.assert_called_once_with("key")
    mock_requests.assert_called_once()

# Mock side effects
def test_retry_logic() -> None:
    """Retry until the API call succeeds."""
    mock_api = Mock()
    mock_api.call.side_effect = [
        ConnectionError("Failed"),
        ConnectionError("Failed"),
        {"status": "ok"}
    ]

    result = retry_api_call(mock_api)
    assert result["status"] == "ok"
    assert mock_api.call.call_count == 3

# Async mock
@pytest.mark.asyncio()
async def test_async_function() -> None:
    """Fetch a user through an async mock."""
    mock_db = AsyncMock()
    mock_db.fetch_user.return_value = User(id=1, name="Alice")

    service = AsyncUserService(mock_db)
    user = await service.get_user(1)

    mock_db.fetch_user.assert_awaited_once_with(1)
    assert user.name == "Alice"
```

## Async Testing

```python
import pytest
import asyncio

# Mark async test
@pytest.mark.asyncio()
async def test_async_fetch() -> None:
    """Await a successful async fetch."""
    result = await fetch_data("https://api.example.com")
    assert result["status"] == "ok"

# Async fixture
@pytest.fixture()
async def async_db() -> AsyncIterator[AsyncDatabase]:
    """Provide a connected async database."""
    db = AsyncDatabase()
    await db.connect()
    yield db
    await db.disconnect()

@pytest.mark.asyncio()
async def test_async_query(async_db: AsyncDatabase) -> None:
    """Query the async database."""
    result = await async_db.query("SELECT * FROM users")
    assert len(result) > 0

# Test concurrent operations
@pytest.mark.asyncio()
async def test_concurrent_requests() -> None:
    """Fetch multiple URLs concurrently."""
    urls = ["http://example.com/1", "http://example.com/2"]
    results = await asyncio.gather(*[fetch(url) for url in urls])
    assert len(results) == 2
```

## Pytest Markers

> Always call marks with parentheses — `@pytest.mark.slow()`, `@pytest.mark.asyncio()` — even when they take no arguments (ruff `flake8-pytest-style`, `mark-parentheses = true`, PT023).

```python
import pytest

# Skip test
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature() -> None:
    """Placeholder for an unimplemented feature."""
    pass

# Conditional skip
@pytest.mark.skipif(sys.version_info < (3, 11), reason="Requires Python 3.11+")
def test_new_feature() -> None:
    """Exercise a Python 3.11+ only feature."""
    pass

# Expected failure
@pytest.mark.xfail(reason="Known bug #123")
def test_known_bug() -> None:
    """Document a known failing case."""
    assert buggy_function() == expected_value

# Custom markers
@pytest.mark.slow()
def test_slow_operation() -> None:
    """Exercise a slow operation."""
    time.sleep(5)
    assert True

@pytest.mark.integration()
def test_integration() -> None:
    """Ping an external service."""
    assert external_service.ping()

# Run with: pytest -m "not slow"
```

## Test Coverage

```python
# Run with coverage
# pytest --cov=myapp --cov-report=html --cov-report=term

# conftest.py - coverage configuration
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )

# pytest.ini or pyproject.toml
"""
[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "--cov=myapp",
    "--cov-report=term-missing",
    "--cov-fail-under=90",
    "-ra",
    "--strict-markers",
]
testpaths = ["tests"]
"""
```

## Property-Based Testing

```python
from hypothesis import given, strategies as st

# Property-based test
@given(st.integers(), st.integers())
def test_addition_commutative(a: int, b: int) -> None:
    """Addition is commutative."""
    assert a + b == b + a

@given(st.lists(st.integers()))
def test_sorted_is_ordered(lst: list[int]) -> None:
    """sorted() returns a non-decreasing sequence."""
    sorted_lst = sorted(lst)
    for i in range(len(sorted_lst) - 1):
        assert sorted_lst[i] <= sorted_lst[i + 1]

# Custom strategies
@given(st.emails())
def test_email_validation(email: str) -> None:
    """Generated emails contain an @ and validate."""
    assert "@" in email
    assert validate_email(email)

# Composite strategies
from hypothesis import strategies as st
from hypothesis.strategies import composite

@composite
def users(draw) -> User:
    """Strategy that generates User instances."""
    return User(
        id=draw(st.integers(min_value=1)),
        name=draw(st.text(min_size=1, max_size=50)),
        email=draw(st.emails()),
        age=draw(st.integers(min_value=18, max_value=120))
    )

@given(users())
def test_user_creation(user: User) -> None:
    """Generated users satisfy their invariants."""
    assert user.age >= 18
    assert len(user.name) > 0
```

## Test Organization

See **Test Layout** in SKILL.md for the rules; this is the mechanical detail.

Mirror the source **packages** to subpackage depth and name files for **behaviour**. Do not split the
tree into `unit/` and `integration/`: that groups by a property of the test rather than by the code
under test, so finding "the tests for orders" means looking in two places, and a test that grows a
database dependency has to move directories. Use a marker if the distinction matters at runtime:

```python
# pyproject.toml
# [tool.pytest.ini_options]
# markers = ["slow: needs external services"]

@pytest.mark.slow()
async def test_against_real_backend() -> None:
    """Exercise the path the in-memory backend cannot run."""
```

```
tests/
  __init__.py                    # required — see below
  conftest.py                    # shared fixtures
  test_architecture.py           # guards on the codebase itself
  core/
    __init__.py
    mongo/
      __init__.py
      test_links.py
      test_repository.py
  domains/
    __init__.py
    orders/
      __init__.py
      test_models.py
      test_pricing.py            # behaviour, not a module name
```

### Why every directory needs `__init__.py`

Pytest's default `prepend` import mode derives a module's importable name by walking up while
`__init__.py` files exist, then puts the directory where the walk stopped on `sys.path`. Two distinct
failures follow from a missing one, and neither error message names the missing file:

| Missing marker | Failure |
| --- | --- |
| `tests/__init__.py` | Project root never reaches `sys.path`; collection dies in `conftest.py` with `ModuleNotFoundError: No module named 'app'` |
| A nested `__init__.py` | Module names truncate — `tests/core/email/test_client.py` imports as `email.test_client`, shadowing the stdlib `email` package |

Fully-qualified names are also what let two `test_models.py` files coexist in different directories.
Without them pytest reports an "import file mismatch" on the second one.

The alternative is `--import-mode=importlib`, which removes the `sys.path` manipulation entirely and
does not need the markers. It is the better mode for new projects; the markers are what you need when
using the default.

### Fixture factory pattern

```python
@pytest.fixture()
def user_factory(db_session: Session):
    """Provide a factory that creates and cleans up users."""
    created_users: list[User] = []

    def _create_user(
        name: str = "Test User",
        email: str | None = None,
        **kwargs
    ) -> User:
        """Create and persist a user."""
        if email is None:
            email = f"{name.lower().replace(' ', '.')}@example.com"

        user = User(name=name, email=email, **kwargs)
        db_session.add(user)
        db_session.commit()
        created_users.append(user)
        return user

    yield _create_user

    # Cleanup
    for user in created_users:
        db_session.delete(user)
    db_session.commit()
```

## Snapshot Testing

```python
import pytest
from syrupy.assertion import SnapshotAssertion

def test_api_response(snapshot: SnapshotAssertion) -> None:
    """Match the API response against a snapshot."""
    response = api.get_user(1)
    assert response == snapshot

def test_rendered_template(snapshot: SnapshotAssertion) -> None:
    """Match rendered HTML against a snapshot."""
    html = render_template("user.html", user=get_user(1))
    assert html == snapshot
```
