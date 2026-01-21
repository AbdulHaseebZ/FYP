#sensor.py
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_DEVICE_NAME

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    device_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = device_data["coordinator"]
    device_name = entry.data[CONF_DEVICE_NAME].lower().replace(" ", "_")

    sensors = [
        InverterSensor(coordinator, entry, "grid_voltage_a", "Grid Phase Voltage A", "V", "mdi:flash", device_name),
        InverterSensor(coordinator, entry, "grid_voltage_b", "Grid Phase Voltage B", "V", "mdi:flash", device_name),
        InverterSensor(coordinator, entry, "grid_voltage_c", "Grid Phase Voltage C", "V", "mdi:flash", device_name),
        InverterSensor(coordinator, entry, "total_pv_power", "Total PV Power", "W", "mdi:solar-power", device_name),
        InverterSensor(coordinator, entry, "pv1_power", "PV1 Power", "W", "mdi:solar-power", device_name),
        InverterSensor(coordinator, entry, "pv1_voltage", "PV1 Voltage", "V", "mdi:solar-panel", device_name),
        InverterSensor(coordinator, entry, "today_load_consumption", "Today Load Consumption", "kWh", "mdi:lightning-bolt", device_name),
        InverterSensor(coordinator, entry, "total_load_consumption", "Total Load Consumption", "kWh", "mdi:lightning-bolt", device_name),
    ]
    async_add_entities(sensors)


class InverterSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, name, unit, icon, device_name):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"{entry.data[CONF_DEVICE_NAME]} {name}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}-{device_name}-{key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)