# MongoDB with Beanie

**Beanie is the default MongoDB ODM.** It's async (built on PyMongo's `AsyncMongoClient`)
and Pydantic-based — a `Document` _is_ a Pydantic model, so the same modeling rules apply
(strict types, no bare dicts; see the Data Modeling section in `SKILL.md`). MongoDB access
goes through a single connector class that also swaps in an in-memory mock for tests — and
the mock is fully self-contained, so testing mode works from a plain `init(is_testing=True)`
call without any pytest fixture.

## Document Models

A `Document` is a Pydantic model bound to a collection. Declare the collection name (and any
indexes) in a nested `Settings` class.

```python
import pymongo
from beanie import Document
from pydantic import EmailStr


class User(Document):
    """A user document — a Pydantic model persisted to MongoDB."""

    name: str
    email: EmailStr
    active: bool = True

    class Settings:
        """Beanie collection settings."""

        name = "users"  # MongoDB collection name
        indexes = [
            pymongo.IndexModel([("email", pymongo.ASCENDING)], unique=True),
        ]
```

## Connector

Keep the integration in a `mongo` package under the main package, with the connector and
its test fixture co-located:

```
app/mongo/
├── __init__.py     # re-exports MongoWithBeanie
├── connector.py    # the connector
├── mock.py         # MongomockCompat — in-memory-Mongo shims (test-only)
└── fixtures.py     # the pytest fixture
```

```python
# app/mongo/__init__.py
"""Mongo with Beanie integration."""

from .connector import MongoWithBeanie

__all__ = [MongoWithBeanie.__name__]
```

`MongoWithBeanie` owns the client, database, and Beanie initialization. `init` is a
classmethod that builds a single shared instance; in testing mode it applies the
`MongomockCompat` shims (see below) and swaps the real client for `mongomock_motor`'s mock.
Because `init` installs the shims itself, testing mode is self-contained — it works from the
CLI or a script, not just under the pytest fixture. Document models are discovered by
importing the configured modules and collecting every `Document` subclass.

```python
# app/mongo/connector.py
"""Mongo with Beanie connector."""

import importlib
import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import ClassVar

from beanie import Document, init_beanie
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import settings


class MongoWithBeanie:
    """MongoDB initializer for Beanie."""

    instance: ClassVar["MongoWithBeanie"]

    client: AsyncMongoClient
    database: AsyncDatabase
    document_model_modules: list[str]
    is_testing: bool

    def __init__(
        self,
        client: AsyncMongoClient,
        database_name: str,
        document_model_modules: list[str],
        is_testing: bool = False,
    ) -> None:
        """Initialize the MongoWithBeanie instance."""
        self.client = client
        self.database = self.client.get_database(database_name)
        self.document_model_modules = document_model_modules
        self.is_testing = is_testing

    @classmethod
    async def init(
        cls,
        host: str,
        database_name: str,
        document_model_modules: list[str],
        is_testing: bool = False,
        **kwargs,
    ) -> "MongoWithBeanie":
        """Initialize Mongo with Beanie, returning a single shared instance."""
        if is_testing:
            if hasattr(cls, "instance"):
                return cls.instance  # one shared instance across all tests

            from mongomock_motor import AsyncMongoMockClient

            from .mock import MongomockCompat

            MongomockCompat.apply()  # bridge mongomock <-> Beanie before init

            mongo_client_cls: type[AsyncMongoClient] = AsyncMongoMockClient
        else:
            mongo_client_cls = AsyncMongoClient

        client = mongo_client_cls(host)
        cls.instance = cls(client, database_name, document_model_modules, is_testing)
        await cls.instance.init_beanie(**kwargs)
        return cls.instance

    async def init_beanie(self, **kwargs) -> None:
        """Initialize Beanie with the discovered document models."""
        models = self.get_document_models()

        await init_beanie(database=self.database, document_models=models, **kwargs)

    def get_document_models(self) -> list[type[Document]]:
        """Collect every `Document` subclass from the configured modules."""
        document_models: list[type[Document]] = []

        for module_path in self.document_model_modules:
            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                message = f"Error importing document model module '{module_path}'"
                raise ImportError(message) from e

            for _name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Document)
                    and obj is not Document
                ):
                    document_models.append(obj)

        return document_models

    @classmethod
    async def close(cls) -> None:
        """Close the database connection."""
        await cls.instance.client.close()

    @classmethod
    @asynccontextmanager
    async def lifespan(cls, is_testing: bool | None = None) -> AsyncIterator[None]:
        """Open the connection on entry and close it on exit.

        Framework-agnostic: use as a FastAPI `lifespan`, in worker startup, or
        directly via `async with MongoWithBeanie.lifespan(): ...`.

        Args:
            is_testing: Force the mock (`True`) or real (`False`) client, overriding
                the settings-derived default. `None` keeps `settings.is_testing`, so
                existing callers are unaffected.

        """
        resolved_is_testing = settings.is_testing if is_testing is None else is_testing

        await cls.init(
            host=settings.mongo_uri,
            database_name=settings.mongo_db_name,
            document_model_modules=settings.document_model_modules,
            is_testing=resolved_is_testing,
        )

        try:
            yield
        finally:
            await cls.close()
```

