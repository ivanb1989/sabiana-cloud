from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any, Dict, List, Tuple
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
)
from .api import SabianaApiClient, SabianaApiError

_LOGGER = logging.getLogger(__name__)

def _unit_key(group_id: Any, address: Any) -> Tuple[Any, Any]:
    return (group_id, address)

class SabianaCoordinator(DataUpdateCoordinator[Dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        api_key = entry.data[CONF_API_KEY]
        base_url = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)

        session = async_get_clientsession(hass)
        self.client = SabianaApiClient(session=session, base_url=base_url, api_key=api_key)

        scan = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=scan),
        )


        self.data = {"groups": [], "units": []}
        self._pending: Dict[Tuple[Any, Any], Dict[str, Any]] = {}

    def mark_pending(self, group_id: Any, address: Any, desired: Dict[str, Any]) -> None:
        self._pending[_unit_key(group_id, address)] = {
            "since_ms": int(time.time() * 1000),
            "desired": desired,
        }

    def _apply_pending_guard(self, units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        to_clear: List[Tuple[Any, Any]] = []

        for u in units:
            gid = u.get("groupId")
            addr = u.get("address")
            key = _unit_key(gid, addr)
            v = u.get("ventUnit") or {}
            last_update = u.get("lastUpdate") or 0  # epoch ms

            pending = self._pending.get(key)
            if pending:
                since_ms = pending.get("since_ms", 0)
                desired = pending.get("desired", {})

                if last_update < since_ms:
                    vv = dict(v)
                    vv.update(desired)
                    u = dict(u)
                    u["ventUnit"] = vv
                    u["__pending"] = True
                else:
                    to_clear.append(key)
                    u = dict(u)
                    u["__pending"] = False
            else:
                u = dict(u)
                u["__pending"] = False

            merged.append(u)
        for key in to_clear:
            self._pending.pop(key, None)

        return merged

    async def _async_update_data(self) -> Dict[str, Any]:
        """Scarica i dati reali da /api/v1/vent, normalizza e applica il pending-guard."""
        try:
            groups = await self.client.list_vent()
        except SabianaApiError as e:
            raise UpdateFailed(str(e)) from e
        except Exception as e:
            raise UpdateFailed(f"Errore generico: {e}") from e

        units: List[Dict[str, Any]] = []
        for g in groups or []:
            gid = g.get("groupId")
            gname = g.get("groupName")
            for u in (g.get("units") or []):
                unit_type = (u.get("unitType") or "").lower()
                if unit_type not in ("vent", "ventunit"):
                    continue
                units.append({
                    "groupId": gid,
                    "groupName": gname,
                    "name": u.get("name"),
                    "address": u.get("address"),
                    "lastUpdate": u.get("lastUpdate"),
                    "controllerType": u.get("controllerType"),
                    "ventUnit": u.get("ventUnit") or {},
                })
        units = self._apply_pending_guard(units)

        return {"groups": groups, "units": units}
