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

from app.config import settings

from .connector import MongoWithBeanie


@pytest_asyncio.fixture()
async def mongo(mocker: MockerFixture) -> AsyncIterable[MongoWithBeanie]:
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
    mongo = await MongoWithBeanie.init(
        host="mongodb://mock:password@localhost:27017",
        database_name="mock_db",
        document_model_modules=settings.document_model_modules,
        is_testing=True,
    )

    # Sanity-check we really got the mock, not a live connection
    if not isinstance(mongo.client, AsyncMongoMockClient):
        msg = "Mongo client is not an instance of AsyncMongoMockClient."
        raise TypeError(msg)

    if mongo.database.name != "mock_db":
        msg = "Mongo database name is not set to 'mock_db'."
        raise ValueError(msg)

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
