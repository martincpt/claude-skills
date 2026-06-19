"""Tests for the application."""

from app.models import User
from app.mongo import MongoWithBeanie


async def test_create_and_read_user(mongo: MongoWithBeanie) -> None:  # noqa: ARG001
    """Persist a user and read it back through Beanie."""
    created = await User(name="Ada", email="ada@example.com").insert()

    found = await User.get(created.id)

    assert found is not None
    assert found.email == "ada@example.com"
