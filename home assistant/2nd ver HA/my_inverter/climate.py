# custom_components/my_inverter/climate.py
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_DEVICE_NAME


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up the HVAC climate entity."""
    device_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = device_data["coordinator"]
    async_add_entities([HVACClimate(coordinator, entry)])


class HVACClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.AUTO,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = ["auto", "low", "medium", "high"]
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_name = f"{entry.data[CONF_DEVICE_NAME]} HVAC"
        self._attr_unique_id = f"{entry.entry_id}_hvac"

    @property
    def hvac_mode(self) -> str:
        return self.coordinator.data.get("hvac_mode", "off")

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.get("target_temperature")

    @property
    def fan_mode(self) -> str | None:
        return self.coordinator.data.get("fan_mode", "auto")

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.get("current_temperature")

   

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        # Send the command to your device
        self.hass.data[DOMAIN][self.entry.entry_id]["commands"].append(
            f"SET_MODE_{hvac_mode.upper()}"
        )

        # IMPORTANT: Update the coordinator data so HA knows the state really changed
        self.coordinator.data["hvac_mode"] = hvac_mode.lower()  # or .upper(), match what you store

        # Update the entity state so the UI updates instantly
        self.async_write_ha_state()

        # Ask coordinator to refresh (so real device state comes back)
        self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get("temperature")) is not None:
            self.hass.data[DOMAIN][self.entry.entry_id]["commands"].append(f"SET_TEMP_{int(temp)}")
            self.coordinator.data["target_temperature"] = float(temp)  # ← add this line
            self.async_write_ha_state()
            self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self.hass.data[DOMAIN][self.entry.entry_id]["commands"].append(f"SET_FAN_{fan_mode.upper()}")
        self.coordinator.data["fan_mode"] = fan_mode  # ← add this line
        self.async_write_ha_state()
        self.coordinator.async_request_refresh()

