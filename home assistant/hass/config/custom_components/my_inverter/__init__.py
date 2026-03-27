import logging
from typing import Any
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components import http, frontend
from homeassistant.components.http import StaticPathConfig

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
from .ai_service import AIService
# Import the profile manager for JSON synchronization
from .profile_manager import (
    load_profile,
    remove_device_from_profile
)

_LOGGER = logging.getLogger(__name__)

# Track if panel is registered globally across entries
PANEL_REGISTERED = False

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the my_inverter component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up my_inverter from a config entry."""
    global PANEL_REGISTERED
    
    hass.data.setdefault(DOMAIN, {})

    coordinator = InverterCoordinator(hass, entry)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "commands": [],
    }

    # Per-device HTTP endpoints for local push/poll
    hass.http.register_view(InverterStateView(entry.entry_id))
    hass.http.register_view(InverterCommandsView(entry.entry_id))

    # Determine which platforms to load based on device type
    platforms = []
    device_type = entry.data[CONF_DEVICE_TYPE]
    
    if device_type == "Inverter":
        platforms.append("sensor")
    elif device_type in ["HVAC", "IR_AC"]:
        platforms.append("climate")
    elif device_type == "Switch":
        platforms.append("switch")
    elif device_type == "Shiftable Load":
        # Shiftable loads are currently treated as switches in HA
        platforms.append("switch")
    elif device_type == "Occupancy Sensor":
        platforms.append("binary_sensor")

    if platforms:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Register the AI Insights panel (singleton logic)
    if not PANEL_REGISTERED:
        await _register_panel(hass)
        
        ai_service = AIService(hass)
        await ai_service.async_setup()
        hass.data[DOMAIN]["ai_service"] = ai_service
        
        PANEL_REGISTERED = True
        _LOGGER.info("AI Insights panel and AI service registered")

    # Inform the physical device of its Permanent Entry ID
    device_ip = entry.data.get("device_ip")
    if device_ip:
        url = f"http://{device_ip}/api/update_entry_id"
        payload = {
            "real_entry_id": entry.entry_id,
            "api_key": entry.data[CONF_API_KEY]
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        _LOGGER.info("Synced entry_id %s to device at %s", entry.entry_id, device_ip)
        except Exception as e:
            _LOGGER.debug("Could not sync entry_id to device (likely offline): %s", e)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up JSON profile."""
    global PANEL_REGISTERED
    
    device_type = entry.data[CONF_DEVICE_TYPE]
    device_name = entry.data[CONF_DEVICE_NAME]
    
    # Map platforms for unloading
    platforms = {
        "Inverter": ["sensor"],
        "HVAC": ["climate"],
        "IR_AC": ["climate"],
        "Switch": ["switch"],
        "Shiftable Load": ["switch"],
        "Occupancy Sensor": ["binary_sensor"],
    }.get(device_type, [])

    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    
    if unloaded:
        # 1. REMOVE FROM JSON PROFILE
        # We do this in the executor because it's a file write operation
        await hass.async_add_executor_job(
            remove_device_from_profile, hass, device_name
        )

        # 2. Clean up memory
        hass.data[DOMAIN].pop(entry.entry_id, None)
        
        # 3. Handle Sidebar Panel Cleanup
        remaining_entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        
        if not remaining_entries and PANEL_REGISTERED:
            ai_service = hass.data[DOMAIN].get("ai_service")
            if ai_service:
                await ai_service.async_unload()
                hass.data[DOMAIN].pop("ai_service", None)
            
            await _unregister_panel(hass)
            PANEL_REGISTERED = False
            _LOGGER.info("Removed AI Sidebar (no devices remaining)")
    
    return unloaded

async def _register_panel(hass: HomeAssistant) -> None:
    """Register the AI Insights custom panel."""
    js_path = hass.config.path(f"custom_components/{DOMAIN}/frontend/ai_summary_panel.js")

    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path=f"/api/{DOMAIN}/ai_summary_panel.js",
            path=js_path,
            cache_headers=True,
        )
    ])

    hass.http.register_view(AIDataView())

    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Inverter AI Insights",
        sidebar_icon="mdi:robot",
        frontend_url_path="my_inverter_ai",
        config={
            "_panel_custom": {
                "name": "my-inverter-ai-panel",
                "module_url": f"/api/{DOMAIN}/ai_summary_panel.js",
            }
        },
        require_admin=False,
    )

async def _unregister_panel(hass: HomeAssistant) -> None:
    """Unregister the AI Insights panel."""
    frontend.async_remove_panel(hass, "my_inverter_ai")

class InverterCoordinator(DataUpdateCoordinator):
    """Data coordinator for ESP32 devices."""
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.entry = entry
        self.data: dict[str, Any] = {
            CONF_HVAC_MODE: "off",
            CONF_TARGET_TEMPERATURE: 25.0,
            CONF_FAN_MODE: "auto",
            "switch_state": "off",
        }

    def update_data(self, incoming: dict[str, Any]) -> None:
        """Merge incoming data and notify HA."""
        self.data.update(incoming)
        self.async_set_updated_data(self.data)

class InverterStateView(http.HomeAssistantView):
    """Endpoint for ESP32 to push state."""
    requires_auth = False

    def __init__(self, entry_id: str):
        self.entry_id = entry_id
        self.url = f"/api/my_inverter/{entry_id}/state"
        self.name = f"api:my_inverter:{entry_id}:state"

    async def post(self, request):
        api_key = request.headers.get("X-API-Key") or request.query.get("api_key")
        entry = request.app["hass"].config_entries.async_get_entry(self.entry_id)
        
        if not entry or entry.data.get(CONF_API_KEY) != api_key:
            return self.json_message("Unauthorized", status_code=401)

        data = await request.json()
        request.app["hass"].data[DOMAIN][self.entry_id]["coordinator"].update_data(data)
        return self.json({"status": "ok"})

class InverterCommandsView(http.HomeAssistantView):
    """Endpoint for ESP32 to poll for commands."""
    requires_auth = False

    def __init__(self, entry_id: str):
        self.entry_id = entry_id
        self.url = f"/api/my_inverter/{entry_id}/commands"
        self.name = f"api:my_inverter:{entry_id}:commands"

    async def get(self, request):
        api_key = request.headers.get("X-API-Key") or request.query.get("api_key")
        entry = request.app["hass"].config_entries.async_get_entry(self.entry_id)
        
        if not entry or entry.data.get(CONF_API_KEY) != api_key:
            return self.json_message("Unauthorized", status_code=401)

        device_data = request.app["hass"].data[DOMAIN][self.entry_id]
        commands = device_data["commands"][:]
        device_data["commands"].clear()
        return self.json({"commands": commands})

class AIDataView(http.HomeAssistantView):
    """Endpoint for the Sidebar to fetch AI data."""
    url = "/api/my_inverter/ai_data"
    name = "api:my_inverter:ai_data"
    requires_auth = True

    async def get(self, request):
        from .ai_service import AI_SUMMARY_DATA
        return self.json(AI_SUMMARY_DATA)