"""Device tracker platform - one entity per device seen by the box.

Uses the ``ScannerEntity`` base because Firewalla tells us online/offline state
with a MAC identifier. Entities are created once per discovered device and
kept alive even if the device drops out of the polled list temporarily.
"""
from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FirewallaCoordinator
from .entity import FirewallaEntity, device_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    known: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new_entities: list[FirewallaDeviceTracker] = []
        for device_id in coordinator.data.devices:
            if device_id in known:
                continue
            known.add(device_id)
            new_entities.append(FirewallaDeviceTracker(coordinator, device_id))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class FirewallaDeviceTracker(FirewallaEntity, ScannerEntity):
    _attr_translation_key = "network_device"

    def __init__(self, coordinator: FirewallaCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{coordinator.box_gid}:device:{device_id}"
        device = coordinator.data.devices[device_id]
        self._attr_name = device.name or device_id
        self._attr_device_info = device_device_info(coordinator, device)

    @property
    def _device(self):
        return self.coordinator.data.devices.get(self._device_id)

    @property
    def is_connected(self) -> bool:
        device = self._device
        return bool(device and device.online)

    @property
    def ip_address(self) -> str | None:
        device = self._device
        return device.ip if device else None

    @property
    def mac_address(self) -> str | None:
        # Firewalla's device id IS the MAC for physical devices.
        return self._device_id if ":" in self._device_id else None

    @property
    def hostname(self) -> str | None:
        device = self._device
        return device.name if device else None

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        device = self._device
        if device is None:
            return {}
        return {
            "mac_vendor": device.mac_vendor,
            "network": device.network_name,
            "group": device.group.name if device.group else None,
            "total_download": device.total_download,
            "total_upload": device.total_upload,
        }
