# Project Architecture: `core/` and `domains/`

The layout in `references/packaging.md` is the right shape for a single-purpose application: a flat
`app/` package with a handful of modules beside `config.py`. Once the application has **more than
one business area**, or more than one entry point into the same logic, it needs an internal
boundary — otherwise every module can import every other, and the import graph decides the
architecture by accident.

The structure is a **modular monolith** with strict layering:

- **`core/`** — cross-cutting infrastructure only. No business logic.
- **`domains/<area>/`** — business logic, one subpackage per area, independent of each other.
- **`api/`, `workflows/`, `cli/`** — thin entry points. They import from `domains/` and hold no
  business logic of their own.

> The classes that live inside a domain — repositories, schemas, services — are covered in
> `references/repositories-and-services.md`.

## The tree

```
app/
├── __init__.py              # package metadata (__title__/__version__ from pyproject)
├── config.py                # Settings(BaseSettings) + the `settings` singleton
│
├── core/                    # cross-cutting infrastructure — NO domain logic
│   ├── __init__.py
│   ├── mongo/               # connector, generic repository, link resolution, fixtures
│   │   ├── __init__.py      # re-exports the public surface
│   │   ├── connector.py
│   │   ├── repository.py
│   │   ├── links.py
│   │   ├── mock.py
│   │   └── fixtures.py
│   ├── models/              # shared model building blocks (mixins, custom types)
│   │   ├── __init__.py
│   │   ├── mixins.py        # CreatedUpdatedAt, ...
│   │   └── slugs.py         # a validating Slug type + an explicit slugifier
│   ├── email/               # the mail client
│   └── error_handler/       # error capture, notification, persisted error records
│
├── domains/                 # business logic — areas independent of one another
│   ├── __init__.py
│   ├── catalog/
│   │   ├── __init__.py
│   │   ├── models.py        # Beanie documents + embedded models
│   │   ├── schemas.py       # create/update payloads (also the API request bodies)
│   │   ├── repository.py    # concrete repositories
│   │   ├── services.py      # cross-aggregate operations
│   │   └── registry.py      # a second, differently-shaped workflow service
│   └── billing/
│       ├── __init__.py
│       ├── base.py          # the generic interface
│       └── acme/            # one concrete provider integration
│           ├── __init__.py
│           └── client.py
│
├── api/                     # FastAPI — thin: intake, validation, dispatch
│   ├── __init__.py
│   ├── app.py
│   └── routers/
├── workflows/               # task/workflow definitions — thin
│   ├── __init__.py
│   └── worker.py
└── cli/                     # Fire launcher — thin
    ├── __init__.py
    ├── __main__.py
    ├── launcher.py
    └── groups/
```

## `core/` — infrastructure only

**The test for `core/`: could this module exist unchanged in a completely different product?** If
the answer is no, it belongs in a domain.

- **One subpackage per concern**, never a `utils/` or `helpers/` grab bag. `mongo/`, `email/`,
  `error_handler/`, `models/` — each named for the thing it integrates or provides.
- **A subpackage's `__init__.py` re-exports its public surface**, so importers depend on the package
  rather than on its internal module split. Build `__all__` from `obj.__name__`:

  ```python
  # app/core/mongo/__init__.py
  """MongoDB with Beanie integration."""

  from .connector import MongoWithBeanie
  from .links import LinkResolver
  from .repository import (
      Creatable,
      Deletable,
      QueryResult,
      Repository,
      Updatable,
      WritableRepository,
  )

  __all__ = [
      Creatable.__name__,
      Deletable.__name__,
      LinkResolver.__name__,
      MongoWithBeanie.__name__,
      QueryResult.__name__,
      Repository.__name__,
      Updatable.__name__,
      WritableRepository.__name__,
  ]
  ```

- **`core/` never imports from `domains/`.** This is the one-directional rule that makes the split
  mean anything. A generic repository parameterized by a document type is fine; a generic repository
  that mentions `Product` is a domain module in the wrong directory.
- **`core/models/` holds building blocks, not entities.** Timestamp mixins, a validating `Slug`
  type, a base document class — things every domain composes. A `User` document is not one of them.
