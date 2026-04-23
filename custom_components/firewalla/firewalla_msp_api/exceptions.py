"""Exceptions for the Firewalla MSP API client."""
from __future__ import annotations


class FirewallaAPIError(Exception):
    """Base exception for all Firewalla MSP API errors."""


class FirewallaAuthError(FirewallaAPIError):
    """Raised when the token is invalid, expired, or forbidden."""


class FirewallaConnectionError(FirewallaAPIError):
    """Raised when the MSP host cannot be reached."""
