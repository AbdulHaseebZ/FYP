#config_flow.py
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from .const import DOMAIN, CONF_API_KEY, CONF_DEVICE_NAME, CONF_DEVICE_TYPE

_LOGGER = logging.getLogger(__name__)

class ESP32InverterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            # Device name
            device_name = user_input[CONF_DEVICE_NAME].strip()
            if not device_name:
                errors["base"] = "device_name_required"
            elif len(device_name) > 20:
                errors["base"] = "device_name_too_long"

            # API key (required)
            api_key = user_input[CONF_API_KEY].strip()
            if not api_key:
                errors["base"] = "api_key_required"
            elif len(api_key) < 4:
                errors["base"] = "api_key_too_short"

            if not errors:
                await self.async_set_unique_id(api_key)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"ESP32: {device_name} ({user_input[CONF_DEVICE_TYPE]})",
                    data=user_input
                )

        data_schema = vol.Schema({
            vol.Required(CONF_DEVICE_NAME): str,
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_DEVICE_TYPE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["Inverter", "HVAC", "Switch"],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )