"""Async HTTP client for the Firewalla MSP API v2."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .exceptions import FirewallaAPIError, FirewallaAuthError, FirewallaConnectionError
from .models import Box, Device, Rule

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)


class FirewallaMSPClient:
    """Thin async wrapper around the Firewalla MSP REST API."""

    def __init__(
        self,
        msp_domain: str,
        token: str,
        *,
        session: aiohttp.ClientSession,
    ) -> None:
        domain = msp_domain.rstrip("/")
        if domain.startswith(("http://", "https://")):
            domain = domain.split("://", 1)[1]
        self._base = f"https://{domain}/v2"
        self._headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        }
        self._session = session

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base}{path}"
        _LOGGER.debug("%s %s", method, url)
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                timeout=_TIMEOUT,
                **kwargs,
            ) as resp:
                if resp.status in (401, 403):
                    raise FirewallaAuthError(
                        f"Authentication failed (HTTP {resp.status})"
                    )
                if resp.status >= 400:
                    text = await resp.text()
                    raise FirewallaAPIError(f"HTTP {resp.status}: {text[:200]}")
                # Some endpoints return 200 with an empty body on success
                if resp.content_length == 0 or resp.status == 204:
                    return {}
                return await resp.json(content_type=None)
        except aiohttp.ClientConnectionError as err:
            raise FirewallaConnectionError(f"Cannot connect to {url}") from err
        except aiohttp.ServerTimeoutError as err:
            raise FirewallaConnectionError(f"Timeout connecting to {url}") from err
        except (FirewallaAPIError, FirewallaAuthError, FirewallaConnectionError):
            raise
        except Exception as err:
            raise FirewallaAPIError(f"Unexpected error calling {url}: {err}") from err

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_boxes(self) -> list[Box]:
        data = await self._request("GET", "/boxes")
        return [Box.from_dict(b) for b in _as_list(data)]

    async def list_devices(self, *, box_gid: str) -> list[Device]:
        data = await self._request("GET", f"/devices?gid={box_gid}")
        return [Device.from_dict(d) for d in _as_list(data)]

    async def list_rules(self, *, box_gid: str) -> list[Rule]:
        data = await self._request("GET", f"/rules?gid={box_gid}")
        return [Rule.from_dict(r) for r in _as_list(data)]

    async def pause_rule(self, rule_id: str) -> None:
        await self._request("POST", f"/rules/{rule_id}/pause")

    async def resume_rule(self, rule_id: str) -> None:
        await self._request("POST", f"/rules/{rule_id}/resume")

    async def create_rule(self, payload: dict[str, Any]) -> Rule:
        data = await self._request("POST", "/rules", json=payload)
        return Rule.from_dict(data)


def _as_list(data: Any) -> list[dict]:
    """Normalise API responses that may be a list or a dict with a results key."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "items"):
            if key in data:
                return data[key]
    return []
