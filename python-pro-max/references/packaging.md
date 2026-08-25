# Python Packaging and Project Setup

## Project Structure

Conventions:

- **Flat layout — no `src/` container.** The package sits at the repository root.
- **Repository name is slugified** (`my-project`); the **main module is the snake_case** form (`my_project`).
- **For an API or runnable application, use the app layout**: the main package is simply **`app`** (rather than the snake_cased repo name).
- **`uv` manages the project**; commit `uv.lock` and pin the interpreter with `.python-version`.

### Library / package (flat layout)

```
my-project/                 # repository: slugified name
├── pyproject.toml
├── README.md
├── .gitignore
├── .python-version         # pinned interpreter (uv python pin)
├── uv.lock                 # uv lockfile (committed)
├── my_project/             # main module: snake_case of the repo name
│   ├── __init__.py
│   ├── py.typed            # PEP 561 type marker
│   ├── core.py
│   └── utils.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_core.py
```

### API / runnable application (app layout)

```
my-project/                 # repository: slugified name
├── pyproject.toml
├── README.md
├── .python-version
├── uv.lock
├── app/                    # main package for a runnable app / API
│   ├── __init__.py         # package metadata (__title__/__version__ from pyproject)
│   ├── config.py           # Pydantic Settings + pyproject access
│   ├── cli.py              # Fire launcher (entry point: app.cli:run)
│   ├── main.py             # lifecycle: startup/shutdown, serve
│   ├── models.py           # Beanie document models
│   └── mongo/              # MongoDB/Beanie integration
│       ├── __init__.py     # re-exports MongoWithBeanie
│       ├── connector.py
│       └── fixtures.py     # the `mongo` test fixture
└── tests/
    ├── conftest.py         # pytest_plugins = ["app.mongo.fixtures"]
    └── test_app.py
```

## pyproject.toml Configuration

Built from the team's standard template — `uv`, flat **app** layout, `select = ["ALL"]`,
`[dependency-groups]`, and `[tool.uv] package = false` (an application is deployed, not
distributed as a wheel).

> New projects target **Python 3.13**; the skill's code patterns are compatible down to **3.11**.

```toml
[project]
name = "my-project"
version = "0.1.0"
description = "A runnable Python application"
authors = [{ name = "Your Name", email = "you@example.com" }]
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "fire>=0.7.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.8.0",
]

[project.optional-dependencies]
# Opt-in features: `uv sync --extra beanie`
beanie = [
    "beanie>=2.0.0",
]

[dependency-groups]
dev = [
    "pre-commit>=4.2.0",
    "coverage>=7.7.0",
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-mock>=3.14.0",
]
docs = [
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.6.0",
    "mkdocstrings-python>=1.16.0",
]

# Runnable entry point: `uv run app` -> app.cli.run()
[project.scripts]
app = "app.cli:run"

[tool.uv]
package = true

[tool.black]
line-length = 88

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "ANN002",  # Missing type annotation for *{name}
    "ANN003",  # Missing type annotation for **{name}
    "ANN401",  # Dynamically typed expressions (typing.Any) are disallowed in {name}
    "D104",    # Missing docstring in public package
    "D401",    # First line of docstring should be in imperative mood
    "D402",    # First line should not be the function's signature
    "D404",    # First word of the docstring should not be `This`
    "D417",    # Missing argument descriptions in Docstring (If we use type annotations, we don't need to describe the arguments)
    "DTZ005",  # The use of `datetime.datetime.now()` without tzinfo must be followed by `.replace(tzinfo=)` or `.astimezone()`
    "DTZ007",  # The use of `datetime.datetime.strptime()` without %z must be followed by `.replace(tzinfo=)` or `.astimezone()`
    "FBT001",  # Boolean positional argument in function definition
    "FBT002",  # Boolean default value in function definition
    "G004",    # Logging statement uses f-string
    "PLR0913", # Too many arguments to function call (N > 5)
    "PLW0603", # Using the global statement to update `X` is discouraged
    "PTH123",  # `open()` should be replaced by `Path.open()`
    "S101",    # Use of assert detected (used for cheap type narrowing to help Pylance)
    "SLF001",  # Private member accessed
    "TD002",   # Missing author in TODO; try: `# TODO(<author_name>): ...`
    "TD003",   # Missing issue link on the line following this TODO
    "TRY400",  # Use `logging.exception` instead of `logging.error`
    "PLE0604", # Invalid object in `__all__`, must contain only strings (So we can use __all__ = [MyClass.__name__])
    # FastAPI dependencies:
    "B008",    # Do not perform function call {name} in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
    # Better reading CRUD resources:
    "RUF012",  # Mutable class attributes should be annotated with typing.ClassVar    
    # New lint rules since python 3.13
    "PLC0415", # `import` should be at the top-level of a file
    "FAST002", # FastAPI dependency without `Annotated`
    "UP046",   # Generic class `PaginatedResults` uses `Generic` subclass instead of type parameters
    "UP047",   # Generic function `inject_dependencies` should use type parameters
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ARG001", "PLR2004"]  # Fixtures, magic values

