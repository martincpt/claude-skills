"""Beanie document models."""

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


__all__ = [User.__name__]
