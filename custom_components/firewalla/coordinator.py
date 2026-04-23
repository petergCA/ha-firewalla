"""Data coordinator for a single Firewalla box.

Pulls boxes/devices/rules on a configurable interval and keeps a cache of
the "managed" rules we use to implement device/group pauses (those tagged
with [HA-PAUSE] in their notes).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from .firewalla_msp_api import (
    Box,
    Device,
    FirewallaAPIError,
    FirewallaAuthError,
    FirewallaMSPClient,
    Rule,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    MANAGED_RULE_PREFIX,
    POST_WRITE_REFRESH_DELAY,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class FirewallaData:
    """Snapshot of everything we know about one box at a given moment."""

    box: Box
    devices: dict[str, Device] = field(default_factory=dict)  # keyed by device.id
    rules: dict[str, Rule] = field(default_factory=dict)  # keyed by rule.id
    groups: dict[str, str] = field(default_factory=dict)  # group_id -> group_name
    managed_rules: dict[str, Rule] = field(default_factory=dict)  # rule.id -> Rule

    def managed_rule_for(self, kind: str, name: str) -> Rule | None:
        """Find the managed [HA-PAUSE] rule for a device or group, if any."""
        wanted = f"{MANAGED_RULE_PREFIX} {kind}={name}"
        for rule in self.managed_rules.values():
            if rule.notes == wanted:
                return rule
        return None


class FirewallaCoordinator(DataUpdateCoordinator[FirewallaData]):
    """Polls the MSP API for one box and serves data to entities."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: FirewallaMSPClient,
        box_gid: str,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{box_gid}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.client = client
        self.box_gid = box_gid

    async def _async_update_data(self) -> FirewallaData:
        try:
            # Fetch everything concurrently; the MSP endpoints are independent.
            boxes_task = asyncio.create_task(self.client.list_boxes())
            devices_task = asyncio.create_task(self.client.list_devices(box_gid=self.box_gid))
            rules_task = asyncio.create_task(self.client.list_rules(box_gid=self.box_gid))

            boxes, devices, rules = await asyncio.gather(
                boxes_task, devices_task, rules_task
            )
        except FirewallaAuthError as err:
            # Triggers reauth flow rather than endlessly retrying.
            raise ConfigEntryAuthFailed(str(err)) from err
        except FirewallaAPIError as err:
            raise UpdateFailed(f"Firewalla MSP API error: {err}") from err

        # Locate our box in the list.
        box = next((b for b in boxes if b.gid == self.box_gid), None)
        if box is None:
            raise UpdateFailed(
                f"Box {self.box_gid} not found in MSP inventory (was it removed?)"
            )

        # Derive groups from device payloads (no dedicated endpoint exists).
        groups: dict[str, str] = {}
        for d in devices:
            if d.group and d.group.id not in groups:
                groups[d.group.id] = d.group.name

        managed = {
            r.id: r for r in rules if r.notes.startswith(MANAGED_RULE_PREFIX)
        }

        return FirewallaData(
            box=box,
            devices={d.id: d for d in devices},
            rules={r.id: r for r in rules},
            groups=groups,
            managed_rules=managed,
        )

    async def async_request_refresh_soon(self) -> None:
        """Request a coordinator refresh after a short delay.

        Used after writes so the MSP API has a chance to reflect the change.
        """
        await asyncio.sleep(POST_WRITE_REFRESH_DELAY)
        await self.async_request_refresh()
