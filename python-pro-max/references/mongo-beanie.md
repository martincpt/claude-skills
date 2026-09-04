# MongoDB with Beanie

**Beanie is the default MongoDB ODM.** It's async (built on PyMongo's `AsyncMongoClient`)
and Pydantic-based — a `Document` _is_ a Pydantic model, so the same modeling rules apply
(strict types, no bare dicts; see the Data Modeling section in `SKILL.md`). MongoDB access
goes through a single connector class that also swaps in an in-memory mock for tests — and
the mock is fully self-contained, so testing mode works from a plain `init(is_testing=True)`
call without any pytest fixture.

> This reference covers the **connection**: documents, the connector, and the test backend. The
> **data-access layer** built on top of it — the generic `Repository` ladder, write schemas, the
> service boundary, and dependency injection — is `references/repositories-and-services.md`. Read
> that one before writing a query anywhere outside a repository.

## Document Models

A `Document` is a Pydantic model bound to a collection. Declare the collection name (and any
indexes) in a nested `Settings` class.

```python
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
```

## Connector

Keep the integration in a `mongo` package under the main package, with the connector and
its test fixture co-located:

```
app/mongo/
├── __init__.py     # re-exports MongoWithBeanie
├── connector.py    # the connector
├── mock.py         # MongomockCompat — in-memory-Mongo shims (test-only)
└── fixtures.py     # the pytest fixture
```

```python
# app/mongo/__init__.py
"""Mongo with Beanie integration."""

from .connector import MongoWithBeanie

__all__ = [MongoWithBeanie.__name__]
```

`MongoWithBeanie` owns the client, database, and Beanie initialization. `init` is a
classmethod that builds a single shared instance; in testing mode it applies the
`MongomockCompat` shims (see below) and swaps the real client for `mongomock_motor`'s mock.
Because `init` installs the shims itself, testing mode is self-contained — it works from the
CLI or a script, not just under the pytest fixture. Document models are discovered by
importing the configured modules and collecting every `Document` subclass.

```python
# app/mongo/connector.py
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
```

Wire it into the application's lifecycle with the `lifespan` context manager. It reads
settings, calls `init` on entry and `close` on exit, so callers don't repeat the wiring —
and it's framework-agnostic:

```python
# As a FastAPI lifespan:
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage app-scoped resources, including the Mongo connection."""
    async with MongoWithBeanie.lifespan():
        yield


app = FastAPI(lifespan=lifespan)

# Or directly — in a worker, script, or test harness:
async with MongoWithBeanie.lifespan():
    ...  # the connection is live here; closed on exit
```

If you need the connection outside a `lifespan` scope, `init`/`close` remain available to call
directly.

## Query construction: operators and expressions, never a mapping literal

Beanie accepts a raw pymongo mapping and its own constructs interchangeably, so a codebase drifts
into using both unless the choice is made once. Make it: **every query and update is built from
Beanie's own constructs.**

- **A comparison expression** for a field predicate — `Product.category == slug`,
  `Category.parent.id == category.id`.
- **An operator** from `beanie.operators` for everything else — `In`, `Or`, `And`, `RegEx`, `Set`,
  `AddToSet`, `Pull`, `Inc`, `Unset`.

A hand-written `{"$set": {...}}` or `{"$or": [...]}` is not a neutral alternative spelling. **It is
the one with a failure mode.** A mapping names its fields as strings that nothing resolves, so
renaming a field leaves every mapping referencing it running and matching *nothing* — no error, no
warning, just a shorter result set indistinguishable from an honest empty. An expression is resolved
against the model where it is written, so the same rename fails there instead.

```python
import re

from beanie.operators import AddToSet, In, Or, RegEx, Set

# Bad — field names are strings; a rename silently empties the result:
await Product.find({"category": old_slug}).update({"$set": {"category": new_slug}})
await Snapshot.find({"_id": snapshot_id}).update({"$set": {"status": "processed"}})
pattern = {"$regex": re.escape(term), "$options": "i"}
products = Product.find({"$or": [{"name": pattern}, {"sku": pattern}]})

# Good — resolved against the model, so a rename fails at the expression:
await Product.find(Product.category == old_slug).update(Set({Product.category: new_slug}))
await Snapshot.find(Snapshot.id == snapshot_id).update(Set({Snapshot.status: Status.processed}))
pattern = re.escape(term)
products = Product.find(
    Or(RegEx(Product.name, pattern, "i"), RegEx(Product.sku, pattern, "i")),
)
```

**Equality is `field == value`, never the `Eq` operator.** Beanie supports the comparison directly,
and it is the form that reads as an expression. Admitting `Eq(field, value)` alongside it would
reintroduce exactly the two-spellings-for-one-query problem the rule exists to remove.

**Two exceptions, each because no expression exists to write:**

1. **A field path assembled at runtime from partial strings** — `f"attributes.{index}.slug"`,
   `f"translations.{locale}.name"` — may be a mapping, since the path is not known statically and so
   cannot resolve against the model. Where the operation has an operator, pass the runtime mapping
   *through* it, so the operator boundary stays visible even where the path is dynamic:

   ```python
   # Good — dynamic paths, still inside the operator:
   changes = {f"attributes.{i}.slug": new_slug for i, a in enumerate(product.attributes) if ...}
   await product.update(Set(changes))

   # Bad — the mapping escapes the operator for no reason:
   await product.update({"$set": changes})
   ```

