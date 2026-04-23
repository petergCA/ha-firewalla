"""Switch platform.

Three kinds of switches are exposed:

1. **Rule switches** — one per existing Firewalla rule. ON = active, OFF = paused.
   These just wrap ``pause_rule``/``resume_rule``.

2. **Device pause switches** — one per device. ON = device has internet access
   (no managed block rule, or the managed rule is paused). OFF = device is paused
   via a managed block rule. The integration auto-creates the block rule on the
   first OFF toggle and reuses it thereafter.

3. **Group pause switches** — same idea as device pause, but the managed rule's
   scope is ``group:<id>`` instead of ``device:<mac>``.

All switches use optimistic state updates + a post-write refresh so the UI feels
snappy even though the MSP API takes a second or two to reflect writes.
"""
from __future__ import annotations

import logging
from typing import Any

from .firewalla_msp_api import FirewallaAPIError
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import managed_rule_note
from .coordinator import FirewallaCoordinator
from .entity import FirewallaEntity, box_device_info, device_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FirewallaCoordinator = entry.runtime_data.coordinator
    known_rules: set[str] = set()
    known_devices: set[str] = set()
    known_groups: set[str] = set()

    @callback
    def _add_new_entities() -> None:
        new_entities: list[SwitchEntity] = []

        # User-visible (non-managed) rules get switches.
        for rule_id in coordinator.data.rules:
            if rule_id in known_rules:
                continue
            if rule_id in coordinator.data.managed_rules:
                continue
            known_rules.add(rule_id)
            new_entities.append(FirewallaRuleSwitch(coordinator, rule_id))

        # One pause switch per device.
        for device_id in coordinator.data.devices:
            if device_id in known_devices:
                continue
            known_devices.add(device_id)
            new_entities.append(FirewallaDevicePauseSwitch(coordinator, device_id))

        # One pause switch per group.
        for group_id in coordinator.data.groups:
            if group_id in known_groups:
                continue
            known_groups.add(group_id)
            new_entities.append(FirewallaGroupPauseSwitch(coordinator, group_id))

        if new_entities:
            async_add_entities(new_entities)

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


# ---------------------------------------------------------------------------
# Rule switches
# ---------------------------------------------------------------------------