- **Test fixtures ship beside the thing they set up** (`core/mongo/fixtures.py`), registered from
  `tests/conftest.py` via `pytest_plugins = ["app.core.mongo.fixtures"]`. That keeps the fixture and
  the connector it fakes in one place.

## `domains/` — one subpackage per business area

- **Name a domain after the business area, 1:1 with how the product documentation names it.** If the
  functional spec has a "data pipeline" chapter, the package is `data_pipeline`. Resisting the urge
  to invent a technical name is what keeps the code searchable from the requirements.
- **Domains are independent.** A domain may import `core/` and its own modules freely. Cross-domain
  imports are a design decision, not a convenience: prefer moving the shared thing into `core/`, or
  putting the operation that spans both in the entry point that already knows about both.
- **A domain owns its documents.** A document type lives in exactly one domain, and no other domain
  writes it.

### Generic interface + concrete integration

Where a domain talks to interchangeable external providers, use `base.py` for the generic interface
and a subpackage per provider:

```
domains/billing/
├── base.py            # the abstract interface + the source-agnostic flow
├── schemas.py         # shared payloads
├── acme/              # one provider
│   └── client.py
└── other_vendor/
    └── client.py
```

The base class owns the flow that is the same for every provider; the subclass implements only what
differs. Worth stating in the base module's docstring which is which — otherwise the next provider
re-implements the flow.

```python
# app/domains/billing/base.py
"""The generic billing flow.

`BaseBilling` owns the provider-agnostic sequence — validate, submit, persist the result,
summarize — while each provider implements `submit` for one API. Per-item failures are isolated so
one rejection never aborts the batch.
"""

from abc import ABC, abstractmethod
from typing import ClassVar


class BaseBilling(ABC):
    """Provider-agnostic billing orchestration."""

    provider: ClassVar[BillingProvider]

    async def issue(self, order: Order) -> Invoice:
        """Validate an order, submit it to the provider, and persist the invoice."""
        ...  # the flow every provider shares

    @abstractmethod
    async def submit(self, payload: InvoicePayload) -> ProviderResponse:
        """Send one invoice to the provider's API."""
```

### The standard module inventory

Inside a domain (or a subpackage of one), these names mean the same thing everywhere:

| Module | Holds | Never holds |
| --- | --- | --- |
| `models.py` | Beanie documents, embedded models, enums, model validators | Anything doing I/O; a query against another document type |
| `schemas.py` | Create/update payloads, transfer models, API request bodies | Documents |
| `repository.py` | Concrete repositories — queries and unconditional writes | Guards, orderings, rollbacks |
| `services.py` | Cross-aggregate operations, named for the workflow | Presentation, framework objects |
| `base.py` | The generic interface, when the area has interchangeable providers | Provider specifics |

**Split a module into a subpackage when it earns it, and keep the same names inside.**
`domains/catalog/models.py` becomes `domains/catalog/products/{models,schemas,repository}.py` when
the area grows a second aggregate — not `domains/catalog/product_models.py`.

**A file per workflow, not one `services.py` holding everything.** When a second service has a
different shape from the first, give it its own module and say in the docstring what separates them.
Otherwise the first service quietly becomes the destination for anything that writes.

**Where does an operation spanning two aggregates live?** At the **domain root**, not inside either
aggregate's subpackage — filing it with one asserts an ownership the operation explicitly denies:

```
domains/data_pipeline/
├── curation.py          # ← attach/dismiss/reconcile: touches BOTH sub-aggregates
├── canonical/
│   ├── models.py
│   └── repository.py
└── snapshots/
    ├── models.py
    └── repository.py
```

### A model does no I/O

An invariant that can be checked from the document's own fields is a Pydantic validator, and runs
everywhere — including the repository's pre-write re-validation. An invariant that needs to *read
another document* cannot be a validator and belongs to the write path that already holds the other
record. Say so explicitly in both places:

```python
# In the model — the rule that cannot live here, and where it went:
class AttributeValue(BaseModel):
    """A typed attribute value on a product.

    Conformance to the definition's `input_type` is **not** checked here: it requires reading
    another document, and this layer does no I/O. It is enforced by `ProductEditService`, the
    write path that already holds the registry.
    """
```

