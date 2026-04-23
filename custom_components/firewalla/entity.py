"""Shared entity base classes and helpers.

Keeps DeviceInfo construction and the CoordinatorEntity wiring in one place so
each platform file stays focused on its own entity types.
"""
from __future__ import annotations

from .firewalla_msp_api import Box, Device
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HIERARCHICAL, DEFAULT_HIERARCHICAL, DOMAIN
from .coordinator import FirewallaCoordinator


def box_device_info(box: Box) -> DeviceInfo:
    """DeviceInfo for the Firewalla box itself."""
    return DeviceInfo(
        identifiers={(DOMAIN, box.gid)},
        manufacturer="Firewalla",
        model=box.model,
        name=box.name or f"Firewalla {box.model}",
        sw_version=box.version,
        configuration_url=None,
    )


def group_device_info(box_gid: str, group_id: str, group_name: str) -> DeviceInfo:
    """DeviceInfo for a device group, parented under the box."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{box_gid}:group:{group_id}")},
        name=group_name,
        model="Device Group",
        via_device=(DOMAIN, box_gid),
    )


def rules_device_info(box: Box) -> DeviceInfo:
    """DeviceInfo for the virtual 'Rules' device, parented under the box."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{box.gid}:rules")},
        name="Rules",
        model="Firewall Rules",
        via_device=(DOMAIN, box.gid),
    )


def device_device_info(coordinator: FirewallaCoordinator, device: Device) -> DeviceInfo:
    """DeviceInfo for a network device tracked behind a box.

    Devices with a group are nested under that group's HA device. Ungrouped
    devices fall back to the hierarchical option (box or flat).
    """
    box_gid = coordinator.box_gid
    info = DeviceInfo(
        identifiers={(DOMAIN, f"{box_gid}:device:{device.id}")},
        manufacturer=device.mac_vendor or "Unknown",
        name=device.name or device.id,
        model="Network device",
    )
    if device.group:
        info["via_device"] = (DOMAIN, f"{box_gid}:group:{device.group.id}")
    else:
        hierarchical = coordinator.config_entry.options.get(CONF_HIERARCHICAL, DEFAULT_HIERARCHICAL)
        if hierarchical:
            info["via_device"] = (DOMAIN, box_gid)
    return info


class FirewallaEntity(CoordinatorEntity[FirewallaCoordinator]):
    """Base for all Firewalla entities.

    Subclasses set ``_attr_unique_id``, ``_attr_name``, ``_attr_device_info``.
    """

    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.last_update_success
