# custom_components/my_inverter/config_flow.py
import logging
import asyncio
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import socket

from .const import DOMAIN, CONF_API_KEY, CONF_DEVICE_NAME, CONF_DEVICE_TYPE
from .device_scanner import DeviceScanner

_LOGGER = logging.getLogger(__name__)


class ESP32InverterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for ESP32 Inverter integration."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_devices = []
        self.selected_device = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step - choose between discovery or manual setup."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"]
        )

    async def async_step_discover(self, user_input=None) -> FlowResult:
        """Discover ESP32 devices on the local network."""
        if user_input is not None:
            # User selected a device from the dropdown
            device_id = user_input["device"]
            self.selected_device = next(
                (d for d in self.discovered_devices if d["id"] == device_id),
                None
            )

            if self.selected_device:
                return await self.async_step_configure()

            return self.async_abort(reason="device_not_found")

        # Perform network scan
        _LOGGER.info("Starting discovery of ESP32 devices...")
        scanner = DeviceScanner(self.hass)

        try:
            self.discovered_devices = await scanner.scan_devices(timeout=8)
        except Exception as e:
            _LOGGER.error("Error during device discovery", exc_info=True)
            return self.async_abort(reason="scan_failed")

        if not self.discovered_devices:
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({}),
                errors={"base": "no_devices_found"},
                description_placeholders={
                    "message": "No ESP32 devices were found on your network.\n"
                               "Make sure your devices are powered on and connected to the same Wi-Fi."
                }
            )

        # Build nice selection options
        device_options = []
        for dev in self.discovered_devices:
            status = "✓ Configured" if dev.get("configured", False) else "⚠ Not configured"
            label = f"{dev['name']} ({dev['type']}) - {dev['ip']} - {status}"
            device_options.append(
                selector.SelectOptionDict(
                    value=dev["id"],
                    label=label
                )
            )

        data_schema = vol.Schema({
            vol.Required("device"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=device_options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        })

        return self.async_show_form(
            step_id="discover",
            data_schema=data_schema,
            description_placeholders={"count": str(len(self.discovered_devices))}
        )

    async def async_step_configure(self, user_input=None) -> FlowResult:
        """Configure the selected discovered device."""
        errors = {}

        if user_input is not None:
            device_name = user_input[CONF_DEVICE_NAME].strip()
            api_key = user_input[CONF_API_KEY].strip()
            device_type = user_input[CONF_DEVICE_TYPE]

            # Basic validation
            if not device_name:
                errors["base"] = "device_name_required"
            elif len(device_name) > 20:
                errors["base"] = "device_name_too_long"
            elif not api_key:
                errors["base"] = "api_key_required"
            elif len(api_key) < 4:
                errors["base"] = "api_key_too_short"

            if not errors:
                # Create unique ID to prevent duplicates
                await self.async_set_unique_id(f"{self.selected_device['id']}_{api_key}")
                self._abort_if_unique_id_configured()

                # Try to push configuration to the actual device
                success = await self._push_config_to_device(
                    device_name, api_key, device_type
                )

                if success:
                    return self.async_create_entry(
                        title=f"ESP32: {device_name} ({device_type})",
                        data={
                            CONF_DEVICE_NAME: device_name,
                            CONF_API_KEY: api_key,
                            CONF_DEVICE_TYPE: device_type,
                            "device_id": self.selected_device["id"],
                            "device_ip": self.selected_device["ip"],  # Added for second push
                        }
                    )
                else:
                    errors["base"] = "cannot_connect"

        # Default values from discovered info
        default_name = self.selected_device.get("name", "ESP32 Device")
        default_type = self.selected_device.get("type", "Inverter")

        data_schema = vol.Schema({
            vol.Required(CONF_DEVICE_NAME, default=default_name): str,
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_DEVICE_TYPE, default=default_type): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["Inverter", "HVAC", "Switch", "IR_AC"],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        })

        return self.async_show_form(
            step_id="configure",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "device_id": self.selected_device["id"],
                "device_type": self.selected_device["type"],
                "device_ip": self.selected_device["ip"],
            }
        )

    async def async_step_manual(self, user_input=None) -> FlowResult:
        """Manual configuration (no auto-discovery)."""
        errors = {}

        if user_input is not None:
            device_name = user_input[CONF_DEVICE_NAME].strip()
            api_key = user_input[CONF_API_KEY].strip()
            device_ip = user_input["device_ip"].strip()  # Added

            if not device_name:
                errors["base"] = "device_name_required"
            elif len(device_name) > 20:
                errors["base"] = "device_name_too_long"
            elif not api_key:
                errors["base"] = "api_key_required"
            elif len(api_key) < 4:
                errors["base"] = "api_key_too_short"
            elif not device_ip:
                errors["base"] = "device_ip_required"

            if not errors:
                await self.async_set_unique_id(api_key)
                self._abort_if_unique_id_configured()

                # Optional: Push config even in manual (if IP provided)
                success = await self._push_config_to_device(
                    device_name, api_key, user_input[CONF_DEVICE_TYPE], device_ip
                )

                return self.async_create_entry(
                    title=f"ESP32: {device_name} ({user_input[CONF_DEVICE_TYPE]})",
                    data={
                        CONF_DEVICE_NAME: device_name,
                        CONF_API_KEY: api_key,
                        CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                        "device_ip": device_ip,  # Added
                    }
                )

        data_schema = vol.Schema({
            vol.Required(CONF_DEVICE_NAME): str,
            vol.Required(CONF_API_KEY): str,
            vol.Required("device_ip"): str,  # Added for manual
            vol.Required(CONF_DEVICE_TYPE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["Inverter", "HVAC", "Switch", "IR_AC"],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        })

        return self.async_show_form(
            step_id="manual",
            data_schema=data_schema,
            errors=errors,
        )

    async def _push_config_to_device(self, device_name: str, api_key: str, device_type: str, device_ip: str = None) -> bool:
        """Attempt to send configuration to the physical ESP32 device."""
        if not self.selected_device and not device_ip:
            return False

        device_ip = device_ip or self.selected_device['ip']
        url = f"http://{device_ip}/api/config"

        # Temporary entry_id
        temp_entry_id = "TEMP_ID_PLACEHOLDER"

        # Socket trick for real HA URL
        def _get_host_lan_ip() -> str:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                _LOGGER.info("Detected host LAN IP for ESP: %s", ip)
                return ip
            except Exception as e:
                _LOGGER.warning("Could not detect LAN IP automatically (%s), falling back to known value", e)
                return "10.255.0.145"
            finally:
                s.close()

        host_ip = _get_host_lan_ip()
        ha_url = f"http://{host_ip}:8123"

        payload = {
            "entry_id": temp_entry_id,
            "api_key": api_key,
            "device_name": device_name,
            "device_type": device_type,
            "device_model": self.selected_device.get("type", "") if self.selected_device else "",
            "ha_url": ha_url
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        _LOGGER.info("Successfully sent configuration to device at %s (HA URL: %s)", device_ip, ha_url)
                        return True
                    else:
                        _LOGGER.warning("Device responded with status %d", resp.status)
                        return False
        except Exception as e:
            _LOGGER.error("Failed to configure device at %s: %s", device_ip, e)
            return False