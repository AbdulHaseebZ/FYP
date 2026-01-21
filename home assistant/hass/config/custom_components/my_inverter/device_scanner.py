# custom_components/my_inverter/device_scanner.py
import logging
import asyncio
import aiohttp
import socket
from typing import List, Dict

from homeassistant.components import zeroconf
from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class DeviceScanner:
    """Scan for ESP32 devices on the local network using mDNS (via HA shared instance) + HTTP fallback."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.discovered_devices: List[Dict] = []
        self._lock = asyncio.Lock()

    async def scan_devices(self, timeout: int = 8) -> List[Dict]:
        """Perform full scan: mDNS first, then HTTP fallback if nothing found."""
        self.discovered_devices = []

        _LOGGER.info("=" * 50)
        _LOGGER.info("Starting ESP32 device discovery...")
        _LOGGER.info("=" * 50)

        # Try mDNS discovery first (recommended & most reliable)
        await self._scan_mdns(timeout)

        # Fallback to HTTP if nothing found
        if not self.discovered_devices:
            _LOGGER.info("mDNS found no devices → falling back to HTTP scan...")
            await self._scan_http()

        _LOGGER.info("=" * 50)
        _LOGGER.info(f"Discovery complete. Found {len(self.discovered_devices)} device(s)")
        _LOGGER.info("=" * 50)

        return self.discovered_devices

    # ────────────────────────────────────────────────────────────────
    #                    Modern mDNS Discovery (2024–2026 style)
    # ────────────────────────────────────────────────────────────────
    async def _scan_mdns(self, timeout: int) -> None:
        """Use Home Assistant's shared Zeroconf instance for discovery."""
        zc: Zeroconf = await zeroconf.async_get_instance(self.hass)
        service_type = "_esp32device._tcp.local."

        _LOGGER.info(f"Searching for mDNS service type: {service_type}")

        discovered_event = asyncio.Event()

        def on_service_state_change(
            zeroconf: Zeroconf,
            service_type: str,
            name: str,
            state_change: ServiceStateChange,
        ) -> None:
            if state_change is not ServiceStateChange.Added:
                return
            _LOGGER.debug(f"Service added: {name}")
            asyncio.create_task(self._process_service(zc, service_type, name, discovered_event))

        # Create browser (no .cancel() needed in recent zeroconf versions)
        browser = AsyncServiceBrowser(zc, service_type, [on_service_state_change])

        try:
            # Try some direct/common name queries in parallel
            await asyncio.gather(
                self._try_direct_query(zc, service_type, "esp-node._esp32device._tcp.local."),
                self._try_direct_query(zc, service_type, "esp32_ac_001._esp32device._tcp.local."),
                self._try_direct_query(zc, service_type, "esp32._esp32device._tcp.local."),
                return_exceptions=True,
            )

            # Wait for at least one discovery or timeout
            try:
                await asyncio.wait_for(discovered_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                _LOGGER.debug(f"mDNS discovery timeout after {timeout}s")

        finally:
            # Modern zeroconf: no explicit cancel needed
            # Just drop reference and let GC + internal cleanup happen
            browser = None
            await asyncio.sleep(0.05)  # tiny grace period for pending tasks

    async def _try_direct_query(self, zc: Zeroconf, service_type: str, fullname: str) -> None:
        """Directly query a known/predicted service name."""
        info = AsyncServiceInfo(service_type, fullname)
        try:
            success = await info.async_request(zc, timeout=3000)
            if success and info.addresses:
                await self._process_service_info(info)
        except Exception:
            pass  # most direct queries will fail - that's normal

    async def _process_service(self, zc: Zeroconf, service_type: str, name: str, discovered_event: asyncio.Event):
        """Get detailed info for a newly discovered service."""
        try:
            info = await zc.async_get_service_info(service_type, name)
            if info and info.addresses:
                await self._process_service_info(info)
                discovered_event.set()  # we found at least one device
        except Exception as e:
            _LOGGER.debug(f"Failed to get info for {name}: {e}")

    async def _process_service_info(self, info: AsyncServiceInfo) -> None:
        """Extract device information from mDNS service info."""
        async with self._lock:
            try:
                if not info.addresses:
                    return

                ip_address = socket.inet_ntoa(info.addresses[0])

                # Parse TXT records
                properties = {}
                if info.properties:
                    for key, value in info.properties.items():
                        try:
                            k = key.decode("utf-8", errors="replace")
                            v = value.decode("utf-8", errors="replace")
                            properties[k] = v
                        except Exception:
                            pass

                device_info = {
                    "id": properties.get("id", "unknown"),
                    "type": properties.get("type", "Unknown"),
                    "name": properties.get("name", properties.get("id", "ESP32 Device")),
                    "configured": properties.get("configured", "false").lower() == "true",
                    "ip": ip_address,
                    "port": info.port,
                    "hostname": info.server.rstrip(".") if info.server else None,
                }

                # Avoid duplicates
                if not any(d["id"] == device_info["id"] for d in self.discovered_devices):
                    self.discovered_devices.append(device_info)
                    _LOGGER.info(
                        "✓ Discovered: %s (%s) @ %s port %d",
                        device_info["name"],
                        device_info["id"],
                        device_info["ip"],
                        device_info["port"],
                    )

            except Exception as e:
                _LOGGER.exception("Error processing mDNS service info")

    # ────────────────────────────────────────────────────────────────
    #                         HTTP Fallback Scan
    # ────────────────────────────────────────────────────────────────
    async def _scan_http(self) -> None:
        """Fallback: Try to reach common ESP32 .local hostnames via HTTP."""
        _LOGGER.info("Starting HTTP fallback scan for common ESP32 hostnames...")

        common_hostnames = [
            "esp-node.local",
            "esp32.local",
            "esp32_ac_001.local",
            "my-esp.local",
            "inverter.local",
        ]

        for hostname in common_hostnames:
            try:
                _LOGGER.debug(f"Trying http://{hostname}/ ...")
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://{hostname}/",
                        timeout=aiohttp.ClientTimeout(total=2.5),
                        allow_redirects=False,
                    ) as resp:
                        if resp.status in (200, 301, 302):
                            text = await resp.text()
                            device = self._parse_html_response(text, hostname)
                            if device and not any(d["id"] == device["id"] for d in self.discovered_devices):
                                self.discovered_devices.append(device)
                                _LOGGER.info(f"✓ Found device via HTTP: {hostname}")
            except Exception as e:
                _LOGGER.debug(f"  {hostname} not responding: {e.__class__.__name__}")

    def _parse_html_response(self, html: str, hostname: str) -> Dict | None:
        """Very simple HTML parsing for device info (fallback only)."""
        try:
            device_id = "unknown"
            device_type = "Unknown"
            configured = False

            if "Device ID:" in html:
                start = html.find("Device ID:") + 10
                end = html.find("</", start)
                device_id = html[start:end].strip()

            if "Device Type:" in html:
                start = html.find("Device Type:") + 12
                end = html.find("</", start)
                device_type = html[start:end].strip()

            if "Configured: Yes" in html or "configured\":true" in html:
                configured = True

            return {
                "id": device_id,
                "type": device_type,
                "name": device_id if device_id != "unknown" else "ESP32 Device",
                "configured": configured,
                "ip": hostname,
                "port": 80,
                "hostname": hostname,
            }
        except Exception:
            return None