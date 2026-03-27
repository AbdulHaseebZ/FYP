# custom_components/my_inverter/tag_engine.py
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class TagEngine:
    def __init__(self):
        self.grid_outage_previous = False
        self.outage_start_time = None
        self.occupancy_states = {} 
        self.prev_humidity = None

    def get_active_tags(self, hass, structured_data: dict, profile: dict) -> list[str]:
        tags = []
        now = datetime.now()
        profile_devices = profile.get("devices", [])
        
        # 1. Hardware Availability
        device_types = [d.get("type") for d in profile_devices]
        if any(t in ["HVAC", "IR_AC"] for t in device_types):
            tags.append("AC_GENERAL")
        if "EV_Charger" in device_types:
            tags.append("EV_GENERAL")
        if "Washing_Machine" in device_types:
            tags.append("WASHING_MACHINE_GENERAL")

        # 2. Inverter Lookup
        inverter_device_info = next((d for d in profile_devices if d.get("type") == "Inverter"), None)
        inv_name = inverter_device_info.get("name") if inverter_device_info else None
        inv_data = structured_data.get(inv_name, {}) if inv_name else {}

        if inv_data:
            try:
                pv = float(inv_data.get("total_pv_power", 0))
                load = float(inv_data.get("total_load_power", 0))
                soc = float(inv_data.get("battery_soc", 0))
                v_a = float(inv_data.get("grid_voltage_a", 0))
                v_b = float(inv_data.get("grid_voltage_b", 0))
                v_c = float(inv_data.get("grid_voltage_c", 0))

                tags.append("SOLAR_SURPLUS" if pv > load else "SOLAR_DEFICIT")
                if pv > load and soc > 80: tags.append("SOLAR_WASTE_RISK")

                if soc < 55: tags.append("BATTERY_CRITICAL")
                elif soc > 80: tags.append("BATTERY_FULL")
                else: tags.append("BATTERY_NORMAL")

                grid_outage = (v_a < 210 or v_b < 210 or v_c < 210)
                if grid_outage:
                    tags.append("GRID_OUTAGE")
                    if not self.outage_start_time: self.outage_start_time = now
                    elif (now - self.outage_start_time).total_seconds() > 7200:
                        tags.append("LOAD_SHEDDING_LONG")
                else:
                    if self.grid_outage_previous: tags.append("GRID_RESTORED")
                    tags.append("GRID_AVAILABLE")
                    self.outage_start_time = None
                self.grid_outage_previous = grid_outage
            except: pass

        # ---------------------------------------------------------
        # 3. SETTINGS & HOURS (FIXED LOGIC & FORMAT)
        # ---------------------------------------------------------
        user_setting = profile.get("setting", "residential").lower()
        tags.append("SETTING_COMMERCIAL" if user_setting == "commercial" else "SETTING_RESIDENTIAL")

        office = profile.get("office_hours")
        if office:
            try:
                # We use [:5] to take only the "10:00" part of "10:00:00"
                start_str = office["start"][:5]
                end_str = office["end"][:5]
                
                start_time = datetime.strptime(start_str, "%H:%M").time()
                end_time = datetime.strptime(end_str, "%H:%M").time()
                current_time = now.time()

                if start_time <= current_time <= end_time:
                    tags.append("WORKING_HOURS")
                else:
                    # At 6:20 PM (18:20), it will now correctly land here
                    tags.append("NON_WORKING_HOURS")
            except Exception as e:
                _LOGGER.error(f"Office Hours Error: {e}")

        # 4. Weather - Using Template Sensors
        temp_sensor = hass.states.get("sensor.outside_temperature")
        hum_sensor = hass.states.get("sensor.outside_humidity")
        cond_sensor = hass.states.get("sensor.outside_condition")

        if temp_sensor and hum_sensor:
            try:
                cond = cond_sensor.state if cond_sensor else ""
                temp = float(temp_sensor.state)
                hum = float(hum_sensor.state)
                is_summer = 4 <= now.month <= 9
                
                if cond.lower() in ["rainy", "pouring", "lightning-rainy", "rain", "showers"]:
                    tags.append("RAINING_OUTSIDE_SUMMER" if is_summer else "RAINING_OUTSIDE_WINTER")
                
                if temp < 30: 
                    tags.append("COOL_WEATHER_OUTSIDE_SUMMER" if is_summer else "COOL_WEATHER_OUTSIDE_WINTER")
                elif temp > 40: 
                    tags.append("VERY_HOT_OUTSIDE")
                
                if hum > 70: 
                    tags.append("HIGH_HUMIDITY")
                
                self.prev_humidity = hum
            except: pass

        # 5. OCCUPANCY LOGIC
        for name, data in structured_data.items():
            if "occupancy" in data:
                current_is_occupied = data["occupancy"] is True
                if name not in self.occupancy_states:
                    self.occupancy_states[name] = {"state": current_is_occupied, "since": now}
                
                if self.occupancy_states[name]["state"] != current_is_occupied:
                    self.occupancy_states[name] = {"state": current_is_occupied, "since": now}
                
                duration = (now - self.occupancy_states[name]["since"]).total_seconds()
                
                if current_is_occupied and duration > 60:
                    tags.append("ROOM_OCCUPIED")
                elif not current_is_occupied and duration > 120:
                    tags.append("ROOM_UNOCCUPIED")

        return list(set(tags))