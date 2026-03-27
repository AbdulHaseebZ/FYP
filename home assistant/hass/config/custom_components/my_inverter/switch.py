# custom_components/my_inverter/switch.py
from __future__ import annotations

from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_DEVICE_NAME, CONF_DEVICE_TYPE

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Switch entity for Switch and Shiftable Load devices."""
    device_type = entry.data.get(CONF_DEVICE_TYPE)
    
    # Allow both generic switches and shiftable loads (EV chargers, etc)
    if device_type not in ["Switch", "Shiftable Load"]:
        return

    device_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = device_data["coordinator"]
    async_add_entities([GenericSwitch(coordinator, entry)])

class GenericSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self.entry = entry
        device_name = entry.data[CONF_DEVICE_NAME]

        self._attr_name = None # Inherits device name
        self._attr_unique_id = f"{entry.entry_id}_switch"

        # --- DYNAMIC ICON LOGIC ---
        name_lower = device_name.lower()
        if "wash" in name_lower:
            self._attr_icon = "mdi:washing-machine"
        elif "ev" in name_lower or "charger" in name_lower:
            self._attr_icon = "mdi:ev-station"
        elif "dish" in name_lower:
            self._attr_icon = "mdi:dishwasher"
        else:
            self._attr_icon = "mdi:toggle-switch"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="ESP32",
            model=entry.data.get(CONF_DEVICE_TYPE, "Switch"),
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        state = self.coordinator.data.get("switch_state")
        return state == "on" if state is not None else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.hass.data[DOMAIN][self.entry.entry_id]["commands"].append("SWITCH_ON")
        # Optimistic update
        self.coordinator.data["switch_state"] = "on"
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.hass.data[DOMAIN][self.entry.entry_id]["commands"].append("SWITCH_OFF")
        # Optimistic update
        self.coordinator.data["switch_state"] = "off"
        self.async_write_ha_state()