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
