"""Exceptions for the Firewalla MSP API client."""
from __future__ import annotations


class FirewallaAPIError(Exception):
    """Base exception for all Firewalla MSP API errors."""


class FirewallaAuthError(FirewallaAPIError):
    """Raised when the token is invalid, expired, or forbidden."""


class FirewallaConnectionError(FirewallaAPIError):
    """Raised when the MSP host cannot be reached."""


class FirewallaRateLimitError(FirewallaAPIError):
    """Raised when the API responds with HTTP 429 Too Many Requests."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limited by the Firewalla MSP API (HTTP 429)"
        if retry_after:
            msg += f"; retry after {retry_after:.0f}s"
        super().__init__(msg)