[tool.ruff.lint.mccabe]
max-complexity = 20

[tool.ruff.lint.flake8-pytest-style]
fixture-parentheses = true
mark-parentheses = true

[tool.mypy]
python_version = "3.13"
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-s -v --durations=0 --disable-warnings --tb short"
cache_dir = ".cache/pytest_cache"
asyncio_mode = "auto"

[tool.coverage.run]
branch = true
source = ["app"]. # or ["my_project"]
command_line = "-m pytest"
omit = ["tests/"]

[tool.coverage.report]
show_missing = true
exclude_lines = [
    'if *TYPE_CHECKING*:$',
    'if t.TYPE_CHECKING:$',
    '\.\.\.$',
    'continue$',
    'break$',
    'pass$',
    'message = *',
    'raise *',
    'raise$',
]

[tool.coverage.xml]
output = "coverage.xml"
```

### Library variant

For a distributable **library** (flat layout, module `my_project`) instead of an app, build a wheel:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
my-project = "my_project.cli:main"
```

Then set `[tool.uv] package = true` (`package = true` 
builds `my_project`), and point coverage at the module: `source = ["my_project"]`.

## UV Project Management

`uv` replaces poetry/pip-tools: dependency resolution, locking, virtualenvs, and Python
version management in one tool.

```bash
# Scaffold
uv init my-project              # New library (flat layout)
uv init --app my-project        # New runnable application (app layout)

# Dependencies
uv add pydantic                 # Add a runtime dependency to [project.dependencies]
uv add --dev mypy ruff          # Add to the dev group ([dependency-groups].dev)
uv add --group test pytest      # Add to a named group
uv add --optional postgres asyncpg  # Add to an optional-dependencies extra
uv remove requests              # Remove a dependency

# Environment & locking
uv sync                         # Create/sync .venv from uv.lock (default groups)
uv sync --all-extras --all-groups   # Everything
uv sync --no-dev                # Production install (no dev group)
uv lock                         # Refresh uv.lock
uv lock --upgrade               # Upgrade pins within constraints

# Running
uv run pytest                   # Run inside the project env (no activation needed)
uv run app                      # Invoke the `app` script ([project.scripts])

# Build / publish (libraries only)
uv build                        # sdist + wheel into dist/
uv publish                      # Publish to PyPI (UV_PUBLISH_TOKEN)

# Python versions (replaces pyenv)
uv python install 3.13
uv python pin 3.13              # Writes .python-version
```

## Virtual Environments

```bash
# uv creates and manages .venv automatically on `uv sync` / `uv run`.
uv venv                         # Explicitly create .venv (honours .python-version)
source .venv/bin/activate       # Optional — `uv run <cmd>` needs no activation
.venv\Scripts\activate          # Windows

# Pin / install interpreters with uv (no separate pyenv needed)
uv python install 3.13
uv python pin 3.13              # Writes .python-version
```

