"""The Firewalla MSP integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .firewalla_msp_api import FirewallaMSPClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BOX_GID,
    CONF_MSP_DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import FirewallaCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

type FirewallaConfigEntry = ConfigEntry[FirewallaRuntimeData]


@dataclass
class FirewallaRuntimeData:
    """Runtime data kept on the ConfigEntry for the lifetime of the entry."""

    client: FirewallaMSPClient
    coordinator: FirewallaCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: FirewallaConfigEntry) -> bool:
    """Set up a Firewalla box from a config entry."""
    msp_domain = entry.data[CONF_MSP_DOMAIN]
    token = entry.data[CONF_TOKEN]
    box_gid = entry.data[CONF_BOX_GID]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # Share HA's aiohttp session so we don't open a new connection pool.
    session = async_get_clientsession(hass)
    client = FirewallaMSPClient(msp_domain, token, session=session)

    coordinator = FirewallaCoordinator(hass, entry, client, box_gid, scan_interval)

    # First refresh — raises ConfigEntryAuthFailed / ConfigEntryNotReady on failure.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = FirewallaRuntimeData(client=client, coordinator=coordinator)

    # Reload on options change (so scan_interval updates apply immediately).
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Services are registered once, shared across all entries.
    async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FirewallaConfigEntry) -> bool:
    """Unload a Firewalla box."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # Nothing to tear down on the client because we're sharing HA's session.

    # If this was the last entry, drop services too.
    remaining = [
        e for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ]
    if not remaining:
        async_unload_services(hass)

    return unload_ok


async def _async_update_options(hass: HomeAssistant, entry: FirewallaConfigEntry) -> None:
    """Reload the entry when options change (e.g., scan_interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
