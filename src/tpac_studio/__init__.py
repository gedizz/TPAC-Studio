"""TPAC Studio public Python interface. Importing this package opens no GUI."""

__version__ = "1.0.0"

from .errors import StudioError

__all__ = ["StudioError", "__version__"]
