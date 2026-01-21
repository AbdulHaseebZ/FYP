# custom_components/my_inverter/switch.py
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_DEVICE_NAME, CONF_DEVICE_TYPE  # ← FIXED: import CONF_DEVICE_TYPE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Switch entity only for Switch-type devices."""
    # ← FIXED: use the constant, not the string
    if entry.data.get(CONF_DEVICE_TYPE) != "Switch":
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([GenericSwitch(coordinator, entry)])


class GenericSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:toggle-switch"

    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self.entry = entry

        self._attr_name = entry.data[CONF_DEVICE_NAME]
        self._attr_unique_id = f"{entry.entry_id}_switch"

        # Unique identifier per device type – this prevents collision with HVAC/Inverter
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_switch")},  # ← FIXED: unique ID
            name=entry.data[CONF_DEVICE_NAME],
            manufacturer="ESP32",
            model="Switch",
            sw_version="0.1.0",
        )

    @property
    def is_on(self) -> bool:
        state = self.coordinator.data.get("switch_state")
        return state == "on" if state is not None else False


    async def async_turn_on(self, **kwargs: Any) -> None:
        self.hass.data[DOMAIN][self.entry.entry_id]["commands"].append("SWITCH_ON")
        self._attr_is_on = True
        self.async_write_ha_state()
        self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.hass.data[DOMAIN][self.entry.entry_id]["commands"].append("SWITCH_OFF")
        self._attr_is_on = False
        self.async_write_ha_state()
        self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        if "switch_state" in self.coordinator.data:
            self.async_write_ha_state()