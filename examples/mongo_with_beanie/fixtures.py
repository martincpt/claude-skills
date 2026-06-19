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

from .connector import MongoWithBeanie

@pytest_asyncio.fixture()
async def mongo_client(mocker: MockerFixture) -> AsyncIterable[MongoWithBeanie]:
    """Mongo with Beanie fixture."""

    # ----------------------------------------------------
    # Patch iter_key_candidates to handle DBRefs and UUIDs
    # ----------------------------------------------------
    def iter_key_candidates_patched(key: str, doc: Any) -> Iterable[Any]:
        """Patched iter_key_candidates to handle DBrefs and UUIDs."""
        if isinstance(doc, DBRef):
            return [doc.as_doc().get(key, None)]

        return iter_key_candidates(key, doc)

    mocker.patch(
        "mongomock.filtering.iter_key_candidates",
        iter_key_candidates_patched,
    )
    # ----------------------------------------------------

    # ----------------------------------------------------
    # Patch AsyncIOMotorCollection.aggregate to wrap motor's synchronous calls
    # |_ This is necessary because aggregate method changed to async in
    # |_ PyMongo's asynchronous client but we still use mongomock motor for testing.
    # ----------------------------------------------------
    original_aggregate = AsyncMongoMockCollection.aggregate

    async def patched_aggregate(*args, **kwargs) -> Iterable[Any]:
        """Async wrapper for the synchronous aggregate method in mongomock."""
        return original_aggregate(*args, **kwargs)

    mocker.patch(
        "mongomock_motor.AsyncMongoMockCollection.aggregate",
        patched_aggregate,
    )
    # ----------------------------------------------------

    # ----------------------------------------------------
    # Patch SyncMongoClient.close to wrap motor's synchronous calls
    # |_ This is necessary because close method changed to async in
    # |_ PyMongo's asynchronous client but we still use mongomock motor for testing.
    # ----------------------------------------------------
    original_close = SyncMongoClient.close

    async def patched_close(*args, **kwargs) -> None:
        """Async wrapper for the synchronous close method in mongomock."""
        return original_close(*args, **kwargs)

    mocker.patch(
        "mongomock.MongoClient.close",
        patched_close,
    )
    # ----------------------------------------------------

    # ----------------------------------------------------
    # Patch Database.list_collection_names to accept **kwargs
    # ----------------------------------------------------
    original_list_collection_names = Database.list_collection_names

    def patched_list_collection_names(*args, **kwargs) -> list[str]:  # noqa: ARG001
        return original_list_collection_names(*args)

    mocker.patch(
        "mongomock.Database.list_collection_names",
        patched_list_collection_names,
    )
    # ----------------------------------------------------

    # ----------------------------------------------------
    # Initialize MongoDB client
    # ----------------------------------------------------
    mongo_with_beanie = await MongoWithBeanie.init(
        host="mongodb://mock:password@localhost:27017",
        database_name="mock_db",
        is_testing=True,
    )
    # ----------------------------------------------------

    # ----------------------------------------------------
    # Validate MongoDB client
    # ----------------------------------------------------
    if not isinstance(mongo_with_beanie.client, AsyncMongoMockClient):
        msg = "Mongo client is not an instance of AsyncMongoMockClient."
        raise TypeError(msg)

    if mongo_with_beanie.database.name != "mock_db":
        msg = "Mongo database name is not set to 'mock_db'."
        raise ValueError(msg)
    # ----------------------------------------------------

    yield mongo_with_beanie

    # ----------------------------------------------------
    # Clean up
    # ----------------------------------------------------
    await mongo_with_beanie.client.drop_database(mongo_with_beanie.database.name)
    # ----------------------------------------------------


def mock_cursor_query(mocker: MockerFixture, items: list) -> None:
    """Mock cursor query."""
    mocker.patch(
        "beanie.odm.queries.cursor.BaseCursorQuery.__aiter__",
        return_value=_AsyncIterator(iter(items)),
    )
    mocker.patch(
        "beanie.odm.queries.find.FindMany.count",
        return_value=len(items),
    )
