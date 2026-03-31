# custom_components/my_inverter/ai_service.py
"""AI service with rule matching and policy recommendations via Ollama."""

import logging
import json
import asyncio
import async_timeout
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .tag_engine import TagEngine
from .profile_manager import load_profile
from .rule_matcher import RuleMatcher

_LOGGER = logging.getLogger(__name__)

# Global storage for the sidebar panel
AI_SUMMARY_DATA = {
    "summary": "Initializing...",
    "timestamp": None,
    "error": None,
    "status": "initializing",
    "active_rules": [],
    "active_tags": [],
    "device_states": {},
}


class AIService:
    """AI Service with rule matching and Ollama LLM integration."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._update_interval = timedelta(minutes=5)
        self._is_updating = False

        self.tag_engine = TagEngine()
        self.rule_matcher: RuleMatcher | None = None
        self.rules_db: list[dict] = []

        # Ollama Configuration
        self.ollama_url = "http://192.168.43.252:11434/api/generate"
        self.model = "llama3.2:3b"

    async def async_setup(self) -> None:
        """Set up the AI Service and load rules database."""
        _LOGGER.info("Setting up AI Service with Rule Matching Engine & Ollama")

        # Load rules from JSON
        await self.hass.async_add_executor_job(self._load_rules_db)

        self.hass.services.async_register(
            DOMAIN, "refresh_ai_summary", self.async_refresh_summary
        )

        # Initial refresh - but only after HA is fully started
        self.hass.async_create_task(self._delayed_initial_refresh())

        # Periodic update timer
        async_track_time_interval(
            self.hass, self.async_refresh_summary, self._update_interval
        )

    async def _delayed_initial_refresh(self) -> None:
        """Wait until Home Assistant is fully started before first AI refresh."""
        # Wait a bit so all devices are properly loaded
        await asyncio.sleep(10)
        _LOGGER.info("✅ Home Assistant fully started. Starting first AI summary generation.")
        await self.async_refresh_summary()

    def _load_rules_db(self) -> None:
        """Load rules database from JSON file."""
        rules_path = self.hass.config.path("my_inverter_rules.json")
        try:
            with open(rules_path, "r") as f:
                self.rules_db = json.load(f)
            self.rule_matcher = RuleMatcher(self.rules_db)
            _LOGGER.info(f"✅ Loaded {len(self.rules_db)} rules from {rules_path}")
        except FileNotFoundError:
            _LOGGER.warning(f"Rules file not found at {rules_path}. Starting with empty rules.")
            self.rules_db = []
            self.rule_matcher = RuleMatcher([])
        except Exception as e:
            _LOGGER.error(f"❌ Failed to load rules: {e}")
            self.rules_db = []
            self.rule_matcher = RuleMatcher([])

    async def async_refresh_summary(self, _=None) -> None:
        """Fetch system state and get a recommendation from the LLM."""
        if self._is_updating:
            _LOGGER.debug("AI Update already in progress, skipping cycle")
            return

        self._is_updating = True
        global AI_SUMMARY_DATA

        try:
            # Only activate AI when there are actual devices configured
            entries = self.hass.config_entries.async_entries(DOMAIN)
            if not entries:
                AI_SUMMARY_DATA.update({
                    "summary": "Waiting for devices to be configured in Home Assistant...",
                    "status": "waiting_for_devices",
                    "timestamp": datetime.now().isoformat(),
                })
                _LOGGER.info("AI Service: No devices yet, waiting...")
                return

            _LOGGER.info(f"🔄 Starting AI summary refresh with {len(entries)} devices")

            # 1. Gather Context
            profile = await self.hass.async_add_executor_job(load_profile, self.hass)
            active_tags = await self._get_active_tags_from_devices()
            device_states = await self._get_device_states()

            # 2. Filter Rules locally (Top 5 matched rules only)
            matched_rules = []
            if self.rule_matcher:
                matched_rules = self.rule_matcher.get_matching_rules(
                    active_tags, profile, top_k=5
                )

            _LOGGER.info(f"📋 Found {len(matched_rules)} matching rules for LLM")

            # 3. Build prompt and log it fully
            prompt = self._build_full_prompt(
                profile.get("setting", "residential"),
                matched_rules,
                device_states
            )

            # Log the exact prompt being sent to LLM
            _LOGGER.info("=== PROMPT SENT TO OLLAMA ===")
            _LOGGER.info(prompt)
            _LOGGER.info("=== END OF PROMPT ===")

            # 4. Call LLM
            ai_recommendation = await self._get_llm_recommendation(prompt)

            # 5. Update Global Data for UI
            AI_SUMMARY_DATA.update({
                "summary": ai_recommendation,
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "active_rules": matched_rules,
                "active_tags": active_tags,
                "device_states": device_states,
                "error": None
            })

            _LOGGER.info("✅ AI summary successfully generated and updated")

        except Exception as e:
            _LOGGER.error(f"Error in AI Service: {e}", exc_info=True)
            AI_SUMMARY_DATA.update({
                "status": "error",
                "error": str(e),
                "summary": "An error occurred while generating AI insights."
            })
        finally:
            self._is_updating = False

    def _build_full_prompt(self, setting: str, rules: list, device_states: dict) -> str:
        """Build the complete prompt with detailed logging."""
        user_message = self._build_user_message({
            "setting": setting,
            "active_rules": rules,
            "device_states": device_states,
        })

        prompt = f"""You are the Smart Load Optimizer Assistant for a {setting} facility. 
