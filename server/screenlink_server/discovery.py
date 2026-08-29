from __future__ import annotations

import logging
import socket
from typing import Optional

from zeroconf import ServiceInfo, Zeroconf

logger = logging.getLogger(__name__)

class DiscoveryResponder:
    """
    mDNS advertisement using zeroconf.
    See ARCHITECTURE.md §6.
    """
    def __init__(self, port: int = 48321, name: Optional[str] = None):
        self.port = port
        self.hostname = name or socket.gethostname()
        self.zeroconf: Optional[Zeroconf] = None
        self.service_info: Optional[ServiceInfo] = None

    def start(self) -> None:
        """Starts the mDNS advertisement for _screenlink._tcp.local."""
        logger.info(f"Starting mDNS advertisement for ScreenLink on port {self.port}")
        self.zeroconf = Zeroconf()

        properties = {
            b"version": b"0.1.0",
            b"name": self.hostname.encode("utf-8"),
            b"port": str(self.port).encode("utf-8"),
            b"max_res": b"3840x2160"
        }

        self.service_info = ServiceInfo(
            "_screenlink._tcp.local.",
            f"{self.hostname}._screenlink._tcp.local.",
            addresses=[socket.inet_aton("0.0.0.0")],
            port=self.port,
            properties=properties,
            server=f"{self.hostname}.local."
        )

        self.zeroconf.register_service(self.service_info)
        logger.info("mDNS advertisement started.")

    def stop(self) -> None:
        """Stops the mDNS advertisement."""
        if self.zeroconf and self.service_info:
            logger.info("Stopping mDNS advertisement.")
            self.zeroconf.unregister_service(self.service_info)
            self.zeroconf.close()
            self.zeroconf = None
            self.service_info = None
            logger.info("mDNS advertisement stopped.")
