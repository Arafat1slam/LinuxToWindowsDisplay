from __future__ import annotations

import argparse
import asyncio
import logging
import signal

import gi
import yaml

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from .capture_pipeline import CapturePipeline  # noqa: E402
from .control_server import ControlServer  # noqa: E402
from .discovery import DiscoveryResponder  # noqa: E402
from .display_manager import DisplayManager  # noqa: E402

logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ScreenLink Server")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml")
    return parser.parse_args()

def load_config(path: str) -> dict:
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"Config file {path} not found, using defaults.")
        return {}

async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    config = load_config(args.config)
    control_port = config.get("control_port", 48321)
    server_name = config.get("server_name")

    Gst.init(None)

    discovery = DiscoveryResponder(port=control_port, name=server_name)
    display_mgr = DisplayManager()
    capture_pipe = CapturePipeline()
    server = ControlServer(
        host="0.0.0.0",
        port=control_port,
        display_manager=display_mgr,
        capture_pipeline=capture_pipe,
    )

    discovery.start()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_signal(sig: int) -> None:
        logger.info(f"Received signal {sig}, shutting down...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    await server.start()

    try:
        await stop_event.wait()
    finally:
        discovery.stop()
        await server.stop()
        display_mgr.remove_virtual_display()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
