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
                return cls.instance  # use one shared instance of across all tests

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