Wire it into the application's lifecycle with the `lifespan` context manager. It reads
settings, calls `init` on entry and `close` on exit, so callers don't repeat the wiring —
and it's framework-agnostic:

```python
# As a FastAPI lifespan:
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage app-scoped resources, including the Mongo connection."""
    async with MongoWithBeanie.lifespan():
        yield


app = FastAPI(lifespan=lifespan)

# Or directly — in a worker, script, or test harness:
async with MongoWithBeanie.lifespan():
    ...  # the connection is live here; closed on exit
```

If you need the connection outside a `lifespan` scope, `init`/`close` remain available to call
directly.

## Testing

`mongomock-motor` doesn't implement every API surface Beanie touches during init and
querying, so an in-memory test DB needs a handful of shims (DBRef lookups, async `aggregate`
and `close` wrappers, `list_collection_names` kwargs). Keep those in a dedicated `mock.py`
behind a `MongomockCompat` installer rather than inline in the fixture. The installer is:

- **Idempotent and process-wide** — `apply()` runs the patches once (`_applied` guard) and is
  safe to call from many entry points. It wraps the mongomock originals in place, so calling
  it twice would otherwise nest the wrappers.
- **Owned by the connector** — `MongoWithBeanie.init(is_testing=True)` calls
  `MongomockCompat.apply()` itself, so the shims land whether you enter through the pytest
  fixture, a CLI command, or a script. The fixture no longer has to patch anything.
- **Test-only** — it imports `mongomock`/`mongomock-motor` (dev dependencies), so it must only
  be imported on the testing path (the local import inside `init` keeps it out of production).

```python
# app/mongo/mock.py
"""In-memory Mongo (mongomock) compatibility shims for Beanie.

`mongomock-motor` does not implement every API surface Beanie exercises during init and
querying. These patches bridge the gaps so `is_testing=True` yields a working in-memory
database — both under pytest and from the CLI. They are applied once, process-wide, and are
idempotent (wrapping the originals more than once would nest the wrappers).

This module imports `mongomock`/`mongomock-motor` (dev-only dependencies), so it must only be
imported on the testing path — never in production.
"""

from collections.abc import Iterable
from typing import Any

import mongomock.filtering
from bson import DBRef
from mongomock import Database
from mongomock import MongoClient as SyncMongoClient
from mongomock_motor import AsyncMongoMockCollection


class MongomockCompat:
    """Idempotent installer for the mongomock ↔ Beanie compatibility patches."""

    _applied: bool = False

    @classmethod
    def apply(cls) -> None:
        """Patch mongomock/mongomock-motor so Beanie can run against it; runs once."""
        if cls._applied:
            return

        cls._patch_iter_key_candidates()
        cls._patch_aggregate()
        cls._patch_close()
        cls._patch_list_collection_names()

        cls._applied = True

    @staticmethod
    def _patch_iter_key_candidates() -> None:
        """Resolve key candidates for DBRefs, which mongomock otherwise mishandles."""
        original = mongomock.filtering.iter_key_candidates

        def patched(key: str, doc: Any) -> Iterable[Any]:
            """Handle DBRefs when resolving key candidates."""
            if isinstance(doc, DBRef):
                return [doc.as_doc().get(key, None)]
            return original(key, doc)

        mongomock.filtering.iter_key_candidates = patched

    @staticmethod
    def _patch_aggregate() -> None:
        """Wrap mongomock's synchronous `aggregate` so it can be awaited."""
        original = AsyncMongoMockCollection.aggregate

        async def patched(*args: Any, **kwargs: Any) -> Iterable[Any]:
            """Async wrapper around mongomock's synchronous aggregate."""
            return original(*args, **kwargs)

        AsyncMongoMockCollection.aggregate = patched

    @staticmethod
    def _patch_close() -> None:
        """Wrap mongomock's synchronous `close` so it can be awaited."""
        original = SyncMongoClient.close

        async def patched(*args: Any, **kwargs: Any) -> None:
            """Async wrapper around mongomock's synchronous close."""
            original(*args, **kwargs)

        SyncMongoClient.close = patched

    @staticmethod
    def _patch_list_collection_names() -> None:
        """Let `list_collection_names` accept and ignore async-client kwargs."""
        original = Database.list_collection_names

        def patched(*args: Any, **kwargs: Any) -> list[str]:  # noqa: ARG001
            """Drop the async-only kwargs (e.g. authorizedCollections) mongomock rejects."""
            return original(*args)

        Database.list_collection_names = patched
```

