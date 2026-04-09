from tkts.api import create_ticket, get_ticket, get_store, list_tickets

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tkts")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__", "create_ticket", "get_ticket", "get_store", "list_tickets"]