## Thin entry points

`api/`, `workflows/`, `cli/`, and any dashboard package are **thin**: they translate a request into a
call on a domain service and translate the result back. They hold no business logic, so:

- **They have no test directory.** What they invoke is tested where it lives, and the absent
  directory documents the decision. (`references/testing.md`)
- **They may live inside a domain when they serve only that domain** — an internal dashboard sharing
  no transport or schema with the HTTP intake sits in `domains/<area>/dashboard/`, because
  everything it shows belongs to one domain. It is still an entry point, and still untested.
- **A page/route/task never writes a document directly.** Every write goes through one service
  operation, which is what keeps the ordering and guard rules in one place.
- **Schemas are shared, not duplicated.** FastAPI and most Python workflow engines are Pydantic-
  based, so `domains/<x>/schemas.py` models are imported directly by both. Do not add a separate
  DTO layer that transcribes them.

```python
# app/api/routers/categories.py — the whole route: dispatch and translate.
@router.delete("/categories/{slug}", status_code=204)
async def delete_category(
    slug: str,
    service: Annotated[RegistryService, Depends(RegistryService)],
) -> None:
    """Delete a category, refusing while anything still references it."""
    category = await CategoryRepository().by_slug(slug)

    if category is None:
        raise HTTPException(status_code=404)

    try:
        await service.delete_category(category)
    except ReferencedRecordError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
```

## Import direction

One rule, in one direction:

```
entry points  →  domains  →  core
     (api, workflows, cli)        ↘  config
```

- `core/` imports `config` and third-party packages. Nothing else in the app.
- `domains/<a>/` imports `core/`, `config`, and its own modules. Not `domains/<b>/`, not entry points.
- Entry points import anything below them.
- **Within a package, use relative imports** (`from .repository import CategoryRepository`);
  **absolute for anything outside it** (`from app.core.mongo import Repository`). Never walk upward
  with `..` — ruff's TID252 forbids it, and an upward import is usually a sign the module is in the
  wrong package.

### Enforce it with an architecture test

Layering that is only written down drifts. A single guard test in `tests/test_architecture.py` costs
little and fails at the moment the rule is broken:

```python
"""Codebase-wide structural guards.

Subject: the layering rules in the project architecture reference.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "app" / "core"


def imported_modules(path: Path) -> set[str]:
    """Return every absolute module name imported by a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)

    return names


def test_core_is_present() -> None:
    """The guarded tree must exist, or every guard below passes on nothing."""
    assert CORE.is_dir(), f"core package not found at {CORE}"


def test_core_does_not_import_domains() -> None:
    """`core/` is cross-cutting infrastructure: it must not know about any business area."""
    offenders = {
        path.relative_to(ROOT).as_posix(): sorted(
            name for name in imported_modules(path) if name.startswith("app.domains")
        )
        for path in CORE.rglob("*.py")
    }
    offenders = {path: names for path, names in offenders.items() if names}

    assert not offenders, f"core imports domain modules: {offenders}"
```

Two other guards worth the same treatment once they apply:

- **No cross-domain imports** — the same walk, asserting a module under `domains/<a>/` imports no
  `app.domains.<b>`.
- **Reserved module names.** Streamlit (and anything else that puts the entry script's directory at
  the front of `sys.path`) turns a module beside the entry point into a top-level import for the
  whole process — a `dashboard/queue.py` *becomes* `import queue` for `concurrent.futures` too.
  Assert no module beside such an entry point shadows a standard-library name.

## Naming

- **Packages and modules**: `snake_case`, singular for a concept (`config.py`, `repository.py`),
  plural only when the module genuinely holds a collection of peers (`models.py`, `schemas.py`,
  `services.py`).
- **A domain is named for the business area**, matching the product documentation.
- **A service is named for the workflow it performs** (`RegistryService`, `CurationService`), never
  for a document (`ProductService`), which is how one class becomes the home for everything.
- **A repository is named for the document it serves** (`CategoryRepository`) — that one *is* a
  document-shaped class.
- **No `utils.py` at the package root.** A helper belongs with the concern it serves, grouped under a
  named class (see the house rule on grouping functions under classes).
