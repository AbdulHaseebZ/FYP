# custom_components/my_inverter/profile_manager.py
import json
import os
import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PROFILE_FILE = "my_inverter_profile.json"

def get_profile_path(hass: HomeAssistant) -> str:
    """Get the path to the profile JSON file in the HA config directory."""
    return hass.config.path(PROFILE_FILE)

def load_profile(hass: HomeAssistant) -> dict | None:
    """Load the profile from disk, return None if it doesn't exist."""
    path = get_profile_path(hass)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        _LOGGER.error("Failed to load user profile: %s", e)
        return None

def save_profile(hass: HomeAssistant, data: dict) -> bool:
    """Save the profile data to disk."""
    path = get_profile_path(hass)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        _LOGGER.error("Failed to save user profile: %s", e)
        return False

def create_initial_profile(hass: HomeAssistant, user_input: dict, office_hours: dict = None) -> None:
    """Create the base JSON structure and save it."""
    profile = {
        "setting": user_input["setting"].lower(),
        "pv_capacity_kw": float(user_input["pv_capacity_kw"]),
        "battery_capacity_kwh": float(user_input["battery_capacity_kwh"]),
        "devices": [],
        "office_hours": office_hours,
        "comfort_priority": user_input["comfort_priority"].lower()
    }
    save_profile(hass, profile)
def add_device_to_profile(hass: HomeAssistant, device_info: dict) -> None:
    """Add a new device to the profile JSON, or update it if it exists."""
    profile = load_profile(hass)
    if not profile:
        return

    # Check if device already exists (by name) to avoid duplicates
    existing_devices = profile.get("devices", [])
    for i, dev in enumerate(existing_devices):
        if dev["name"] == device_info["name"]:
            existing_devices[i] = device_info
            break
    else:
        existing_devices.append(device_info)

    profile["devices"] = existing_devices
    save_profile(hass, profile)

def get_existing_locations(hass: HomeAssistant) -> list[str]:
    """Get a unique list of locations already in the JSON."""
    profile = load_profile(hass)
    if not profile:
        return []
    locations = {d.get("location") for d in profile.get("devices", []) if d.get("location")}
    return sorted(list(locations))

def remove_device_from_profile(hass: HomeAssistant, device_name: str) -> None:
    """Remove a device from the profile JSON by its name."""
    profile = load_profile(hass)
    if not profile:
        return

    existing_devices = profile.get("devices", [])
    # Rebuild the list excluding the device with the matching name
    new_devices = [dev for dev in existing_devices if dev["name"] != device_name]

    if len(new_devices) != len(existing_devices):
        profile["devices"] = new_devices
        save_profile(hass, profile)
        _LOGGER.info("Removed device '%s' from JSON profile", device_name)