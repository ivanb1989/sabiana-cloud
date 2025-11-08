from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime, timezone
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN
from .coordinator import SabianaCoordinator


SENSORS_MAIN = {
    "power": "Power",
    "mode": "Mode",
    "fan": "Fan",
    "t1": "T1 Aria",
    "t3": "T3 Acqua",
    "request": "Richiesta Termica",
    "setPointHeating": "Setpoint Heating",
    "setPointCooling": "Setpoint Cooling",
    "name": "Name",
    "address": "Address",
    "activeAlarms": "Active Alarms",
    "withActiveAlarms": "With Active Alarms",
}

EXTRA_TOP = {
    "lastUpdate",
    "unitType",
}

EXTRA_VENT = {
    "autoModeAvalible",
    "setPointAutoMode",
    "setPointAutoModeRange",
    "setPointHeatingMin",
    "setPointHeatingMax",
    "setPointCoolingMin",
    "setPointCoolingMax",
    "lockAllFeatures",
    "lockOnOff",
    "lockMode",
    "lockSet",
    "lockFan",
    "slave",
    "controllerType",
    "flap",
    "t2",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: SabianaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: List[SensorEntity] = []

    for u in coordinator.data.get("units", []):
        gid = u["groupId"]
        addr = u["address"]
        name = u.get("name") or addr
        vent = u.get("ventUnit") or {}
        main_values = {
            "power": "on" if vent.get("on") else "off",
            "mode": vent.get("mode"),
            "fan": vent.get("fan"),
            "request": "on" if vent.get("requestThermo") else "off",
            "t1": vent.get("t1"),
            "t3": vent.get("t3"),
            "setPointHeating": vent.get("setPointHeating"),
            "setPointCooling": vent.get("setPointCooling"),
            "name": name,
            "address": addr,
            "activeAlarms": ", ".join(map(str, vent.get("activeAlarms") or [])) if vent.get("activeAlarms") else "",
            "withActiveAlarms": bool(vent.get("withActiveAlarms")),
        }
        for key, label in SENSORS_MAIN.items():
            entities.append(
                SabianaSimpleSensor(
                    coordinator, gid, addr, name,
                    key=key,
                    value=main_values.get(key),
                    enabled_default=True,
                    diagnostic=(key in ("activeAlarms", "withActiveAlarms")),
                )
            )
        for key in EXTRA_TOP:
            entities.append(
                SabianaSimpleSensor(
                    coordinator, gid, addr, name,
                    key=key,
                    value=u.get(key),
                    enabled_default=False,
                    diagnostic=True,
                )
            )

        for key in EXTRA_VENT:
            entities.append(
                SabianaSimpleSensor(
                    coordinator, gid, addr, name,
                    key=key,
                    value=vent.get(key),
                    enabled_default=False,
                    diagnostic=True,
                )
            )

    async_add_entities(entities)


class SabianaSimpleSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: SabianaCoordinator,
        gid: Any,
        addr: Any,
        unit_name: str,
        *,
        key: str,
        value: Any,
        enabled_default: bool = True,
        diagnostic: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._gid = gid
        self._addr = addr
        self._key = key
        self._unit_name = unit_name
        self._attr_unique_id = f"sabiana:{gid}:{addr}:{key}"
        self._attr_name = f"Sabiana {unit_name} {SENSORS_MAIN.get(key, key)}"
        self._value = value
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sabiana:{gid}:{addr}")},
            manufacturer="Sabiana",
            name=f"Sabiana {unit_name}",
        )
        self._attr_entity_registry_enabled_default = enabled_default

        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

        if key in (
            "t1", "t3", "t2",
            "setPointHeating", "setPointCooling",
            "setPointHeatingMin", "setPointHeatingMax",
            "setPointCoolingMin", "setPointCoolingMax",
            "setPointAutoMode",
        ):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT

        if key == "lastUpdate":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    def _current(self) -> Dict[str, Any] | None:
        for u in self.coordinator.data.get("units", []):
            if u.get("groupId") == self._gid and u.get("address") == self._addr:
                return u
        return None

    @property
    def native_value(self):
        u = self._current()
        if not u:
            return None
        if self._key == "name":
            return u.get("name")
        if self._key == "address":
            return u.get("address")
        if self._key == "lastUpdate":
            raw = u.get("lastUpdate")
            if raw is None:
                return None
            try:
                return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
            except Exception:
                return None
        vent = u.get("ventUnit") or {}
        if self._key == "power":
            return "on" if vent.get("on") else "off"
        if self._key == "request":
            return "on" if vent.get("requestThermo") else "off"
        if self._key == "activeAlarms":
            al = vent.get("activeAlarms") or []
            return ", ".join(map(str, al)) if al else ""
        return vent.get(self._key)