Because `init` installs the shims, the `mongo` fixture shrinks to just standing up the
connection and cleaning up afterwards. Tests get a fully initialized Beanie connection and a
clean database each run. Expose it to the suite by registering the module as a plugin in
`tests/conftest.py`:

```python
# tests/conftest.py
pytest_plugins = ["app.mongo.fixtures"]
```

See `testing.md` for the broader pytest setup.

```python
# app/mongo/fixtures.py
"""Pytest fixtures for the Beanie ODM integration."""

from collections.abc import AsyncIterable
from unittest.mock import _AsyncIterator  # type: ignore[attr-defined]

import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient
from pytest_mock import MockerFixture

from app.config import settings

from .connector import MongoWithBeanie


@pytest_asyncio.fixture()
async def mongo() -> AsyncIterable[MongoWithBeanie]:
    """Mongo with Beanie fixture backed by an in-memory mock.

    The mongomock <-> Beanie compatibility shims are applied by
    `MongoWithBeanie.init(is_testing=True)` (see `mock.py`), so this fixture only has to
    initialize the connection and clean up afterwards.
    """
    mongo = await MongoWithBeanie.init(
        host="mongodb://mock:password@localhost:27017",
        database_name="mock_db",
        document_model_modules=settings.document_model_modules,
        is_testing=True,
    )

    # Sanity-check we really got the mock, not a live connection
    if not isinstance(mongo.client, AsyncMongoMockClient):
        message = "Mongo client is not an instance of AsyncMongoMockClient."
        raise TypeError(message)

    if mongo.database.name != "mock_db":
        message = "Mongo database name is not set to 'mock_db'."
        raise ValueError(message)

    yield mongo

    # Clean up: drop the database so each test starts fresh
    await mongo.client.drop_database(mongo.database.name)


def mock_cursor_query(mocker: MockerFixture, items: list) -> None:
    """Mock a Beanie find cursor to yield a fixed list of items."""
    mocker.patch(
        "beanie.odm.queries.cursor.BaseCursorQuery.__aiter__",
        return_value=_AsyncIterator(iter(items)),
    )
    mocker.patch(
        "beanie.odm.queries.find.FindMany.count",
        return_value=len(items),
    )
```

## Dependencies

```toml
[project.optional-dependencies]
# Runtime: enable the Mongo/Beanie integration with `uv sync --extra beanie`
beanie = [
    "beanie>=2.0.0",
    "pydantic[email]>=2.10.0",  # for EmailStr
]

[dependency-groups]
dev = [
    "mongomock-motor>=0.0.35",  # in-memory MongoDB for tests
    "pytest-asyncio>=0.25.0",
    "pytest-mock>=3.14.0",
]
```

`beanie` pulls in `pymongo`; `mongomock-motor` (test-only) provides the in-memory client that
`MongomockCompat` patches and the `mongo` fixture relies on.
