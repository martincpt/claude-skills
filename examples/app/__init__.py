"""My Project (application) package."""

from .config import pyproject

__title__ = pyproject["project"]["description"]
__version__ = pyproject["project"]["version"]