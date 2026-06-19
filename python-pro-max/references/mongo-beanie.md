# MongoDB with Beanie

**Beanie is the default MongoDB ODM.** It's async (built on PyMongo's `AsyncMongoClient`)
and Pydantic-based — a `Document` _is_ a Pydantic model, so the same modeling rules apply
(strict types, no bare dicts; see the Data Modeling section in `SKILL.md`). MongoDB access
goes through a single connector class that also swaps in an in-memory mock for tests.

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

`MongoWithBeanie` owns the client, database, and Beanie initialization. `init` is a
classmethod that builds a single shared instance; in testing mode it swaps the real client
for `mongomock_motor`'s mock. Document models are discovered by importing the configured
modules and collecting every `Document` subclass.

```python
# app/mongo.py  (or my_project/mongo.py)
"""Mongo with Beanie integration."""

import importlib
import inspect
from typing import ClassVar

from beanie import Document, init_beanie
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase


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
        """Initialize Mongo with Beanie."""
        if is_testing:
            if hasattr(cls, "instance"):
                return cls.instance  # one shared instance across all tests

            from mongomock_motor import AsyncMongoMockClient

            mongo_client_cls = AsyncMongoMockClient
        else:
            mongo_client_cls = AsyncMongoClient

        client = mongo_client_cls(host)
        cls.instance = cls(client, database_name, document_model_modules, is_testing)
        await cls.instance.init_beanie(**kwargs)
        return cls.instance

    async def init_beanie(self, **kwargs) -> None:
        """Initialize Beanie."""
        models = self.get_document_models()

        await init_beanie(
            database=self.database,
            document_models=models,
            **kwargs,
        )

    def get_document_models(self) -> list[type[Document]]:
        """Get all document models."""
        document_models = []

        for module_path in self.document_model_modules:
            try:
                module = importlib.import_module(module_path)
                for _name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, Document)
                        and obj != Document
                    ):
                        document_models.append(obj)

            except ImportError as e:
                msg = f"Error importing document model module '{module_path}'"
                raise ImportError(msg) from e

        return document_models

    @classmethod
    async def close(cls) -> None:
        """Close the database connection."""
        await cls.instance.client.close()
```

Wire it into the application's lifecycle — initialize on startup, close on shutdown:

```python
from app.config import settings

await MongoWithBeanie.init(
    host=settings.mongo_uri,
    database_name=settings.mongo_db_name,
    document_model_modules=settings.document_model_modules,
)
# ... on shutdown:
await MongoWithBeanie.close()
```

## Testing

The `mongo_client` fixture stands up an in-memory MongoDB via `mongomock_motor` and patches
the gaps so it behaves like the real async client (DBRef/UUID lookups, async `aggregate`
and `close` wrappers, `list_collection_names` kwargs). Tests get a fully initialized Beanie
connection and a clean database each run. See `testing.md` for the broader pytest setup.

```python
# tests/conftest.py
"""Fixtures for the Beanie ODM integration."""

from collections.abc import AsyncIterable, Iterable
from typing import Any
from unittest.mock import _AsyncIterator  # type: ignore[attr-defined]

import pytest_asyncio
from bson import DBRef
from mongomock import Database
from mongomock import MongoClient as SyncMongoClient
from mongomock.filtering import iter_key_candidates
from mongomock_motor import AsyncMongoMockClient, AsyncMongoMockCollection
from pytest_mock import MockerFixture

from app.mongo import MongoWithBeanie


@pytest_asyncio.fixture()
async def mongo_client(mocker: MockerFixture) -> AsyncIterable[MongoWithBeanie]:
    """Mongo with Beanie fixture backed by an in-memory mock."""

    # Patch iter_key_candidates to handle DBRefs and UUIDs
    def iter_key_candidates_patched(key: str, doc: Any) -> Iterable[Any]:
        """Patched iter_key_candidates to handle DBRefs and UUIDs."""
        if isinstance(doc, DBRef):
            return [doc.as_doc().get(key, None)]
        return iter_key_candidates(key, doc)

    mocker.patch(
        "mongomock.filtering.iter_key_candidates",
        iter_key_candidates_patched,
    )

    # Wrap mongomock's sync aggregate/close so they're awaitable like the async client
    original_aggregate = AsyncMongoMockCollection.aggregate

    async def patched_aggregate(*args, **kwargs) -> Iterable[Any]:
        """Async wrapper for the synchronous aggregate method in mongomock."""
        return original_aggregate(*args, **kwargs)

    mocker.patch(
        "mongomock_motor.AsyncMongoMockCollection.aggregate",
        patched_aggregate,
    )

    original_close = SyncMongoClient.close

    async def patched_close(*args, **kwargs) -> None:
        """Async wrapper for the synchronous close method in mongomock."""
        return original_close(*args, **kwargs)

    mocker.patch("mongomock.MongoClient.close", patched_close)

    # Let list_collection_names accept (and ignore) kwargs the async client passes
    original_list_collection_names = Database.list_collection_names

    def patched_list_collection_names(*args, **kwargs) -> list[str]:  # noqa: ARG001
        return original_list_collection_names(*args)

    mocker.patch(
        "mongomock.Database.list_collection_names",
        patched_list_collection_names,
    )

    # Initialize the connector in testing mode (swaps in the mock client)
    mongo_with_beanie = await MongoWithBeanie.init(
        host="mongodb://mock:password@localhost:27017",
        database_name="mock_db",
        document_model_modules=["app.models"],
        is_testing=True,
    )

    # Sanity-check we really got the mock, not a live connection
    if not isinstance(mongo_with_beanie.client, AsyncMongoMockClient):
        msg = "Mongo client is not an instance of AsyncMongoMockClient."
        raise TypeError(msg)

    if mongo_with_beanie.database.name != "mock_db":
        msg = "Mongo database name is not set to 'mock_db'."
        raise ValueError(msg)

    yield mongo_with_beanie

    # Clean up: drop the database so each test starts fresh
    await mongo_with_beanie.client.drop_database(mongo_with_beanie.database.name)


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

`beanie` pulls in `pymongo`; `mongomock-motor` (test-only) provides the in-memory client the
`mongo_client` fixture relies on.