Your goal is to analyze the current energy situation and provide clear, actionable instructions based strictly on the pre-defined system policies provided below.

When generating recommendations:
1. Be concise and action-oriented
2. Only recommend changes that align with the active policies
3. Provide specific device names and target values
4. Explain the reasoning behind each recommendation
5. Prioritize battery preservation and cost savings

{user_message}"""

        return prompt

    async def _get_llm_recommendation(self, prompt: str) -> str:
        """Send prompt to Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.7,
        }

        try:
            session = async_get_clientsession(self.hass)
            async with async_timeout.timeout(120):
                async with session.post(self.ollama_url, json=payload) as response:
                    if response.status == 200:
                        res_json = await response.json()
                        response_text = res_json.get("response", "No response generated.")
                        _LOGGER.info("✅ Received response from Ollama")
                        return response_text
                    else:
                        error_msg = f"Ollama Error: {response.status}"
                        _LOGGER.error(error_msg)
                        return error_msg
        except asyncio.TimeoutError:
            _LOGGER.error("Ollama request timed out")
            return "AI Request timed out. The local LLM is taking too long to respond."
        except Exception as e:
            _LOGGER.error(f"Ollama connection error: {e}")
            return f"Connection Error: {str(e)}"

    def _build_user_message(self, llm_input: dict) -> str:
        """Build the user message for the LLM."""
        active_rules = llm_input.get("active_rules", [])
        device_states = llm_input.get("device_states", {})
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rules_str = "\n".join([f"* {rule}" for rule in active_rules]) or "* No applicable policies at this time\n"

        devices_str = ""
        for device_name, states in device_states.items():
            devices_str += f"* [{device_name}]\n"
            for key, value in states.items():
                devices_str += f"   * {key}: {value}\n"
        if not devices_str:
            devices_str = "* No live device data available\n"

        message = f"""### 🕐 CURRENT TIME
{now_str}

### 📜 MANDATORY POLICIES TO FOLLOW
{rules_str}

### 🔌 LIVE DEVICE STATES
{devices_str}

### INSTRUCTIONS FOR YOUR RESPONSE:
1. **Summary**: Provide a 2-3 sentence summary of the current energy state.
2. **Recommended Actions**: List specific changes for each affected device.
   * Format: [Device Name]: Change [Attribute] from [Current] to [Target] (Reason)
3. **Reasoning**: Briefly explain why these actions protect the battery or optimize costs.
4. Keep the response concise but actionable.
"""

        return message

    async def _get_active_tags_from_devices(self) -> list[str]:
        """Retrieve current system tags based on hardware states."""
        profile = await self.hass.async_add_executor_job(load_profile, self.hass)
        if not profile:
            return []

        entries = self.hass.config_entries.async_entries(DOMAIN)
        structured_data = {}

        for entry in entries:
            coordinator = self.hass.data[DOMAIN].get(entry.entry_id, {}).get("coordinator")
            if coordinator and coordinator.data:
                device_name = entry.data.get("device_name", "Unknown")
                structured_data[device_name] = coordinator.data

        return self.tag_engine.get_active_tags(self.hass, structured_data, profile)

    async def _get_device_states(self) -> dict:
        """Collect live device states for the LLM prompt."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        device_states = {}

        for entry in entries:
            coordinator = self.hass.data[DOMAIN].get(entry.entry_id, {}).get("coordinator")
            if coordinator and coordinator.data:
                device_name = entry.data.get("device_name", f"Device_{entry.entry_id[-6:]}")
                device_states[device_name] = dict(coordinator.data)

        return device_states

    async def async_unload(self) -> None:
        """Cleanup when unloading the integration."""
        _LOGGER.info("Unloading AI Service")