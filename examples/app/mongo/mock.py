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
