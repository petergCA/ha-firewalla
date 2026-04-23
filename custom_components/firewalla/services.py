"""Services for the Firewalla integration.

Currently exposes two timed-pause services:

- ``firewalla.pause_device`` — pause a single network device for ``duration``
- ``firewalla.pause_group`` — pause a whole device group for ``duration``

Both accept an HA entity_id target so users can select from the UI. Under the
hood they reuse the same managed-rule machinery as the switch platform, then
schedule an auto-unpause call after ``duration``.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    ATTR_DURATION,
    DEFAULT_PAUSE_DURATION,
    DOMAIN,
    SERVICE_PAUSE_DEVICE,
    SERVICE_PAUSE_GROUP,
)

_LOGGER = logging.getLogger(__name__)


# Schemas accept HA's standard entity_id list plus a duration.
_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_DURATION, default=DEFAULT_PAUSE_DURATION.total_seconds()): vol.All(
            vol.Coerce(float), vol.Range(min=1)
        ),
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register services once per HA lifecycle.

    Calling repeatedly is safe — HA will overwrite the existing handler.
    """

    async def _pause(call: ServiceCall, *, unique_key_prefix: str) -> None:
        """Shared implementation for both pause services.

        ``unique_key_prefix`` is either ``"device-pause:"`` or ``"group-pause:"``
        so we can match against the switch entities' unique_ids.
        """
        entity_ids: list[str] = call.data[ATTR_ENTITY_ID]
        duration = timedelta(seconds=call.data[ATTR_DURATION])

        registry = er.async_get(hass)
        switches: list[Any] = []

        for entity_id in entity_ids:
            entry = registry.async_get(entity_id)
            if entry is None or entry.platform != DOMAIN or entry.domain != "switch":
                raise HomeAssistantError(
                    f"{entity_id} is not a Firewalla switch entity"
                )
            if unique_key_prefix not in (entry.unique_id or ""):
                raise HomeAssistantError(
                    f"{entity_id} is not a "
                    f"{'device' if 'device-pause' in unique_key_prefix else 'group'} pause switch"
                )

            # Resolve the actual entity object via the component platform.
            component = hass.data["entity_components"].get("switch")
            if component is None:
                raise HomeAssistantError("Switch component not loaded")
            entity_obj = component.get_entity(entity_id)
            if entity_obj is None:
                raise HomeAssistantError(f"Could not resolve entity {entity_id}")
            switches.append(entity_obj)

        # Turn them all off (=pause) in parallel.
        await asyncio.gather(*(s.async_turn_off() for s in switches))

        # Schedule auto-resume after duration. We use hass.loop.call_later so
        # the tasks are cleaned up if HA shuts down.
        async def _resume_after() -> None:
            await asyncio.sleep(duration.total_seconds())
            try:
                await asyncio.gather(*(s.async_turn_on() for s in switches))
            except Exception:  # noqa: BLE001 — log & move on; we can't crash the loop
                _LOGGER.exception("Error auto-resuming paused Firewalla entities")

        hass.async_create_background_task(
            _resume_after(), f"{DOMAIN}-timed-pause-{entity_ids}"
        )

    async def pause_device(call: ServiceCall) -> None:
        await _pause(call, unique_key_prefix="device-pause:")

    async def pause_group(call: ServiceCall) -> None:
        await _pause(call, unique_key_prefix="group-pause:")

    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE_DEVICE, pause_device, schema=_BASE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE_GROUP, pause_group, schema=_BASE_SCHEMA
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove Firewalla services (called when the last entry is unloaded)."""
    for svc in (SERVICE_PAUSE_DEVICE, SERVICE_PAUSE_GROUP):
        if hass.services.has_service(DOMAIN, svc):
            hass.services.async_remove(DOMAIN, svc)
