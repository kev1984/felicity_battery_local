"""Config flow for Felicity Battery (Local)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigSubentryFlow, SubentryFlowResult
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CMD_REAL_INFO,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SOCKET_TIMEOUT,
)
from .protocol import FelicityConnectionError, FelicityNoDataError, async_send_command

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


async def _validate_device(host: str, port: int) -> dict[str, str]:
    """Try to talk to a battery. Returns a dict of errors (empty if OK)."""
    try:
        data = await async_send_command(host, port, CMD_REAL_INFO, SOCKET_TIMEOUT)
    except FelicityConnectionError:
        return {"base": "cannot_connect"}
    except FelicityNoDataError:
        return {"base": "no_data"}

    if "Batsoc" not in data and "Batt" not in data:
        return {"base": "unexpected_response"}
    return {}


class FelicityBatteryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the first (main) battery."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()

            errors = await _validate_device(user_input[CONF_HOST], user_input[CONF_PORT])
            if not errors:
                return self.async_create_entry(
                    title=f"Felicity Battery ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FelicityBatteryOptionsFlow(config_entry)

    @classmethod
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Additional batteries are added as subentries of the same entry."""
        return {"battery": FelicityBatterySubentryFlow}


class FelicityBatterySubentryFlow(ConfigSubentryFlow):
    """Add an extra battery to an existing Felicity Battery (Local) entry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await _validate_device(user_input[CONF_HOST], user_input[CONF_PORT])
            if not errors:
                return self.async_create_entry(
                    title=f"Felicity Battery ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class FelicityBatteryOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.options.get(
            CONF_SCAN_INTERVAL,
            self._entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Optional(CONF_SCAN_INTERVAL, default=current): int}
            ),
        )
