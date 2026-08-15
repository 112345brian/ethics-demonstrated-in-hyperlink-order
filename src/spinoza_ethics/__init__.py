"""Static-site generator for the Spinoza Ethics scholarly workbench."""

from .builder import build
from .config import BuildConfig

__all__ = ["BuildConfig", "build"]
__version__ = "1.0.0"
