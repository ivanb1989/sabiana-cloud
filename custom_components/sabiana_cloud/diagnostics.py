from __future__ import annotations
from typing import Any, Dict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:

    coordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": entry.data,
            "options": entry.options,
            "version": entry.version,
        },
        "coordinator_last_update_success": coordinator.last_update_success,
        "units": coordinator.data.get("units"),
        "groups": coordinator.data.get("groups"),
    }
