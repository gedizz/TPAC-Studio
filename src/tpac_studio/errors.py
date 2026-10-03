"""Stable error codes shared by the library, CLI, GUI and MCP adapters."""

from typing import Any


class StudioError(Exception):
    """An actionable failure, with a machine-readable code and optional details."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable error without a traceback or hidden state."""
        return {"code": self.code, "message": str(self), "details": self.details}


def require(condition: bool, message: str, code: str = "INVALID_DATA", **details: Any) -> None:
    """Validate external input even when Python runs with optimization enabled."""
    if not condition:
        raise StudioError(code, message, **details)
