from __future__ import annotations

from typing import Any


class PackagerError(Exception):
    """Raised when contract validation fails."""

    def __init__(self, error_code: str, message: str, details: dict[str, Any]) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details

    def payload(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }
