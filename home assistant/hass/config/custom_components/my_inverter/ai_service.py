# custom_components/my_inverter/ai_service.py
"""AI service - Currently in DEBUG mode with filtered device data."""

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .tag_engine import TagEngine
from .profile_manager import load_profile

_LOGGER = logging.getLogger(__name__)

# Global storage for the sidebar panel
AI_SUMMARY_DATA = {
    "summary": "Initializing Debug Mode...",
    "timestamp": None,
    "error": None,
    "status": "initializing",
}

class AIService:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._update_interval = timedelta(seconds=10)
        self._remove_listener = None
        self.tag_engine = TagEngine()

    async def async_setup(self) -> None:
        _LOGGER.info("Setting up AI Service in DEBUG mode.")
        
        self.hass.services.async_register(
            DOMAIN,
            "refresh_ai_summary",
            self.async_refresh_summary,
        )
        
        await self.async_refresh_summary()
        
        self._remove_listener = async_track_time_interval(
            self.hass,
            self._periodic_update,
            self._update_interval,
        )

    async def async_unload(self) -> None:
        if self._remove_listener:
            self._remove_listener()
        self.hass.services.async_remove(DOMAIN, "refresh_ai_summary")

    async def _periodic_update(self, now=None):
        await self.async_refresh_summary()

    async def async_refresh_summary(self, call: ServiceCall = None) -> None:
        global AI_SUMMARY_DATA
        try:
            debug_text = await self._build_debug_prompt()
            AI_SUMMARY_DATA.update({
                "summary": debug_text,
                "timestamp": datetime.now().isoformat(),
                "error": None,
                "status": "success"
            })
        except Exception as e:
            _LOGGER.exception(f"Error generating debug text: {e}")
            AI_SUMMARY_DATA.update({
                "summary": f"❌ Error: {str(e)}",
                "status": "error",
                "timestamp": datetime.now().isoformat(),
            })

    async def _build_debug_prompt(self) -> str:
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return "No devices configured."

        # 1. Load Profile to get locations/names
        profile = await self.hass.async_add_executor_job(load_profile, self.hass)
        profile_devices = profile.get("devices", []) if profile else []

        # 2. Define schema-based filtering
        CLIMATE_KEYS = ["hvac_mode", "target_temperature", "fan_mode", "current_temperature"]
        VALID_KEYS = {
            "Inverter": ["grid_voltage_a", "grid_voltage_b", "grid_voltage_c", "total_pv_power", "total_load_power", "battery_soc"],
            "HVAC": CLIMATE_KEYS,
            "IR_AC": CLIMATE_KEYS,
            "Occupancy Sensor": ["occupancy"],
            "Switch": ["switch_state"],
            "Shiftable Load": ["switch_state"]
        }

        structured_data = {}
        device_summary_lines = []
        
        for entry in entries:
            entry_id = entry.entry_id
            conf_name = entry.data.get("device_name")
            dtype = entry.data.get("device_type", "Unknown")
            
            # Find the matching device in the profile for location
            device_info = next((d for d in profile_devices if d["name"] == conf_name), {})
            location = device_info.get("location") # Will be None for Inverter per your setup
            
            coordinator = self.hass.data[DOMAIN].get(entry_id, {}).get("coordinator")
            if coordinator and coordinator.data:
                # Format key: "Name (Location)" or just "Name" if Location is None
                loc_label = f" ({location})" if location else ""
                device_key = f"{conf_name}{loc_label}"
                
                # FILTERING LOGIC
                allowed_keys = VALID_KEYS.get(dtype, [])
                filtered_data = {k: v for k, v in coordinator.data.items() if k in allowed_keys}
                
                structured_data[device_key] = filtered_data
                device_summary_lines.append(f"• {device_key}")

        # 3. Generate Tags using the logic from the TagEngine
        # We now pass the WHOLE structured_data map to the engine
        active_tags_list = self.tag_engine.get_active_tags(self.hass, structured_data, profile)
        active_tags_string = "\n".join([f"✅ {tag}" for tag in active_tags_list])

        # 4. Format the UI Output
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        details = ""
        for dev_name, data in structured_data.items():
            if not data: continue
            details += f"\n[{dev_name}]\n"
            for k, v in data.items():
                details += f"  {k}: {v}\n"

        debug_prompt = f"""=== 🛠️ SYSTEM DEBUG MONITOR ===
Last Updated: {now_str}

[ CONFIGURED DEVICES ]
{chr(10).join(device_summary_lines)}

[ ACTIVE TAGS ]
{active_tags_string if active_tags_string else "No active tags"}

[ LIVE DEVICE STATES ]
{details}
================================="""
        return debug_prompt

def get_ai_service(hass: HomeAssistant) -> AIService:
    return hass.data[DOMAIN].get("ai_service")