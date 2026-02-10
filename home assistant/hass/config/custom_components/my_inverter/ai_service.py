# custom_components/my_inverter/ai_service.py
"""AI service for communicating directly with Ollama."""
import logging
from typing import Any
from datetime import datetime, timedelta
import aiohttp

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Store the latest AI response globally
AI_SUMMARY_DATA = {
    "summary": "Initializing AI service...",
    "timestamp": None,
    "error": None,
    "status": "initializing",
}


class AIService:
    """Service to handle AI interactions directly with Ollama."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the AI service."""
        self.hass = hass
        self._update_interval = timedelta(minutes=1)
        self._remove_listener = None
        self._ollama_url = None 
        self._ollama_model = "llama3.2:3b"  # Default model

    async def async_setup(self) -> None:
        """Set up the AI service."""
        _LOGGER.info("Setting up AI service for direct Ollama integration")
        
        # Find Ollama configuration
        self._ollama_url = await self._find_ollama_config()
        
        if self._ollama_url:
            _LOGGER.info("Found Ollama at: %s", self._ollama_url)
        else:
            _LOGGER.warning("Ollama not configured - using default localhost:11434")
            self._ollama_url = "http://192.168.43.252:11434"
        
        try:
            # Register the manual refresh service
            self.hass.services.async_register(
                DOMAIN,
                "refresh_ai_summary",
                self.async_refresh_summary,
            )
            _LOGGER.info("Registered refresh_ai_summary service")
        except Exception as e:
            _LOGGER.error("Failed to register service: %s", e)
        
        # Do an initial fetch
        await self.async_refresh_summary()
        
        # Set up periodic updates (every 1 minute)
        self._remove_listener = async_track_time_interval(
            self.hass,
            self._periodic_update,
            self._update_interval,
        )
        
        _LOGGER.info("AI service setup complete")

    async def async_unload(self) -> None:
        """Unload the AI service."""
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
        
        # Unregister the service
        self.hass.services.async_remove(DOMAIN, "refresh_ai_summary")
        
        _LOGGER.info("AI service unloaded")

    async def _periodic_update(self, now=None) -> None:
        """Periodic update callback."""
        await self.async_refresh_summary()

    async def _find_ollama_config(self) -> str | None:
        """Find Ollama configuration from the Ollama integration."""
        try:
            # Check if Ollama integration is loaded
            if "ollama" in self.hass.data:
                ollama_data = self.hass.data["ollama"]
                _LOGGER.debug("Found ollama data: %s", ollama_data)
                
                # Try to get config entries
                config_entries = self.hass.config_entries.async_entries("ollama")
                if config_entries:
                    # Get the first Ollama config entry
                    entry = config_entries[0]
                    url = entry.data.get("url")
                    if url:
                        # Remove /api suffix if present
                        base_url = url.replace("/api", "")
                        _LOGGER.info("Found Ollama URL from config: %s", base_url)
                        return base_url
            
            # Fallback: try to detect from states
            for state in self.hass.states.async_all():
                if state.entity_id.startswith("sensor.ollama_") or "ollama" in state.attributes.get("integration", ""):
                    # Try to extract URL from attributes
                    url = state.attributes.get("url")
                    if url:
                        return url.replace("/api", "")
            
        except Exception as e:
            _LOGGER.debug("Error finding Ollama config: %s", e)
        
        return None

    async def async_refresh_summary(self, call: ServiceCall = None) -> None:
        """Refresh the AI summary by calling Ollama directly."""
        global AI_SUMMARY_DATA
        
        _LOGGER.info("Refreshing AI summary via Ollama...")
        AI_SUMMARY_DATA["status"] = "updating"
        
        try:
            # Build the prompt
            prompt = await self._build_prompt()
            
            # Call Ollama API directly
            api_url = f"{self._ollama_url}/api/generate"
            
            payload = {
                "model": self._ollama_model,
                "prompt": prompt,
                "stream": False,  # Get complete response at once
            }
            
            _LOGGER.debug("Calling Ollama at %s with model %s", api_url, self._ollama_model)
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        api_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)  # 60 second timeout for AI response
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            ai_text = data.get("response", "")
                            
                            if ai_text:
                                AI_SUMMARY_DATA.update({
                                    "summary": ai_text.strip(),
                                    "timestamp": datetime.now().isoformat(),
                                    "error": None,
                                    "status": "success",
                                    "prompt": prompt,
                                    "model": self._ollama_model,
                                    "ollama_url": self._ollama_url,
                                })
                                
                                _LOGGER.info("AI summary updated successfully (length: %d chars)", len(ai_text))
                            else:
                                raise Exception("Empty response from Ollama")
                                
                        elif response.status == 404:
                            error_text = await response.text()
                            
                            # Model not found - provide helpful message
                            helpful_msg = (f"⚠️ Model '{self._ollama_model}' not found on Ollama server.\n\n"
                                         f"To fix this:\n"
                                         f"1. Run: ollama pull {self._ollama_model}\n"
                                         f"2. Or change the model in the integration code\n\n"
                                         f"Available models you can use:\n"
                                         f"• llama3.2 (recommended, 3GB)\n"
                                         f"• llama3.2:1b (smallest, 1.3GB)\n"
                                         f"• mistral (good quality, 4GB)\n"
                                         f"• phi3 (fast, 2.3GB)")
                            
                            AI_SUMMARY_DATA.update({
                                "summary": helpful_msg,
                                "timestamp": datetime.now().isoformat(),
                                "error": f"Model not found: {self._ollama_model}",
                                "status": "error"
                            })
                            
                        else:
                            error_text = await response.text()
                            raise Exception(f"Ollama returned status {response.status}: {error_text}")
                            
            except aiohttp.ClientConnectorError as e:
                _LOGGER.error("Cannot connect to Ollama: %s", e)
                
                helpful_msg = (f"🔌 Cannot connect to Ollama at {self._ollama_url}\n\n"
                             f"Please check:\n"
                             f"1. Is Ollama running? Run: ollama serve\n"
                             f"2. Is the URL correct?\n"
                             f"3. Can Home Assistant reach this URL?\n\n"
                             f"Default Ollama URL: http://localhost:11434\n"
                             f"Current URL: {self._ollama_url}")
                
                AI_SUMMARY_DATA.update({
                    "summary": helpful_msg,
                    "timestamp": datetime.now().isoformat(),
                    "error": f"Connection error: {str(e)}",
                    "status": "error"
                })
                
            except aiohttp.ServerTimeoutError:
                _LOGGER.error("Ollama request timed out")
                
                helpful_msg = (f"⏱️ Request timed out after 60 seconds.\n\n"
                             f"Your Ollama server might be:\n"
                             f"• Processing a large model\n"
                             f"• Running on slow hardware\n"
                             f"• Overloaded\n\n"
                             f"Try using a smaller/faster model like:\n"
                             f"• llama3.2:1b (fastest)\n"
                             f"• phi3 (good balance)")
                
                AI_SUMMARY_DATA.update({
                    "summary": helpful_msg,
                    "timestamp": datetime.now().isoformat(),
                    "error": "Request timeout",
                    "status": "error"
                })
                
        except Exception as e:
            error_msg = f"Failed to get AI response: {str(e)}"
            _LOGGER.error(error_msg, exc_info=True)
            
            AI_SUMMARY_DATA.update({
                "summary": f"❌ Unexpected error: {str(e)}\n\nCheck Home Assistant logs for details.",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "error"
            })

    async def _build_prompt(self) -> str:
        """Build the prompt for the AI."""
        # Simple test prompt - will be enhanced later to include device data
        return "Define human in one paragraph."

    def get_latest_summary(self) -> dict[str, Any]:
        """Get the latest AI summary data."""
        return AI_SUMMARY_DATA.copy()


def get_ai_service(hass: HomeAssistant) -> AIService:
    """Get the AI service instance."""
    return hass.data[DOMAIN].get("ai_service")