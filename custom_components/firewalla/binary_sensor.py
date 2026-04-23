"""Binary sensor platform - box online/offline.

Per-device online status lives in the device_tracker platform; this file
just handles the box itself.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FirewallaCoordinator
from .entity import FirewallaEntity, box_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([FirewallaBoxOnlineSensor(coordinator)])


class FirewallaBoxOnlineSensor(FirewallaEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "box_online"

    def __init__(self, coordinator: FirewallaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.box_gid}:online"
        self._attr_device_info = box_device_info(coordinator.data.box)

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.box.online