class FirewallaRuleSwitch(FirewallaEntity, SwitchEntity):
    """ON = rule active, OFF = rule paused."""

    _attr_translation_key = "rule"

    def __init__(self, coordinator: FirewallaCoordinator, rule_id: str) -> None:
        super().__init__(coordinator)
        self._rule_id = rule_id
        rule = coordinator.data.rules[rule_id]
        self._attr_unique_id = f"{coordinator.box_gid}:rule:{rule_id}"
        self._attr_name = rule.notes or f"Rule {rule_id[:8]}"
        self._attr_device_info = box_device_info(coordinator.data.box)
        self._optimistic_state: bool | None = None

    @property
    def _rule(self):
        return self.coordinator.data.rules.get(self._rule_id)

    @property
    def is_on(self) -> bool | None:
        if self._optimistic_state is not None:
            return self._optimistic_state
        rule = self._rule
        return rule.is_active if rule else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rule = self._rule
        if rule is None:
            return {}
        return {
            "action": rule.action,
            "direction": rule.direction,
            "target_type": rule.target.type if rule.target else None,
            "target_value": rule.target.value if rule.target else None,
            "scope_type": rule.scope.type if rule.scope else None,
            "scope_value": rule.scope.value if rule.scope else None,
            "notes": rule.notes,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._optimistic_state = True
        self.async_write_ha_state()
        try:
            await self.coordinator.client.resume_rule(self._rule_id)
        except FirewallaAPIError as err:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(f"Failed to resume rule: {err}") from err
        await self.coordinator.async_request_refresh_soon()
        self._optimistic_state = None

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._optimistic_state = False
        self.async_write_ha_state()
        try:
            await self.coordinator.client.pause_rule(self._rule_id)
        except FirewallaAPIError as err:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise HomeAssistantError(f"Failed to pause rule: {err}") from err
        await self.coordinator.async_request_refresh_soon()
        self._optimistic_state = None


# ---------------------------------------------------------------------------
# Pause switches (shared helpers)
# ---------------------------------------------------------------------------


class _PauseSwitchBase(FirewallaEntity, SwitchEntity):
    """Common logic for device/group pause switches.

    Pause state is represented by a managed block rule with a tagged notes
    field. The rule is created on first OFF toggle, then toggled via
    pause/resume for later changes.

    HA semantics: ON means "allowed" (either no managed rule, or it's paused).
    OFF means "blocked" (managed rule exists and is active).
    """

    # Subclasses populate these
    _kind: str  # "device" | "group"
    _target_name: str
    _scope_type: str  # "device" | "tag" — scope value goes in the rule
    _scope_value: str

    _attr_icon = "mdi:pause-circle"

    def __init__(self, coordinator: FirewallaCoordinator) -> None:
        super().__init__(coordinator)
        self._optimistic_state: bool | None = None

    @property
    def _managed_rule(self):
        return self.coordinator.data.managed_rule_for(self._kind, self._target_name)

    @property
    def is_on(self) -> bool:
        """ON = allowed (no active block rule)."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        rule = self._managed_rule
        if rule is None:
            return True  # No managed rule = not paused = allowed
        return not rule.is_active  # Rule exists but paused = allowed

    async def _ensure_and_activate_block_rule(self) -> None:
        """Pause the target: create the managed rule if absent, else resume it."""
        rule = self._managed_rule
        if rule is None:
            payload = {
                "action": "block",
                "direction": "bidirection",
                "gid": self.coordinator.box_gid,
                "notes": managed_rule_note(self._kind, self._target_name),
                "target": {"type": "internet", "value": ""},
                "scope": {"type": self._scope_type, "value": self._scope_value},
            }
            try:
                await self.coordinator.client.create_rule(payload)
            except FirewallaAPIError as err:
                raise HomeAssistantError(
                    f"Failed to create pause rule for {self._kind} '{self._target_name}': {err}"
                ) from err
            return
        # Rule exists but is paused; resume it (= activate the block).
        if not rule.is_active:
            try:
                await self.coordinator.client.resume_rule(rule.id)
            except FirewallaAPIError as err:
                raise HomeAssistantError(
                    f"Failed to activate pause rule for {self._kind} '{self._target_name}': {err}"
                ) from err

    async def _release_block_rule(self) -> None:
        """Unpause the target: pause the managed rule if it exists and is active."""
        rule = self._managed_rule
        if rule is None or not rule.is_active:
            return
        try:
            await self.coordinator.client.pause_rule(rule.id)
        except FirewallaAPIError as err:
            raise HomeAssistantError(
                f"Failed to release pause rule for {self._kind} '{self._target_name}': {err}"
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Allow traffic = release the block."""
        self._optimistic_state = True
        self.async_write_ha_state()
        try:
            await self._release_block_rule()
        except HomeAssistantError:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_request_refresh_soon()
        self._optimistic_state = None

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Block traffic = activate the block."""
        self._optimistic_state = False
        self.async_write_ha_state()
        try:
            await self._ensure_and_activate_block_rule()
        except HomeAssistantError:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_request_refresh_soon()
        self._optimistic_state = None


# ---------------------------------------------------------------------------
# Device pause switch
# ---------------------------------------------------------------------------


class FirewallaDevicePauseSwitch(_PauseSwitchBase):
    _kind = "device"
    _scope_type = "device"
    _attr_translation_key = "device_pause"

    def __init__(self, coordinator: FirewallaCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        device = coordinator.data.devices[device_id]
        self._target_name = device.name or device_id
        self._scope_value = device_id
        self._attr_unique_id = f"{coordinator.box_gid}:device-pause:{device_id}"
        self._attr_device_info = device_device_info(coordinator, device)
        # name is implied by translation_key + the HA device's own name

    @property
    def _managed_rule(self):
        # Resolve against the live device name in case the user renamed it.
        device = self.coordinator.data.devices.get(self._device_id)
        name = device.name if device else self._target_name
        return self.coordinator.data.managed_rule_for("device", name)


# ---------------------------------------------------------------------------
# Group pause switch
# ---------------------------------------------------------------------------


class FirewallaGroupPauseSwitch(_PauseSwitchBase):
    _kind = "group"
    _scope_type = "tag"  # MSP uses "tag" for device-group scope in rules
    _attr_translation_key = "group_pause"

    def __init__(self, coordinator: FirewallaCoordinator, group_id: str) -> None:
        super().__init__(coordinator)
        self._group_id = group_id
        group_name = coordinator.data.groups[group_id]
        self._target_name = group_name
        self._scope_value = group_id
        self._attr_unique_id = f"{coordinator.box_gid}:group-pause:{group_id}"
        self._attr_name = f"Pause group {group_name}"
        self._attr_device_info = box_device_info(coordinator.data.box)

    @property
    def _managed_rule(self):
        name = self.coordinator.data.groups.get(self._group_id, self._target_name)
        return self.coordinator.data.managed_rule_for("group", name)
