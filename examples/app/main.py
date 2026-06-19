"""Application lifecycle and entry points."""

import asyncio

from app.config import settings
from app.mongo import MongoWithBeanie


async def startup() -> None:
    """Initialize application resources (database, etc.)."""
    await MongoWithBeanie.init(
        host=settings.mongo_uri,
        database_name=settings.mongo_db_name,
        document_model_modules=settings.document_model_modules,
        is_testing=settings.is_testing,
    )


async def shutdown() -> None:
    """Release application resources."""
    await MongoWithBeanie.close()


async def serve() -> None:
    """Start the application and run until interrupted."""
    await startup()
    try:
        # Replace with the real server / worker loop (e.g. uvicorn, a task runner).
        await asyncio.Event().wait()
    finally:
        await shutdown()