## Configuration (Pydantic Settings)

Configuration lives in a `config.py` directly under the main package, using
**pydantic-settings**. A `Settings(BaseSettings)` class declares typed, defaulted fields
that are overridden by environment variables (and a `.env` file); `get_settings()` /
`get_pyproject()` are `lru_cache`d factories, and module-level `settings` / `pyproject`
singletons are imported wherever needed. This keeps config typed, validated, and in one
place — no scattered `os.getenv` calls or config dicts.

```python
# app/config.py  (or my_project/config.py)
"""Configs for the My Project package."""

import sys
import tomllib
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings class."""

    # ---- Pydantic config ----
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- App settings (overridable via env / .env) ----
    debug: bool = False
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8000
    log_level: str = "info"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "my-project"
    is_testing: bool = "pytest" in sys.modules
    document_model_modules: list[str] = ["app.models"]


@lru_cache
def get_settings() -> Settings:
    """Settings factory."""
    return Settings()


@lru_cache
def get_pyproject() -> dict[str, Any]:
    """Read and cache the pyproject.toml file."""
    with open("pyproject.toml", "rb") as f:
        return tomllib.load(f)


# ---- Globals ----
settings = get_settings()
pyproject = get_pyproject()
```

## Package __init__.py

Pull the package title and version from `pyproject.toml` (via `config.pyproject`) so they
have a single source of truth instead of a hardcoded `__version__`.

```python
# app/__init__.py  (or my_project/__init__.py)
"""My Project (application) package."""

from .config import pyproject

__title__ = pyproject["project"]["description"]
__version__ = pyproject["project"]["version"]
```

When a package re-exports a public API, build `__all__` from each object's `__name__`
rather than re-typing the string. A rename or typo then fails fast (the attribute won't
exist) instead of silently dropping the export. Plain values have no `__name__`, so list
those as strings.

```python
# my_project/__init__.py  (library re-exporting its public API)
"""My Project package."""

from .core import CoreClass, main_function

DEFAULT_TIMEOUT = 30  # a plain value has no __name__

__all__ = [
    CoreClass.__name__,      # -> "CoreClass"
    main_function.__name__,  # -> "main_function"
    "DEFAULT_TIMEOUT",       # string for objects without __name__
]
```

