# custom_components/my_inverter/config_flow.py
import logging
import asyncio
import voluptuous as vol
import aiohttp
import socket

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_API_KEY, CONF_DEVICE_NAME, CONF_DEVICE_TYPE
from .device_scanner import DeviceScanner

# Import the profile manager functions
from .profile_manager import (
    load_profile, 
    create_initial_profile, 
    get_existing_locations, 
    add_device_to_profile
)

_LOGGER = logging.getLogger(__name__)

# Define the updated list of supported device types
DEVICE_TYPES = [
    "Inverter", 
    "HVAC", 
    "IR_AC", 
    "Switch", 
    "Occupancy Sensor", 
    "Shiftable Load"
]

class ESP32InverterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for ESP32 Inverter integration."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_devices = []
        self.selected_device = None
        self.profile_data = None  # Temporarily holds profile/device data between steps

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Check if profile exists. If not, create it. Otherwise, go to device add menu."""
        existing_profile = await self.hass.async_add_executor_job(load_profile, self.hass)
        
        if existing_profile is None:
            return await self.async_step_system_profile()
            
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"]
        )

    async def async_step_system_profile(self, user_input=None) -> FlowResult:
        """Prompt user for the initial system profile."""
        errors = {}
        if user_input is not None:
            self.profile_data = user_input
            if user_input["setting"] == "commercial":
                return await self.async_step_commercial_hours()
            
            await self.hass.async_add_executor_job(
                create_initial_profile, self.hass, self.profile_data, None
            )
            return await self.async_step_user()

        data_schema = vol.Schema({
            vol.Required("setting", default="residential"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "residential", "label": "Residential"},
                        {"value": "commercial", "label": "Commercial"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("comfort_priority", default="balanced"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "low", "label": "Low"},
                        {"value": "balanced", "label": "Balanced"},
                        {"value": "high", "label": "High"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required("pv_capacity_kw", default=0.0): vol.All(vol.Coerce(float), vol.Range(min=0.0)),
            vol.Required("battery_capacity_kwh", default=0.0): vol.All(vol.Coerce(float), vol.Range(min=0.0)),
        })

        return self.async_show_form(step_id="system_profile", data_schema=data_schema, errors=errors)

    async def async_step_commercial_hours(self, user_input=None) -> FlowResult:
        """Ask for start and end hours if Commercial is selected."""
        if user_input is not None:
            office_hours = {"start": user_input["start_hour"], "end": user_input["end_hour"]}
            await self.hass.async_add_executor_job(
                create_initial_profile, self.hass, self.profile_data, office_hours
            )
            return await self.async_step_user()

        return self.async_show_form(
            step_id="commercial_hours",
            data_schema=vol.Schema({
                vol.Required("start_hour", default="09:00"): selector.TimeSelector(),
                vol.Required("end_hour", default="17:00"): selector.TimeSelector(),
            })
        )

    async def async_step_discover(self, user_input=None) -> FlowResult:
        """Discover ESP32 devices on the local network."""
        if user_input is not None:
            device_id = user_input["device"]
            self.selected_device = next((d for d in self.discovered_devices if d["id"] == device_id), None)
            if self.selected_device:
                return await self.async_step_configure()
            return self.async_abort(reason="device_not_found")

        scanner = DeviceScanner(self.hass)
        try:
            self.discovered_devices = await scanner.scan_devices(timeout=8)
        except Exception:
            return self.async_abort(reason="scan_failed")

        if not self.discovered_devices:
            return self.async_show_form(step_id="discover", data_schema=vol.Schema({}), errors={"base": "no_devices_found"})

        device_options = [{"value": d["id"], "label": f"{d['name']} ({d['ip']})"} for d in self.discovered_devices]
        return self.async_show_form(
            step_id="discover", 
            data_schema=vol.Schema({
                vol.Required("device"): selector.SelectSelector(selector.SelectSelectorConfig(options=device_options, mode=selector.SelectSelectorMode.DROPDOWN))
            })
        )

    async def async_step_manual(self, user_input=None) -> FlowResult:
        """Manual configuration entry."""
        if user_input is not None:
            self.profile_data = user_input
            
            # FIXED ROUTING: 
            # If it's a Shiftable Load, we MUST go to the location step first, 
            # then the location step will route to the shiftable_type step.
            if user_input[CONF_DEVICE_TYPE] == "Inverter":
                return await self.async_finish_device_setup()
            
            # HVAC, IR_AC, Switch, Occupancy Sensor, and Shiftable Load all need location
            return await self.async_step_location()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_NAME): str,
                vol.Required(CONF_API_KEY): str,
                vol.Required("device_ip"): str,
                vol.Required(CONF_DEVICE_TYPE, default="Inverter"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=DEVICE_TYPES, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
            })
        )

    async def async_step_configure(self, user_input=None) -> FlowResult:
        """Configure the discovered device."""
        if user_input is not None:
            self.profile_data = user_input
            # Merge IP from discovery
            self.profile_data["device_ip"] = self.selected_device["ip"]
            
            if user_input[CONF_DEVICE_TYPE] in ["Inverter", "Shiftable Load"]:
                if user_input[CONF_DEVICE_TYPE] == "Shiftable Load":
                    return await self.async_step_shiftable_type()
                return await self.async_finish_device_setup()
            return await self.async_step_location()

        data_schema = vol.Schema({
            vol.Required(CONF_DEVICE_NAME, default=self.selected_device.get("name", "")): str,
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_DEVICE_TYPE, default="Inverter"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=DEVICE_TYPES, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
        })
        return self.async_show_form(step_id="configure", data_schema=data_schema)

    async def async_step_location(self, user_input=None) -> FlowResult:
        """Step to select or enter a location."""
        if user_input is not None:
            # Use new location text if provided, else use dropdown selection
            loc = user_input.get("new_location") or user_input.get("existing_location")
            self.profile_data["location"] = loc
            
            if self.profile_data[CONF_DEVICE_TYPE] == "Shiftable Load":
                return await self.async_step_shiftable_type()
            return await self.async_finish_device_setup()

        # Get unique locations already in JSON
        existing_locs = await self.hass.async_add_executor_job(get_existing_locations, self.hass)
        
        data_schema = vol.Schema({
            vol.Optional("existing_location"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=existing_locs, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            vol.Optional("new_location"): str,
        })
        return self.async_show_form(step_id="location", data_schema=data_schema)

    async def async_step_shiftable_type(self, user_input=None) -> FlowResult:
        """Question specifically for Shiftable Loads."""
        if user_input is not None:
            self.profile_data["subtype"] = user_input["subtype"]
            return await self.async_finish_device_setup()

        return self.async_show_form(
            step_id="shiftable_type",
            data_schema=vol.Schema({
                vol.Required("subtype"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["Washing_Machine", "EV_Charger"], mode=selector.SelectSelectorMode.DROPDOWN)
                )
            })
        )

    async def async_finish_device_setup(self) -> FlowResult:
        """Send config to hardware, update JSON, and create HA entry."""
        device_name = self.profile_data[CONF_DEVICE_NAME]
        api_key = self.profile_data[CONF_API_KEY]
        device_type = self.profile_data[CONF_DEVICE_TYPE]
        device_ip = self.profile_data.get("device_ip")

        # Map type for JSON requirements
        final_type = device_type
        if device_type == "Shiftable Load":
            final_type = self.profile_data.get("subtype", "Plug")
        elif device_type == "Occupancy Sensor":
            final_type = "Occupancy_Sensor"

        # Push to physical device
        success = await self._push_config_to_device(device_name, api_key, final_type, device_ip)
        
        if not success:
            _LOGGER.warning("Could not connect to ESP32 at %s, but proceeding with setup.", device_ip)
           # return self.async_abort(reason="cannot_connect")

        # Update the user_profile.json
        json_entry = {
            "name": device_name,
            "type": final_type,
            "location": self.profile_data.get("location")  # null if not provided
        }
        await self.hass.async_add_executor_job(add_device_to_profile, self.hass, json_entry)

        return self.async_create_entry(
            title=f"ESP32: {device_name}",
            data=self.profile_data
        )

    async def _push_config_to_device(self, device_name, api_key, device_type, device_ip) -> bool:
        """Send JSON config to the ESP32."""
        if not device_ip: return False
        url = f"http://{device_ip}/api/config"
        
        # Determine host IP for callback
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            host_ip = s.getsockname()[0]
        except Exception:
            host_ip = "127.0.0.1"
        finally:
            s.close()

        payload = {
            "api_key": api_key,
            "device_name": device_name,
            "device_type": device_type,
            "ha_url": f"http://{host_ip}:8123"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=5) as resp:
                    return resp.status == 200
        except Exception:
            return False