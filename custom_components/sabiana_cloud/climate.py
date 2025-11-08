from __future__ import annotations
from typing import List, Optional
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
    FAN_AUTO,
)
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN, DEFAULT_FAN_MAP
from .coordinator import SabianaCoordinator

HVAC_MAP_API_TO_HA = {
    "heating": HVACMode.HEAT,
    "cooling": HVACMode.COOL,
    "auto": HVACMode.AUTO,
    "ventilate": HVACMode.FAN_ONLY,
}
HVAC_MAP_HA_TO_API = {
    HVACMode.HEAT: "heating",
    HVACMode.COOL: "cooling",
    HVACMode.AUTO: "auto",
    HVACMode.FAN_ONLY: "ventilate",
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: SabianaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: List[SabianaClimate] = [SabianaClimate(coordinator, u) for u in coordinator.data.get("units", [])]
    async_add_entities(entities, update_before_add=True)

class SabianaClimate(CoordinatorEntity, ClimateEntity):
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.FAN_ONLY]
    _attr_fan_modes = [FAN_AUTO, "low", "medium", "high"]

    def __init__(self, coordinator: SabianaCoordinator, unit: dict) -> None:
        super().__init__(coordinator)
        self._unit = unit
        self._address = unit.get("address")
        self._group_id = unit.get("groupId")
        name = unit.get("name") or self._address or "Vent"
        self._attr_name = f"Sabiana {name}"
        self._attr_unique_id = f"sabiana:{self._group_id}:{self._address}"
        self._fan_map = DEFAULT_FAN_MAP
        self._fan_map_inv = {v: k for k, v in self._fan_map.items()}
        self._fan_map_inv[FAN_AUTO] = "auto"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Sabiana",
            model=unit.get("controllerType") or "Vent",
            name=self._attr_name,
        )


    def _current_unit(self) -> dict:
        u = self.coordinator.data.get("units", [])
        return next((x for x in u if x.get("address") == self._address and x.get("groupId") == self._group_id), self._unit)

    @property
    def _v(self) -> dict:
        return (self._current_unit().get("ventUnit") or {})

    def _clamp(self, value: float, v: dict) -> float:
        mode_api = (v.get("mode") or "").lower()
        if mode_api == "heating":
            mn, mx = v.get("setPointHeatingMin"), v.get("setPointHeatingMax")
        elif mode_api == "cooling":
            mn, mx = v.get("setPointCoolingMin"), v.get("setPointCoolingMax")
        else:
            mn, mx = v.get("setPointHeatingMin"), v.get("setPointCoolingMax")
        try:
            if mn is not None: value = max(value, float(mn))
            if mx is not None: value = min(value, float(mx))
        except Exception:
            pass
        return value

    @property
    def hvac_mode(self) -> HVACMode:
        v = self._v
        is_on = v.get("on")
        mode_api = (v.get("mode") or "").lower()
        if not is_on:
            return HVACMode.OFF
        return HVAC_MAP_API_TO_HA.get(mode_api, HVACMode.AUTO)

    @property
    def fan_mode(self) -> Optional[str]:
        v = self._v
        api_fan = v.get("fan")
        if api_fan is None:
            return None
        return self._fan_map.get(api_fan, str(api_fan).lower())

    @property
    def current_temperature(self) -> Optional[float]:
        return self._v.get("t1")

    @property
    def target_temperature(self) -> Optional[float]:
        v = self._v
        mode_api = (v.get("mode") or "").lower()
        if mode_api == "heating":
            return v.get("setPointHeating")
        if mode_api == "cooling":
            return v.get("setPointCooling")
        return v.get("setPoint") or v.get("setPointAutoMode")

    @property
    def min_temp(self) -> Optional[float]:
        v = self._v
        mode_api = (v.get("mode") or "").lower()
        if mode_api == "heating":
            return v.get("setPointHeatingMin")
        if mode_api == "cooling":
            return v.get("setPointCoolingMin")
        return v.get("setPointHeatingMin")

    @property
    def max_temp(self) -> Optional[float]:
        v = self._v
        mode_api = (v.get("mode") or "").lower()
        if mode_api == "heating":
            return v.get("setPointHeatingMax")
        if mode_api == "cooling":
            return v.get("setPointCoolingMax")
        return v.get("setPointCoolingMax")

    @property
    def extra_state_attributes(self):
        v = self._v
        this = self._current_unit()
        pending = bool(this.get("__pending"))
        return {
            "address": self._address,
            "group_id": self._group_id,
            "t1_air": v.get("t1"),
            "t3_water": v.get("t3"),
            "raw_mode": v.get("mode"),
            "raw_fan": v.get("fan"),
            "pending": pending,  
        }


    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        v = dict(self._v)
        if hvac_mode == HVACMode.OFF:
            on = False
            api_mode = (v.get("mode") or "auto")
        else:
            on = True
            api_mode = HVAC_MAP_HA_TO_API.get(hvac_mode, "auto")

        payload = {
            "on": on,
            "mode": api_mode,
            "fan": v.get("fan") or "auto",
            "setPoint": self.target_temperature or v.get("setPoint") or v.get("setPointHeating") or v.get("setPointCooling") or 22.0,
        }

        self.coordinator.mark_pending(self._group_id, self._address, {
            "on": payload["on"],
            "mode": payload["mode"],
            "fan": payload["fan"],
            "setPoint": payload["setPoint"],
        })

        v.update({"on": on, "mode": api_mode})
        self._poke_local_cache(v)
        self.async_write_ha_state()

        await self.coordinator.client.cmd_vent(self._address, payload)
        v.update({"on": on, "mode": api_mode})
        self._poke_local_cache(v)
        self.async_write_ha_state()

        await self.coordinator.client.cmd_vent(self._address, payload)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        v = dict(self._v)
        api_fan = self._fan_map_inv.get(fan_mode, "auto")
        payload = {
            "on": v.get("on", True),
            "mode": v.get("mode") or "auto",
            "fan": api_fan,
            "setPoint": self.target_temperature or v.get("setPoint") or v.get("setPointHeating") or v.get("setPointCooling") or 22.0,
        }

        v.update({"fan": api_fan})
        self._poke_local_cache(v)
        self.async_write_ha_state()

        await self.coordinator.client.cmd_vent(self._address, payload)

    async def async_set_temperature(self, **kwargs) -> None:
        new_temp = kwargs.get("temperature")
        if new_temp is None:
            return
        v = dict(self._v)
        new_temp = float(new_temp)
        new_temp = self._clamp(new_temp, v)

        payload = {
            "on": v.get("on", True),
            "mode": v.get("mode") or "auto",
            "fan": v.get("fan") or "auto",
            "setPoint": new_temp,
        }

        mode_api = (v.get("mode") or "").lower()
        if mode_api == "heating":
            v["setPointHeating"] = new_temp
        elif mode_api == "cooling":
            v["setPointCooling"] = new_temp
        else:
            v["setPoint"] = new_temp

        self._poke_local_cache(v)
        self.async_write_ha_state()

        await self.coordinator.client.cmd_vent(self._address, payload)


    def _poke_local_cache(self, new_v: dict) -> None:
        """Aggiorna la cache dell'unit corrente nel coordinator."""
        units = self.coordinator.data.get("units", [])
        for i, u in enumerate(units):
            if u.get("address") == self._address and u.get("groupId") == self._group_id:
                merged = dict(u)
                vv = dict(u.get("ventUnit") or {})
                vv.update(new_v)
                merged["ventUnit"] = vv
                units[i] = merged
                break

