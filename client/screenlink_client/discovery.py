from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

logger = logging.getLogger(__name__)

class DiscoveryBrowser:
    """
    mDNS browsing using zeroconf.
    Browses for _screenlink._tcp.local. services (ARCHITECTURE.md §6).
    """

    def __init__(
        self,
        on_server_found: Callable[[str, Dict[str, Any]], None],
        on_server_removed: Callable[[str], None],
    ) -> None:
        """
        Initializes the discovery browser.

        Args:
            on_server_found: Callback when a server is discovered.
            on_server_removed: Callback when a server is removed.
        """
        self.zeroconf: Optional[Zeroconf] = None
        self.browser: Optional[ServiceBrowser] = None
        self.on_server_found = on_server_found
        self.on_server_removed = on_server_removed
        self.service_type = "_screenlink._tcp.local."
        self.servers: Dict[str, Dict[str, Any]] = {}

    def start(self) -> None:
        """Starts browsing for ScreenLink servers."""
        if self.zeroconf is not None:
            return

        logger.info("Starting mDNS discovery for %s", self.service_type)
        self.zeroconf = Zeroconf()
        self.browser = ServiceBrowser(
            self.zeroconf, self.service_type, handlers=[self._on_service_state_change]
        )

    def stop(self) -> None:
        """Stops browsing."""
        if self.zeroconf is not None:
            logger.info("Stopping mDNS discovery")
            if self.browser:
                self.browser.cancel()
            self.zeroconf.close()
            self.zeroconf = None
            self.browser = None
            self.servers.clear()

    def _on_service_state_change(
        self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
    ) -> None:
        """Internal callback for zeroconf service state changes."""
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                addresses = [str(addr) for addr in info.parsed_addresses()]
                address = addresses[0] if addresses else "127.0.0.1"
                port = info.port or 48321
                properties = {}
                if info.properties:
                    for k, v in info.properties.items():
                        if isinstance(k, bytes) and isinstance(v, bytes):
                            properties[k.decode('utf-8')] = v.decode('utf-8')

                server_info = {
                    "name": name,
                    "address": address,
                    "port": port,
                    "max_res": properties.get("max_res", "Unknown")
                }
                self.servers[name] = server_info
                logger.info("Discovered ScreenLink server: %s at %s:%d", name, address, port)
                self.on_server_found(name, server_info)
        elif state_change is ServiceStateChange.Removed:
            logger.info("ScreenLink server removed: %s", name)
            if name in self.servers:
                del self.servers[name]
                self.on_server_removed(name)
