"""Shared pytest configuration."""

# Expose the Mongo/Beanie fixture (`mongo`) to the whole suite.
pytest_plugins = ["app.mongo.fixtures"]
