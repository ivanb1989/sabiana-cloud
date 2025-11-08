from __future__ import annotations
from typing import Any, Dict
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SOURCE,
    CONF_SETPOINT_STRATEGY,
    CONF_FAN_MAP,
    CONF_DEBUG,
    DEFAULT_BASE_URL,
    DEFAULT_FAN_MAP,
    DEFAULT_SCAN_INTERVAL,
)

USER_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
    vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
})

OPTIONS_SCHEMA = vol.Schema({
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    vol.Optional(CONF_TEMPERATURE_SOURCE, default="t1"): vol.In(["t1", "t3"]),
    vol.Optional(CONF_SETPOINT_STRATEGY, default="single"): vol.In(["single", "dual"]),
    vol.Optional(CONF_FAN_MAP, default=DEFAULT_FAN_MAP): dict,
    vol.Optional(CONF_DEBUG, default=False): bool,
})

class SabianaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if not api_key:
                errors["base"] = "invalid_auth"
            else:
                unique = f"{DOMAIN}_{hash(api_key)}"
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title="Sabiana Cloud", data=user_input)

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SabianaOptionsFlow(config_entry)

class SabianaOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {
            CONF_SCAN_INTERVAL: self.entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_TEMPERATURE_SOURCE: self.entry.options.get(CONF_TEMPERATURE_SOURCE, "t1"),
            CONF_SETPOINT_STRATEGY: self.entry.options.get(CONF_SETPOINT_STRATEGY, "single"),
            CONF_FAN_MAP: self.entry.options.get(CONF_FAN_MAP, DEFAULT_FAN_MAP),
            CONF_DEBUG: self.entry.options.get(CONF_DEBUG, False),
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Optional(CONF_SCAN_INTERVAL, default=current[CONF_SCAN_INTERVAL]): int,
            vol.Optional(CONF_TEMPERATURE_SOURCE, default=current[CONF_TEMPERATURE_SOURCE]): vol.In(["t1", "t3"]),
            vol.Optional(CONF_SETPOINT_STRATEGY, default=current[CONF_SETPOINT_STRATEGY]): vol.In(["single", "dual"]),
            vol.Optional(CONF_FAN_MAP, default=current[CONF_FAN_MAP]): dict,
            vol.Optional(CONF_DEBUG, default=current[CONF_DEBUG]): bool,
        }))
