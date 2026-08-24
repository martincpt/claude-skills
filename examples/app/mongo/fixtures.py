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
