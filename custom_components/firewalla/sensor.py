"""Sensor platform - box diagnostic counts."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .firewalla_msp_api import Box
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FirewallaEntity, box_device_info


@dataclass(frozen=True, kw_only=True)
class FirewallaSensorDescription(SensorEntityDescription):
    """Describes a Firewalla box sensor.

    ``value_fn`` pulls the value from a Box model instance. Kept simple on
    purpose — if we later need per-device sensors this pattern generalises.
    """

    value_fn: Callable[[Box], int | str | None]


SENSORS: tuple[FirewallaSensorDescription, ...] = (
    FirewallaSensorDescription(
        key="device_count",
        translation_key="device_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda box: box.device_count,
    ),
    FirewallaSensorDescription(
        key="rule_count",
        translation_key="rule_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda box: box.rule_count,
    ),
    FirewallaSensorDescription(
        key="alarm_count",
        translation_key="alarm_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda box: box.alarm_count,
    ),
    FirewallaSensorDescription(
        key="public_ip",
        translation_key="public_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda box: box.public_ip,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        FirewallaBoxSensor(coordinator, desc) for desc in SENSORS
    )


class FirewallaBoxSensor(FirewallaEntity, SensorEntity):
    entity_description: FirewallaSensorDescription

    def __init__(self, coordinator, description: FirewallaSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.box_gid}:{description.key}"
        self._attr_device_info = box_device_info(coordinator.data.box)

    @property
    def native_value(self) -> int | str | None:
        return self.entity_description.value_fn(self.coordinator.data.box)