2. **An operation Beanie provides no operator for** may be a mapping or a direct driver call
   (`collection.distinct(...)`).

### Type the query entry points as Beanie does

A repository method that forwards expressions should declare Beanie's own argument type rather than
`Any`:

```python
def query(
    self,
    *expressions: Mapping[Any, Any] | bool,
    sort: Any = None,
    skip: int | None = None,
    limit: int | None = None,
) -> QueryResult[T]: ...
```

The two arms are not decorative. `Mapping` admits the operator objects — `BaseOperator` subclasses
`collections.abc.Mapping` — and `bool` admits `Model.field == value`, which a type checker reads as
`bool` because Beanie's runtime substitution of an `ExpressionField` is invisible to static analysis.

**Declaring it on your own method is what makes it enforceable, and this is worth knowing precisely.**
A typical pre-commit mypy hook installs only `pydantic` into its isolated environment, and with
`ignore_missing_imports = true` every `beanie` import then resolves to `Any` — `reveal_type(Document)`
and `reveal_type(Document.find)` both report `Any` there, so **Beanie's own signature constrains
nothing in the gate**. `Mapping` comes from the standard library, so an annotation written in your
own module survives the unresolved import and still rejects a bad call. Measured: with the parameter
typed `Any`, `self.query(42)` passes the hook; typed `Mapping[Any, Any] | bool`, it fails with
`expected "Mapping[Any, Any] | bool"`.

(The other way to close that gap is to add `beanie` to the hook's `additional_dependencies`. Worth
doing — but it surfaces every error the missing package was hiding, so it is its own piece of work,
and the annotation is worth having either way.)

### Guard it with a test

The rule is mechanical, so let a test hold it rather than a review. A dict *literal* carrying a
`$`-prefixed key is precisely the hand-written form, and it needs no exception list — both permitted
exceptions build their mapping at runtime, so neither is a literal:

```python
def test_queries_use_operators_not_mapping_literals() -> None:
    """No query is written as a mapping literal with a Mongo operator key."""
    offenders: list[str] = []

    for path in data_access_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue

            operator_keys = [
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value.startswith("$")
            ]

            if operator_keys:
                offenders.append(f"{path}:{node.lineno}: {operator_keys}")

    assert not offenders, f"queries written as mapping literals: {offenders}"
```

Check such a guard against the code *before* the cleanup — if it does not flag the sites you just
converted, it is not testing what you think it is.

## Testing

`mongomock-motor` doesn't implement every API surface Beanie touches during init and
querying, so an in-memory test DB needs a handful of shims (DBRef lookups, async `aggregate`
and `close` wrappers, `list_collection_names` kwargs). Keep those in a dedicated `mock.py`
behind a `MongomockCompat` installer rather than inline in the fixture. The installer is:

- **Idempotent and process-wide** — `apply()` runs the patches once (`_applied` guard) and is
  safe to call from many entry points. It wraps the mongomock originals in place, so calling
  it twice would otherwise nest the wrappers.
- **Owned by the connector** — `MongoWithBeanie.init(is_testing=True)` calls
  `MongomockCompat.apply()` itself, so the shims land whether you enter through the pytest
  fixture, a CLI command, or a script. The fixture no longer has to patch anything.
- **Test-only** — it imports `mongomock`/`mongomock-motor` (dev dependencies), so it must only
  be imported on the testing path (the local import inside `init` keeps it out of production).

```python
# app/mongo/mock.py
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
```

Because `init` installs the shims, the `mongo` fixture shrinks to just standing up the
connection and cleaning up afterwards. Tests get a fully initialized Beanie connection and a
clean database each run. Expose it to the suite by registering the module as a plugin in
`tests/conftest.py`:

```python
# tests/conftest.py
pytest_plugins = ["app.mongo.fixtures"]
```

See `testing.md` for the broader pytest setup.

```python
# app/mongo/fixtures.py
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

    # Clear documents, not the database: dropping it drops the indexes, recreated once per session.
    for collection_name in await mongo.database.list_collection_names():
        await mongo.database[collection_name].delete_many({})


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
```

## Dependencies

```toml
[project.optional-dependencies]
# Runtime: enable the Mongo/Beanie integration with `uv sync --extra beanie`
beanie = [
    "beanie>=2.0.0",
    "pydantic[email]>=2.10.0",  # for EmailStr
]

[dependency-groups]
dev = [
    "mongomock-motor>=0.0.35",  # in-memory MongoDB for tests
    "pytest-asyncio>=0.25.0",
    "pytest-mock>=3.14.0",
]
```

`beanie` pulls in `pymongo`; `mongomock-motor` (test-only) provides the in-memory client that
`MongomockCompat` patches and the `mongo` fixture relies on.

## Next: the data-access layer

Application code should not call `Document.find()` directly. Queries and writes live behind a
repository per document type, with writes opted into one operation at a time and the writable field
set declared as a Pydantic schema; anything that *decides* — a guard, an ordering, a rollback —
lives in a service that composes those repositories. See
`references/repositories-and-services.md`, which also records the two measured Beanie behaviours
(late validation on a partial `$set`, and an embedded copy written for a raw `Link` payload) that
its update path exists to contain.
