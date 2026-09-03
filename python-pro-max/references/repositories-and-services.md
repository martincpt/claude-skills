# Repositories and Services

Two layers sit between the documents and everything that uses them, and the boundary between them
is one sentence:

> **Repositories carry mechanism. Services carry policy.**

A repository *may* write — it is not "the read layer" — but only operations that **decide nothing**.
Anything that decides (an ordering, a guard, a rollback, a conformance check that reads another
collection) belongs to a service. Getting this line right is what keeps a data-access class from
slowly becoming the place every rule ends up.

This reference covers both layers together because neither reads correctly alone: the repository's
job is defined by what it refuses to do, and the service's job is defined by what it composes.
Dependency injection is the seam between them, so it lives here too.

> Where these files sit in the package tree: `references/project-architecture.md`.
> The Beanie/Mongo integration the repositories build on: `references/mongo-beanie.md`.

## Contents

1. [The generic repository](#the-generic-repository) — the base ladder, copy it as-is
2. [Concrete repositories](#concrete-repositories) — what belongs on one
3. [Write schemas](#write-schemas) — what may be written is a declared type
4. [Services](#services) — when one exists, and what it holds
5. [Dependency injection](#dependency-injection) — constructor injection with a default
6. [Testing both layers](#testing-both-layers)
7. [Anti-patterns](#anti-patterns)

## The generic repository

**Writes are opted into one operation at a time.** `Repository` is read-only; `Creatable`,
`Updatable`, and `Deletable` each add exactly one operation, and `WritableRepository` composes all
three for the common case.

Splitting them is load-bearing rather than tidy. A repository whose documents are created but never
edited declares `Creatable` alone, and thereby does *not* acquire the update and delete that no
write path should have. Denying by default is the half that carries the information: a repository
added later is read-only until someone says otherwise, so the declaration marks where writing is
**intended**, not where someone remembered to forbid it.

And because a missing operation is *absent* rather than present-and-disabled, calling it is a **type
error** caught by mypy at the call site — not a runtime exception in production.

> What this does not claim: type-level absence is not a safety barrier. `await document.delete()`
> works from anywhere. It states "this repository does not write", which is static; it cannot state
> "not while referenced", which is conditional and belongs where conditions can be tested.

Copy this module into `core/mongo/repository.py` (or the equivalent) essentially verbatim — the
subtleties in `__init_subclass__` and `Updatable.update` were each measured, and simplifying them
reintroduces a silent failure.

```python
# app/core/mongo/repository.py
"""Generic data access for Beanie documents."""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar, get_args

from beanie import Document, PydanticObjectId
from beanie.odm.utils.encoder import Encoder
from pydantic import BaseModel

T = TypeVar("T", bound=Document)
CreateSchema = TypeVar("CreateSchema", bound=BaseModel)
UpdateSchema = TypeVar("UpdateSchema", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class QueryResult(Generic[T]):
    """A lazy result set: an unconsumed cursor paired with an uncounted total.

    Both halves are deferred, so a caller that wants only rows never pays for a count, and one that
    wants only a count never opens a cursor.

    **Consume within the operation that built it.** `items` is backed by a server-side cursor
    subject to an idle timeout; a result set stored in a cache or held across an interaction will
    eventually fail rather than return stale data.
    """

    items: AsyncIterator[T]
    _count: Callable[[], Awaitable[int]]

    async def count(self) -> int:
        """Return how many documents match, ignoring any skip or limit.

        Safe to call more than once. The total is produced by calling a factory each time rather
        than by awaiting a stored coroutine — a coroutine may be awaited exactly once, and callers
        routinely want a total twice ("are there any?", then "showing N of M").
        """
        return await self._count()

    async def to_list(self) -> list[T]:
        """Materialize the cursor."""
        return [document async for document in self.items]


class Repository(Generic[T]):
    """Read access to one Beanie document type."""

    document: ClassVar[type[T]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Resolve the served document type from the class's own generic arguments.

        `class CategoryRepository(WritableRepository[Category, ...])` already names `Category`;
        restating it as a class attribute underneath is a second declaration free to disagree with
        the first, and nothing would catch the disagreement.

        Three shapes:

        - A **parameterized concrete** repository resolves the first generic argument that is a
          `Document` subclass — the schema parameters beside it are `BaseModel`s and are skipped.
        - A **generic intermediate** (`Creatable`, `WritableRepository` itself) resolves nothing,
          and must: its arguments are type variables, and a naive walk taking the first one would
          bind the base's `document` to a `TypeVar` and hand every repository the same wrong
          answer. It is recognized by still having free type parameters of its own.
        - A **subclass of a concrete repository** inherits. Only the class's *own* `__orig_bases__`
          are read, since the attribute is otherwise inherited too and would re-resolve the
          parent's argument as though the subclass had declared it.

        Raises:
            TypeError: If a concrete repository resolves no document type — so the failure lands at
                import with the class named, rather than at the first read against a missing
                attribute.

        """
        super().__init_subclass__(**kwargs)

        resolved = next(
            (
                argument
                for base in vars(cls).get("__orig_bases__", ())
                for argument in get_args(base)
                if isinstance(argument, type) and issubclass(argument, Document)
            ),
            None,
        )

        if resolved is not None:
            cls.document = resolved
        # `__parameters__` is set by `Generic.__init_subclass__`, which `super()` above has
        # already run — but it is invisible to the type checker, hence the dynamic read.
        elif not getattr(cls, "__parameters__", ()) and not hasattr(cls, "document"):
            message = (
                f"{cls.__name__} resolves no document type. A concrete repository must name one "
                f"as a generic argument, as in `class {cls.__name__}(Repository[SomeDocument])`."
            )
            raise TypeError(message)

    async def read(self, _id: PydanticObjectId) -> T | None:
        """Return the document with this id, or None if there is none.

        Named `_id` after Mongo's own key. (`id` would trip ruff's A002 as a shadowed builtin.)
        """
        return await self.document.get(_id)

    def query(
        self,
        *expressions: Any,
        sort: Any = None,
        skip: int | None = None,
        limit: int | None = None,
    ) -> QueryResult[T]:
        """Build a result set from Beanie find expressions.

        Not a coroutine: it performs no I/O. Beanie's `find` builds a cursor without touching the
        database, and the count is deferred, so awaiting this would mean awaiting something that
        does nothing in order to obtain things that must be awaited later.

        Expressions are Beanie's own (`Model.field == value`) and are forwarded untouched. They are
        mappings once evaluated, so this is not about keeping dictionaries out of the query path —
        it is that an expression is resolved against the model where it is written, so a renamed
        field fails there, whereas a hand-written mapping fails silently as a query matching
        nothing.

        The cursor and the count are built from **two separate queries** sharing the same
        expressions. Beanie's `count()` honours pagination already applied to a query — over ten
        matching documents, `find(expr).limit(3).count()` returns 3 — so deriving both from one
        paginated query would report the page size the caller already knows instead of the total it
        asked for.
        """
        cursor = self.document.find(*expressions)

        if sort is not None:
            cursor = cursor.sort(sort)
        if skip is not None:
            cursor = cursor.skip(skip)
        if limit is not None:
            cursor = cursor.limit(limit)

        def count() -> Awaitable[int]:
            """Count matches on an unpaginated query built from the same expressions."""
            return self.document.find(*expressions).count()

        return QueryResult(items=cursor, _count=count)


class PayloadRepository(Repository[T]):
    """The translation both writing mixins need: a declared schema becomes a field mapping."""

    @staticmethod
    def _payload(data: BaseModel, *, changed_only: bool) -> dict[str, Any]:
        """Read a schema's fields into a mapping of field name to value.

        Values are taken with `getattr` rather than `model_dump()`, so a nested model stays a model
        and a document stays a document. That matters on the way to a `Link` field, where a dumped
        mapping would no longer be recognizable as a reference.

        Args:
            data: The create or update schema instance the caller supplied.
            changed_only: Read only the fields the caller explicitly set, which is the
                partial-update rule; False reads every field, which is a create.

        Returns:
            One entry per field read, keyed by field name.

        """
        names = data.model_fields_set if changed_only else set(type(data).model_fields)

        return {name: getattr(data, name) for name in names}


class Creatable(PayloadRepository[T], Generic[T, CreateSchema]):
    """Insertion, for repositories that opt into it."""

    async def create(self, data: CreateSchema) -> T:
        """Build a document from the create schema, insert it, and return it.

        Every field of the schema is read, so a create is total: what the schema declares is what
        the document is built from. The document's own validators run at construction, before any
        write.
        """
        return await self.document(**self._payload(data, changed_only=False)).insert()


class Updatable(PayloadRepository[T], Generic[T, UpdateSchema]):
    """Partial editing, for repositories that opt into it."""

    async def update(self, document: T, data: UpdateSchema) -> T:
        """Write the fields the caller set on the update schema, and nothing else.

        **Unset means "leave alone"; explicitly null means "clear".** Both are expressible because
        Pydantic records which fields a caller provided, so the distinction never has to be
        inferred from the value. An update that names one field cannot overwrite one it did not
        mention.

        The candidate document is **validated before the write**, and this is load-bearing rather
        than defensive: `document.set()` was measured to write first and validate afterwards while
        syncing the in-memory instance, so an invariant living only in a model validator would
        already be stored by the time it raised.

        The payload is then taken from the validated candidate **encoded through the document
        class**, not from the raw values. A `Link` field is the case that forces it: passing a
        document instance straight into `set()` stores a full embedded copy of the target instead
        of a reference, which then goes stale on the target's next edit. Encoding with the
        document's own field types produces the `DBRef` a whole-document write would have produced.

        Args:
            document: The stored document to edit.
            data: The fields to change; unset fields are left as stored.

        Returns:
            The same document, with the write applied in memory as well as in the database.

        Raises:
            ValidationError: If the resulting document would violate one of its own invariants.

        """
        changes = self._payload(data, changed_only=True)

        if not changes:
            return document

        candidate = self.document.model_validate(document.model_dump() | changes)
        encoded: dict[str, Any] = Encoder(to_db=True).encode(candidate)

        await document.set({name: encoded[name] for name in changes})

        return document


class Deletable(Repository[T]):
    """Removal, for repositories that opt into it.

    Takes no schema parameter: there is no payload to declare, only a document to remove.
    """

    async def delete(self, document: T) -> None:
        """Remove a document.

        Unconditional by design: whether the deletion is *permitted* — whether anything still
        references it — is a policy question, answered by the service before it calls this.
        """
        await document.delete()


class WritableRepository(
    Creatable[T, CreateSchema],
    Updatable[T, UpdateSchema],
    Deletable[T],
    Generic[T, CreateSchema, UpdateSchema],
):
    """All three persistence operations, for the common case that wants them together."""
```

### Two measured Beanie behaviours the update path depends on

Neither is suggested by the method names (Beanie 2.2.0, verified against MongoDB 7.0.x and the
mongomock backend alike):

- **A partial `$set` validates too late to help.** `document.set({...})` issues the write and only
  *then* re-validates while syncing the in-memory instance. An invariant that no index can enforce
  — uniqueness *within* one document's embedded list, for instance — is therefore already stored by
  the time the `ValidationError` surfaces. Hence the validate-the-candidate-first step above.
  **Test this by asserting on stored state, not on the raise**: asserting the raise alone passes
  against the broken version too.
- **A raw payload is silently wrong for a `Link` field.** `set({"parent": <Category>})` stores a
  full embedded copy of the target rather than a `DBRef`. Hence encoding through the document class.

Timestamps are safe on both paths: `save()` in Beanie 2.x is not a replace but an upsert `$set` of
the whole document routed through `update()`, exactly as `set()` is, so a `created_at`/`updated_at`
mixin sees both.

## Concrete repositories

A concrete repository names its document and its schemas as generic arguments, and adds **only
queries specific to that document**. Beanie is already a competent data-access layer; the base
carries what genuinely parameterizes on the document type, and everything else ("the latest snapshot
for this source id", "the products referencing this slug") lives on the subclass where it can use
Beanie's typed expressions instead of a hand-rolled query language.

```python
# app/domains/catalog/repository.py
"""Data access for the catalog: products and categories."""

import re
from typing import Any

from beanie.operators import In

from app.core.mongo import Creatable, QueryResult, Updatable, WritableRepository

from .models import Category, Product, ProductStatus
from .schemas import CategoryCreate, CategoryUpdate, ProductCreate, ProductUpdate

DEFAULT_PAGE_SIZE = 25


class ProductRepository(
    Creatable[Product, ProductCreate],
    Updatable[Product, ProductUpdate],
):
    """Reads, creation, and editing over the product collection.

    **Create and update, but not delete.** No write path removes a product, so a call to `delete`
    is a type error rather than a capability nobody happens to be using. Granting it belongs to
    whichever change introduces a deletion path.
    """

    def search(
        self,
        term: str = "",
        statuses: list[ProductStatus] | None = None,
        skip: int = 0,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> QueryResult[Product]:
        """Find products by text, status, or both.

        Not a coroutine — both halves of a `QueryResult` are lazy, so a caller wanting only rows
        pays nothing for the total it never reads.

        **An empty term applies no text constraint**, and absent `statuses` means unfiltered rather
        than empty. A screen that must not list everything before the user has typed declines to
        call this at all; keeping that guard here would make an unfiltered list inexpressible.
        """
        expressions: list[Any] = []

        if term.strip():
            # Escaped: the term is user input, and an unescaped `(` or `*` would either error or
            # silently change what the query means.
            pattern = {"$regex": re.escape(term.strip()), "$options": "i"}
            expressions.append({"$or": [{"name": pattern}, {"sku": pattern}]})

        if statuses:
            expressions.append(In(Product.status, statuses))

        return self.query(*expressions, sort="-updated_at", skip=skip, limit=limit)

    async def count_referencing_category(self, slug: str) -> int:
        """Count products carrying this category slug."""
        return await Product.find(Product.category == slug).count()

    async def rewrite_category_slug(self, old_slug: str, new_slug: str) -> int:
        """Repoint every product referencing `old_slug` at `new_slug`, returning how many moved.

        A bulk repoint decides nothing — *whether* to rename, in what order, and what to do on a
        collision is the service's business (see `CategoryService.rename_slug`).
        """
        result = await Product.find(Product.category == old_slug).update(
            {"$set": {"category": new_slug}},
        )

        return int(result.modified_count)


class CategoryRepository(WritableRepository[Category, CategoryCreate, CategoryUpdate]):
    """Reads, traversal, and persistence over the category tree.

    Writable because a registry screen creates and edits categories. Whether a delete is
    *permitted* — whether anything still references it — is the service's question, not this
    class's.
    """

    async def count_children(self, category: Category) -> int:
        """Count categories nested directly under this one."""
        return await Category.find(Category.parent.id == category.id).count()
```

**Rules for a concrete repository:**

- **Declare the narrowest set of write mixins that today's write paths actually need.** Widen it in
  the change that introduces the write, not speculatively. Record the narrowness in the docstring so
  the next reader knows it was a decision.
- **A method that decides nothing.** "Count what references this" belongs here; "refuse the delete
  when the count is non-zero" does not.
- **Reference-rewriting queries live on the repository, not the model.** A model that queries
  another document type is how an import graph closes into a cycle — two model modules each
  importing the other's document to rewrite references to their own key.
- **Return a `QueryResult` for anything paginated**, so the caller chooses whether to pay for the
  total.
- **Document the measured cost of a query** when it is non-obvious (which index serves it, whether
  a filter bounds the scan or is applied as a residual after fetching). That is the note nobody can
  reconstruct later without an `explain`.

## Write schemas

**What may be written is a declared schema**, not a set of loose arguments. A writing repository is
parameterized by Pydantic create and update models kept in the domain's `schemas.py`, and the
operations take them: `create(data)` and `update(document, data)`.

The schema's field set **is** the contract. If `CategoryUpdate` has no `slug` *field*, a caller
cannot express a re-key, and mypy says so at the call site — which is what turns "this key is
create-only" from a rule people follow into one the types carry.

```python
# app/domains/catalog/schemas.py
"""What may be written to the catalog: the create and update payloads its repositories take."""

from pydantic import BaseModel, Field

from app.core.models import Slug

from .models import Category


class CategoryCreate(BaseModel):
    """The fields a new category is built from."""

    slug: Slug = Field(
        description="The identity key products will store. Offered once, here, and never again.",
    )
    name: str = Field(description="The base display name; required.")
    parent: Category | None = Field(default=None, description="Parent, or None for a root.")


class CategoryUpdate(BaseModel):
    """The fields an existing category may change.

    **No `slug`.** Re-keying rewrites every stored reference in one pass and belongs to
    `CategoryService.rename_slug`; an update that changed the slug quietly would leave those
    references pointing at nothing.
    """

    name: str | None = None
    parent: Category | None = None
```

**Rules:**

- **Duplicate the field declarations the document already carries; do not derive them.** They are
  deliberately *different sets* — `CategoryUpdate` omits `slug` **because** `Category` has one. A
  schema generated from the document reintroduces exactly what these exist to exclude.
- **There is deliberately no `read_only_fields` list.** A name in a list is enforced by a runtime
  filter that silently drops what it matches, and a rename does not follow it. An omitted field is
  enforced by mypy, at the call site, before the code runs.
- **Every update field is `X | None = None`**, even where the document forbids null. Absence and
  clearing need the same uniform spelling; *whether a null may actually be stored* is the
  document's own business, enforced by the pre-write re-validation.
- **A list-valued field is replaced wholesale.** A partial write names fields, and a field holding a
  list is one field. That is what makes removal expressible at all — an element-wise merge could add
  and change but never delete.
- **Keep them Pydantic and keep them in the domain**, because they are also the request bodies a
  FastAPI intake or a workflow input will accept. The intake then validates against the same object
  the repository writes from, rather than a transcription of it that drifts.

## Services

A service owns an operation that **decides something**. Four shapes recur; if an operation is none
of them, it probably belongs on a repository or a model validator instead.

| Shape | The hard part | Example |
| --- | --- | --- |
| **Cross-aggregate** | The *ordering* between two writes that cannot be transactional | Attach A to B, then mark A processed — never the reverse |
| **Guarded write** | Refusing a write while other documents reference the target | Delete a category only if no product and no child names it |
| **Conformance** | An invariant needing I/O, so it cannot be a model validator | A value must match the input type of a definition in another collection |
| **Ordering + rollback** | One implementation of an invariant, with recovery | Rename a key: save first, roll back the in-memory value on collision, then repoint references |

**A service is named for a workflow, not for a document.** `RegistryService`, `CurationService`,
`ProductEditService` — not `ProductService` as a bag for everything touching products. The moment
one service becomes the destination for "anything that writes", it has stopped being named for a
workflow and the boundary is gone.

```python
# app/domains/catalog/registry.py
"""The registry workflow: creating, editing, and removing categories.

What lives here is **policy**. The repositories perform the writes; this module decides whether a
write is allowed: that a deletion is refused while anything still points at the record, that an
update leaves the key alone, that a re-parenting goes through the operation which rejects cycles.
None of those can live in a repository, because a repository decides nothing.
"""

from dataclasses import dataclass

from .models import Category
from .repository import CategoryRepository, ProductRepository
from .schemas import CategoryCreate, CategoryUpdate
from .services import CategoryService


@dataclass(frozen=True, slots=True)
class ReferenceCounts:
    """What still points at a record a user tried to delete."""

    products: int = 0
    child_categories: int = 0

    @property
    def total(self) -> int:
        """How many documents would be orphaned by the deletion."""
        return self.products + self.child_categories


class ReferencedRecordError(Exception):
    """Raised when a record cannot be deleted because something still references it.

    Carries the counts as data rather than only in the message, so a caller can render them
    without parsing a string.
    """

    counts: ReferenceCounts

    def __init__(self, slug: str, counts: ReferenceCounts) -> None:
        """Initialize the ReferencedRecordError instance."""
        self.counts = counts
        super().__init__(f"Cannot delete {slug!r}: {counts.total} document(s) reference it.")


class RegistryService:
    """The write path over the category registry."""

    categories: CategoryRepository
    products: ProductRepository
    category_service: CategoryService

    def __init__(
        self,
        categories: CategoryRepository | None = None,
        products: ProductRepository | None = None,
        category_service: CategoryService | None = None,
    ) -> None:
        """Initialize the RegistryService instance."""
        self.categories = categories or CategoryRepository()
        self.products = products or ProductRepository()
        self.category_service = category_service or CategoryService()

    async def update_category(self, category: Category, data: CategoryUpdate) -> Category:
        """Update a category's editable fields, and its parent when the caller names one.

        **An unset parent leaves the category where it is**; only an explicitly passed one moves
        it, and passing `None` explicitly detaches it to a root.

        Re-parenting delegates to `CategoryService.set_parent`, which rejects a category as its own
        parent and any parent already beneath it. Delegating rather than re-checking keeps one
        implementation of the acyclicity invariant; a second would diverge the first time either
        changed. It runs **before** the write, so a rejected cycle stores nothing.

        Raises:
            ValueError: If the parent assignment would form a cycle.

        """
        if "parent" in data.model_fields_set:
            await self.category_service.set_parent(category, data.parent)

        return await self.categories.update(category, data)

    async def delete_category(self, category: Category) -> None:
        """Delete a category, refusing while anything still references it.

        Refusing rather than cascading (which silently discards work) or nulling (which produces a
        document state no write path creates). The check is read-then-write and not atomic;
        accepted where the failure mode is a visible dangling reference rather than a silent one.

        Raises:
            ReferencedRecordError: If anything still references the category.

        """
        counts = ReferenceCounts(
            products=await self.products.count_referencing_category(category.slug),
            child_categories=await self.categories.count_children(category),
        )

        if counts.total:
            raise ReferencedRecordError(category.slug, counts)

        await self.categories.delete(category)
```

### Ordering without transactions

When two documents must change together and the deployment has no multi-document transactions
(a standalone MongoDB, or the in-memory test backend), the substitute is a **fixed write order plus
idempotent writes**, chosen so an interruption fails toward the *visible* state rather than the
silent one. Spell the reasoning out in the docstring — it is invisible from the code:

```python
    async def attach(self, snapshot: Snapshot, product: Product) -> AttachResult:
        """Attach a snapshot to a product and mark it processed.

        **The write order is normative, not incidental.** The reference append is issued first and
        the status update second, because of what each interruption leaves behind:

        - Interrupted after the append: the product references the snapshot, which is still
          `pending`. It stays in the queue and `reconcile` can repair it. Visible.
        - Interrupted after a status-first write: the snapshot is `processed` with nothing
          referencing it — indistinguishable from a dismissal, silently gone. Invisible, and
          unrecoverable without an audit.

        Both writes are idempotent (`$addToSet`, and a `$set` of a fixed value), so retrying an
        interrupted attach converges rather than duplicating or failing.
        """
        reference_added = await self.products.add_source_ref(product.id, snapshot.id)
        status_advanced = await self.snapshots.mark_processed(snapshot.id)

        return AttachResult(reference_added=reference_added, status_advanced=status_advanced)
```

Pair such an operation with an explicit, deliberately-invoked **repair** command (`reconcile`)
rather than a repair that happens as a side effect of another write.

### What a service must not do

- **Never call the ODM's own writes.** A service reaching for `document.insert()` or
  `document.delete()` bypasses the declared schema and the opt-in ladder. Go through the repository
  — and if the repository does not declare that operation, that absence is the answer, not an
  obstacle to route around.
- **Never inherit from a repository.** See below.
- **No presentation.** No formatting, no framework objects, no request/session state. The service is
  called identically from an HTTP handler, a worker task, a CLI command, and a dashboard page.
- **No I/O-free validation.** If a rule needs no other document, it is a Pydantic validator on the
  model, where it runs on every path including the repository's pre-write re-validation.

## Dependency injection

**Services compose repositories; they never inherit them.** Inheritance cannot express two
collaborators — and most operations have two — and it would publish the whole data-access surface on
the service, letting a caller reach past the very invariants the service exists to hold.

The pattern is **constructor injection with a defaulting fallback**:

```python
class CategoryService:
    """Operations spanning the category tree and the products referencing it."""

    categories: CategoryRepository        # ← the class header is the dependency list
    products: ProductRepository

    def __init__(
        self,
        categories: CategoryRepository | None = None,
        products: ProductRepository | None = None,
    ) -> None:
        """Initialize the CategoryService instance."""
        self.categories = categories or CategoryRepository()
        self.products = products or ProductRepository()
```

Why this shape specifically:

- **Every collaborator is declared at class level**, annotation-only, per the house rule on instance
  variables. The class header alone answers "what does this service touch?" without reading
  `__init__` or grepping for `self.`.
- **The default keeps call sites trivial.** `CategoryService()` at every entry point — no container,
  no wiring module, no framework-owned lifecycle. Repositories are **stateless** (the Mongo client
  and Beanie's model registry are process-global), so constructing one is free and there is nothing
  to share. This is what makes the default honest rather than a hidden singleton.
- **The seam exists for substitution**, and that is its whole job: a test passing a fake or an
  instrumented repository, and a service composing another service.
- **Services may inject services.** `RegistryService` takes a `CategoryService` so that re-parenting
  has exactly one implementation of the acyclicity check. A second copy diverges the first time
  either changes.
- **Inject the repository, never the document class or the ODM.** The repository *is* the seam; a
  service holding a `Document` subclass has reached past it.
- **No DI framework, and no `Depends()` in the domain.** The domain is called from several entry
  points (HTTP, worker, CLI, dashboard); a container owned by one framework serves exactly one of
  them and makes the domain unusable from the rest. Where a framework wants its own injection, wire
  it in the *entry point*: a FastAPI `Depends(CategoryService)` at the route, resolving to the same
  default-constructed object.

```python
# Entry point — the framework's injection stops at the boundary:
@router.delete("/categories/{slug}")
async def delete_category(
    slug: str,
    service: Annotated[RegistryService, Depends(RegistryService)],
) -> None:
    """Delete a category."""
    ...
```

## Testing both layers

- **Repositories are tested against a real in-memory MongoDB** through the shared `mongo` fixture,
  not against mocks — the point of a repository test is that the query actually matches.
- **Services are tested through their public operations** with real repositories, since the
  repositories are cheap and the interesting assertions are about stored state. Inject a fake only
  to force a path you cannot otherwise reach — an interruption between two writes, a driver error.
- **Assert on stored state, not on the raise.** A test that only asserts `pytest.raises(...)` passes
  against the version that wrote first and validated afterwards. Re-read the document and check.
- **Verify link-resolving and reference-matching reads against a live MongoDB**, and record that you
  did. Several such reads return *empty without raising* on the mongomock backend, so a wrong query
  passes its tests against nothing. See `references/mongo-beanie.md`.

```python
async def test_update_rejects_a_duplicate_choice_before_writing(mongo) -> None:
    """A partial $set validates after writing, so the repository must validate first."""
    definition = await AttributeDefinitionRepository().create(...)

    with pytest.raises(ValidationError):
        await AttributeDefinitionRepository().update(definition, AttributeDefinitionUpdate(...))

    # The assertion that matters: the raise alone passes against the broken version.
    stored = await AttributeDefinitionRepository().read(definition.id)
    assert [choice.slug for choice in stored.choices] == ["original"]
```

## Anti-patterns

| Anti-pattern | Why it fails | Instead |
| --- | --- | --- |
| One `BaseRepository` with `create`/`update`/`delete` on it | Every repository silently gains every write; nothing marks where writing is intended | Opt in one operation at a time via the mixins |
| `document: ClassVar = Category` beside `Repository[Category]` | Two declarations free to disagree, and nothing catches it | Resolve it in `__init_subclass__` |
| `def update(self, doc, **fields)` | The writable field set is undeclared, so a create-only key is one keyword away | A declared `UpdateSchema` |
| `read_only_fields = ["slug"]` | A runtime filter that silently drops what it matches, and renames do not follow it | Omit the field from the schema; mypy enforces it |
| `if data.name is not None: doc.name = data.name` | Cannot distinguish "leave alone" from "clear", and repeats the decision per field | `model_fields_set` in one place |
| Service calls `await document.insert()` | Bypasses the schema and the opt-in ladder | Go through the repository, or widen it deliberately |
| `class CategoryService(CategoryRepository)` | Cannot express two collaborators; publishes the data-access surface | Compose; inject |
| Repository refuses a delete when referenced | Policy in the mechanism layer; the next caller adds a different rule next to it | Count in the repository, refuse in the service |
| Model queries another document type | Closes the import graph into a cycle | Put the cross-document query on the repository |
| A global `registry_service = RegistryService()` singleton | Un-substitutable in tests, and hides the dependency list | Default-construct at the call site |
| Business logic in a route/task/page | Untestable without the framework, and duplicated across entry points | Thin entry point calling one service operation |
