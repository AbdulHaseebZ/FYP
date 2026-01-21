# custom_components/my_inverter/__init__.py
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components import http
import aiohttp  # Added for second POST

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_HVAC_MODE,
    CONF_TARGET_TEMPERATURE,
    CONF_FAN_MODE,
    CONF_CURRENT_TEMPERATURE,
)
#comment
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up my_inverter from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = InverterCoordinator(hass, entry)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "commands": [],
    }

    # Per-device HTTP endpoints (supports unlimited devices)
    hass.http.register_view(InverterStateView(entry.entry_id))
    hass.http.register_view(InverterCommandsView(entry.entry_id))

    # Load the correct platform(s)
    platforms = []
    device_type = entry.data[CONF_DEVICE_TYPE]
    
    if device_type == "Inverter":
        platforms.append("sensor")
    elif device_type in ["HVAC", "IR_AC"]:  # Both use climate platform
        platforms.append("climate")
    elif device_type == "Switch":
        platforms.append("switch")

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # ─── Send real entry_id to device after entry creation ───
    device_ip = entry.data.get("device_ip")
    if device_ip:
        url = f"http://{device_ip}/api/update_entry_id"
        payload = {
            "real_entry_id": entry.entry_id,
            "api_key": entry.data[CONF_API_KEY]  # For auth on ESP side
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        _LOGGER.info("Successfully sent real entry_id %s to device %s", entry.entry_id, device_ip)
                    else:
                        _LOGGER.warning("Device responded with status %d for real entry_id update", resp.status)
        except Exception as e:
            _LOGGER.error("Failed to send real entry_id to device %s: %s", device_ip, e)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device_type = entry.data[CONF_DEVICE_TYPE]
    
    platforms = {
        "Inverter": ["sensor"],
        "HVAC": ["climate"],
        "IR_AC": ["climate"],
        "Switch": ["switch"],
    }.get(device_type, [])

    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


class InverterCoordinator(DataUpdateCoordinator):
    """Hold all data received from the ESP."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.entry = entry
        self.data: dict[str, Any] = {
            CONF_HVAC_MODE: "off",
            CONF_TARGET_TEMPERATURE: 25.0,
            CONF_FAN_MODE: "auto",
            CONF_CURRENT_TEMPERATURE: None,
            "switch_state": "off",
        }

    def update_data(self, incoming: dict[str, Any]) -> None:
        """Merge incoming data from ESP."""
        for key, value in incoming.items():
            self.data[key] = value
        self.async_set_updated_data(self.data)


# POST – ESP pushes state → Home Assistant
class InverterStateView(http.HomeAssistantView):
    requires_auth = False

    def __init__(self, entry_id: str):
        self.entry_id = entry_id
        self.url = f"/api/my_inverter/{entry_id}/state"
        self.name = f"api:my_inverter:{entry_id}:state"

    async def post(self, request):
        api_key = (
            request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            or request.headers.get("X-API-Key")
            or request.query.get("api_key")
        )
        entry = request.app["hass"].config_entries.async_get_entry(self.entry_id)
        if not entry or entry.data.get(CONF_API_KEY) != api_key:
            return self.json_message("Unauthorized", status_code=401)

        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", status_code=400)

        device_data = request.app["hass"].data[DOMAIN][self.entry_id]
        device_data["coordinator"].update_data(data)
        return self.json({"status": "ok"})


# GET – ESP polls for commands
class InverterCommandsView(http.HomeAssistantView):
    requires_auth = False

    def __init__(self, entry_id: str):
        self.entry_id = entry_id
        self.url = f"/api/my_inverter/{entry_id}/commands"
        self.name = f"api:my_inverter:{entry_id}:commands"

    async def get(self, request):
        api_key = (
            request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            or request.headers.get("X-API-Key")
            or request.query.get("api_key")
        )
        entry = request.app["hass"].config_entries.async_get_entry(self.entry_id)
        if not entry or entry.data.get(CONF_API_KEY) != api_key:
            return self.json_message("Unauthorized", status_code=401)

        device_data = request.app["hass"].data[DOMAIN][self.entry_id]
        commands = device_data["commands"][:]
        device_data["commands"].clear()

        if commands:
            _LOGGER.debug("Sent to %s → %s", entry.title, commands)

        return self.json({"commands": commands})