> This relies on ruff ignoring `PLE0604` ("Invalid object in `__all__`, must contain only
> strings"), which is in the standard ignore list above.

## CLI Entry Points

Use the **Fire** package for CLIs. For anything beyond a single command, expose a
**class-based launcher**: each public method becomes a subcommand and its parameters map to
flags. Nested classes give command groups. Fire infers the interface from the class, so
there's no parser boilerplate to maintain.

```python
# app/cli.py — class-based Fire launcher; each method is a subcommand.
# Wired via [project.scripts] app = "app.cli:run"  ->  `uv run app <command> [--flags]`
import fire


class Database:
    """Database management commands (a nested command group)."""

    def migrate(self, revision: str = "head") -> None:
        """Apply migrations up to a revision."""
        ...

    def seed(self, *, force: bool = False) -> None:
        """Populate the database with seed data."""
        ...


class CLI:
    """my-project command-line interface."""

    db: Database  # exposes the `db` command group: `app db migrate`

    def __init__(self) -> None:
        """Initialize the CLI instance."""
        self.db = Database()

    def serve(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the application server."""
        ...

    def shell(self) -> None:
        """Open an interactive shell with the app context loaded."""
        ...


def run() -> None:
    """Entry point: dispatch subcommands through Fire."""
    fire.Fire(CLI)


if __name__ == "__main__":
    run()
```

```bash
# Subcommands and flags are derived from the class:
uv run app serve --port 9000
uv run app db migrate --revision head
uv run app db seed --force
```

## Type Stub Files (py.typed)

```python
# my_project/py.typed
# Empty file (PEP 561) — marks the package as typed so consumers get your hints.

# my_project/__init__.pyi (optional stub file)
__version__: str

def main_function(arg: str) -> None: ...

class CoreClass:
    def __init__(self, name: str) -> None: ...
    def process(self) -> str: ...
```

## Requirements Files

`uv` resolves and locks via `pyproject.toml` + `uv.lock` (committed). A `requirements.txt`
is only needed for environments that can't run `uv` — export it:

```bash
uv export --no-emit-project --no-hashes -o requirements.txt
uv export --only-group test --no-emit-project -o requirements-test.txt
```

## Building and Distribution

```bash
# Libraries (package = true):
uv build                        # Build sdist + wheel into dist/
uv publish                      # Publish to PyPI (set UV_PUBLISH_TOKEN)

# Applications (package = false) are deployed, not published:
# ship the repo + uv.lock and provision the target with `uv sync --no-dev`.
```

## Version Management

```python
# Preferred: read the installed distribution's version (single source of truth).
from importlib.metadata import version

__version__ = version("my-project")

# Or read pyproject.toml directly (tomllib is stdlib on Python 3.11+).
import tomllib
from pathlib import Path

def get_version() -> str:
    """Read the project version from pyproject.toml."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]
```

## Dependency Management Best Practices

```toml
# Floors with lower bounds; cap a version only when a known break exists.
dependencies = ["pydantic>=2.10", "httpx>=0.27,<1.0"]
```

- **Applications**: commit `uv.lock` for reproducible installs (`uv sync` honours it); deploy with `uv sync --no-dev`.
- **Libraries**: keep ranges in `[project.dependencies]` and do **not** commit a lock file.
- Upgrade deliberately with `uv lock --upgrade`, then `uv sync` and run the test suite.

## CI/CD Integration

CI runs **pre-commit** across the Python matrix — the hooks already cover lint (ruff),
format (black), types (mypy), and tests (the local pytest hook), so the workflow stays a
single source of truth with the local checks. Install with `uv`, cache the hook
environments, and run them with `--show-diff-on-failure`.

```yaml
# .github/workflows/pre-commit.yml
name: pre-commit

on:
  pull_request:
  push:
    branches: [main]

jobs:
  pre-commit:
    runs-on: ubuntu-latest

    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.13"]   # track requires-python (add "3.12" etc. to widen)

    steps:
      - uses: actions/checkout@v6

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install the project
        run: uv sync --locked --all-extras --dev

      - name: Cache pre-commit hooks
        uses: actions/cache@v4
        with:
          path: ~/.cache/pre-commit
          key: pre-commit-${{ matrix.python-version }}-${{ hashFiles('.pre-commit-config.yaml') }}

      - name: Run pre-commit
        run: uv run pre-commit run --all-files --show-diff-on-failure
```

## Pre-commit Hooks

Built from the team's standard config — the pre-commit-hooks hygiene suite, then black,
ruff (`--fix`), mypy (with stub install), and a local pytest gate. `black` and `ruff` both
run, so the differing line lengths are intentional: black formats at 88, ruff only flags
lines over 120.

```yaml
# .pre-commit-config.yaml
default_language_version:
  python: python3
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-docstring-first
      - id: check-yaml
      - id: debug-statements
      - id: check-ast
  - repo: https://github.com/psf/black
    rev: 26.3.1
    hooks:
      - id: black
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: "v0.15.12"
    hooks:
      - id: ruff
        args: ["--fix"]
        fail_fast: true
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: "v2.1.0"
    hooks:
      - id: mypy
        args: ["--install-types", "--non-interactive"]
        additional_dependencies:
          - pydantic
          - types-setuptools
          # add the stub packages your code imports (e.g. types-requests)
        fail_fast: true
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        stages: [pre-commit]
        language: system
        entry: pytest -v --showlocals --disable-warnings
        types: [python]
        pass_filenames: false
```

```bash
# Install and run (pre-commit lives in the dev group)
uv run pre-commit install
uv run pre-commit run --all-files
```
