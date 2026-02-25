# custom_components/my_inverter/ai_service.py
"""AI service for communicating directly with Ollama - with real device data."""

import logging
from typing import Any
from datetime import datetime, timedelta
import aiohttp
import json

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Global storage for the latest result shown in the panel
AI_SUMMARY_DATA = {
    "summary": "Initializing AI service...",
    "timestamp": None,
    "error": None,
    "status": "initializing",
}


class AIService:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._update_interval = timedelta(minutes=1)
        self._remove_listener = None
        self._ollama_url = "http://10.255.0.48:11434/"     # ← change if needed
        self._ollama_model = "llama3.2:3b"              # ← your preferred model

    async def async_setup(self) -> None:
        _LOGGER.info("Setting up direct Ollama AI service")
        
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
        
        _LOGGER.info("AI service ready (direct Ollama)")

    async def async_unload(self) -> None:
        if self._remove_listener:
            self._remove_listener()
        self.hass.services.async_remove(DOMAIN, "refresh_ai_summary")
        _LOGGER.info("AI service unloaded")

    async def _periodic_update(self, now=None):
        await self.async_refresh_summary()

    async def async_refresh_summary(self, call: ServiceCall = None) -> None:
        global AI_SUMMARY_DATA
        AI_SUMMARY_DATA["status"] = "updating"
        _LOGGER.info("Generating new AI summary...")

        try:
            prompt = await self._build_prompt()
            
            if "No devices configured" in prompt:
                AI_SUMMARY_DATA.update({
                    "summary": prompt,
                    "timestamp": datetime.now().isoformat(),
                    "error": None,
                    "status": "warning"
                })
                return

            # ── Direct call to Ollama ───────────────────────────────────────
            url = f"{self._ollama_url}/api/generate"
            payload = {
                "model": self._ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=45) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise Exception(f"Ollama HTTP {resp.status}: {text}")

                    data = await resp.json()
                    response_text = data.get("response", "").strip()

                    if not response_text:
                        raise Exception("Empty response from Ollama")

                    AI_SUMMARY_DATA.update({
                        "summary": response_text,
                        "timestamp": datetime.now().isoformat(),
                        "error": None,
                        "status": "success"
                    })
                    _LOGGER.info("AI summary updated (%d chars)", len(response_text))

        except aiohttp.ClientConnectionError:
            msg = (
                "Cannot connect to Ollama.\n\n"
                f"Is Ollama running at {self._ollama_url}?\n"
                "Try:  ollama serve\n\n"
                "Or change the URL in ai_service.py if using docker/remote."
            )
            AI_SUMMARY_DATA.update({"summary": msg, "status": "error", "timestamp": datetime.now().isoformat()})

        except Exception as e:
            err = f"Error contacting Ollama / generating summary: {str(e)}"
            _LOGGER.exception(err)
            AI_SUMMARY_DATA.update({
                "summary": f"❌ {err}\n\nCheck logs and make sure the model is pulled:\nollama pull {self._ollama_model}",
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })

    async def _build_prompt(self) -> str:
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return (
                "No ESP32 devices (inverters, HVACs, switches etc.) have been added yet.\n\n"
                "→ Go to Settings → Devices & Services → Add Integration → ESP32 Inverter"
            )

        lines = []
        total_pv = 0.0
        total_load_today = 0.0
        device_count = 0

        for entry in entries:
            coordinator = self.hass.data[DOMAIN].get(entry.entry_id, {}).get("coordinator")
            if not coordinator or not hasattr(coordinator, "data") or not coordinator.data:
                continue

            data = coordinator.data
            name = entry.data.get("device_name", f"Device-{entry.entry_id[-6:]}")
            dtype = entry.data.get("device_type", "unknown")

            device_lines = [f"Device: {name}  ({dtype})"]

            if dtype == "Inverter":
                pv = float(data.get("total_pv_power", 0))
                total_pv += pv
                load_today = float(data.get("today_load_consumption", 0))
                total_load_today += load_today

                device_lines.extend([
                    f"  PV total     : {pv} W",
                    f"  PV1          : {data.get('pv1_power', '?')} W @ {data.get('pv1_voltage', '?')} V",
                    f"  Load today   : {load_today} kWh",
                    f"  Grid L1/L2/L3: {data.get('grid_voltage_a','?')} / {data.get('grid_voltage_b','?')} / {data.get('grid_voltage_c','?')} V",
                ])

            elif dtype in ("HVAC", "IR_AC"):
                device_lines.extend([
                    f"  Mode         : {data.get('hvac_mode', 'off')}",
                    f"  Current temp : {data.get('current_temperature', '?')} °C",
                    f"  Target temp  : {data.get('target_temperature', '?')} °C",
                    f"  Fan          : {data.get('fan_mode', 'auto')}",
                ])

            elif dtype == "Switch":
                device_lines.append(f"  State        : {data.get('switch_state', 'off')}")

            if len(device_lines) > 1:  # only add if we have real data
                lines.extend(device_lines)
                device_count += 1

        if device_count == 0:
            return "No devices are currently reporting data. Check if they are online."

        # Aggregates
        agg = []
        if total_pv > 0:
            agg.append(f"Total solar production right now: {total_pv:.0f} W")
        if total_load_today > 0:
            agg.append(f"Household consumption today: {total_load_today:.1f} kWh")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        prompt = f"""Current local time: {now_str}

Home solar + energy status from {device_count} device(s):

{'\n'.join(lines)}

{'\n'.join(agg) if agg else ''}

Write a short, natural, helpful summary in 4–8 sentences.
Include:
- overall system status (production vs consumption)
- anything unusual (very low/high values, grid issues…)
- 1–2 practical suggestions for the user right now

Be concise, friendly and realistic. Do not hallucinate numbers."""
        
        return prompt

    def get_latest_summary(self) -> dict:
        return AI_SUMMARY_DATA.copy()


def get_ai_service(hass: HomeAssistant) -> AIService:
    return hass.data[DOMAIN].get("ai_service")