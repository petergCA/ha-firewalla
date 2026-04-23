"""Config and options flow for Firewalla MSP."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from firewalla_msp_api import (
    Box,
    FirewallaAPIError,
    FirewallaAuthError,
    FirewallaConnectionError,
    FirewallaMSPClient,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BOX_GID,
    CONF_BOX_NAME,
    CONF_HIERARCHICAL,
    CONF_MSP_DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_HIERARCHICAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class FirewallaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two-step flow: auth (domain+token) -> pick a box."""

    VERSION = 1

    def __init__(self) -> None:
        self._msp_domain: str | None = None
        self._token: str | None = None
        self._boxes: list[Box] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: collect MSP domain + token and validate by listing boxes."""
        errors: dict[str, str] = {}

        if user_input is not None:
            msp_domain = user_input[CONF_MSP_DOMAIN].strip()
            token = user_input[CONF_TOKEN].strip()

            session = async_get_clientsession(self.hass)
            client = FirewallaMSPClient(msp_domain, token, session=session)
            try:
                self._boxes = await client.list_boxes()
            except FirewallaAuthError:
                errors["base"] = "invalid_auth"
            except FirewallaConnectionError:
                errors["base"] = "cannot_connect"
            except FirewallaAPIError:
                errors["base"] = "unknown"
            except Exception:  # noqa: BLE001 — unexpected error, we want to log
                _LOGGER.exception("Unexpected error validating Firewalla MSP credentials")
                errors["base"] = "unknown"
            else:
                if not self._boxes:
                    errors["base"] = "no_boxes"
                else:
                    self._msp_domain = msp_domain
                    self._token = token
                    return await self.async_step_pick_box()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MSP_DOMAIN): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_box(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: choose which box to add as this config entry."""
        assert self._msp_domain is not None
        assert self._token is not None

        # Filter out boxes already configured.
        existing_gids = {
            entry.data[CONF_BOX_GID] for entry in self._async_current_entries()
        }
        available = [b for b in self._boxes if b.gid not in existing_gids]

        if not available:
            return self.async_abort(reason="all_boxes_configured")

        if user_input is not None:
            gid = user_input[CONF_BOX_GID]
            box = next((b for b in available if b.gid == gid), None)
            if box is None:
                return self.async_abort(reason="box_not_found")

            await self.async_set_unique_id(gid)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=box.name or f"Firewalla {box.model}",
                data={
                    CONF_MSP_DOMAIN: self._msp_domain,
                    CONF_TOKEN: self._token,
                    CONF_BOX_GID: gid,
                    CONF_BOX_NAME: box.name,
                },
            )

        choices = {b.gid: f"{b.name} ({b.model}, {b.gid[:8]}…)" for b in available}
        return self.async_show_form(
            step_id="pick_box",
            data_schema=vol.Schema({vol.Required(CONF_BOX_GID): vol.In(choices)}),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication when the token expires or is revoked."""
        self._msp_domain = entry_data[CONF_MSP_DOMAIN]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        assert self._msp_domain is not None

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            session = async_get_clientsession(self.hass)
            client = FirewallaMSPClient(self._msp_domain, token, session=session)
            try:
                await client.list_boxes()
            except FirewallaAuthError:
                errors["base"] = "invalid_auth"
            except FirewallaConnectionError:
                errors["base"] = "cannot_connect"
            except FirewallaAPIError:
                errors["base"] = "unknown"
            else:
                existing = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    existing,
                    data={**existing.data, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return FirewallaOptionsFlow()


class FirewallaOptionsFlow(OptionsFlow):
    """Expose polling interval and device hierarchy mode."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        scan_validator = vol.All(
            vol.Coerce(int),
            vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): scan_validator,
                    vol.Required(
                        CONF_HIERARCHICAL,
                        default=opts.get(CONF_HIERARCHICAL, DEFAULT_HIERARCHICAL),
                    ): bool,
                }
            ),
        )
