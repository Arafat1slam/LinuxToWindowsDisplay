from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import Any, Dict

import yaml

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:
    QApplication = None

from .control_client import ControlClient
from .discovery import DiscoveryBrowser
from .input_hooks import InputHooks
from .render_pipeline import RenderPipeline
from .ui.main_window import MainWindow
from .ui.settings_dialog import SettingsDialog


def load_config(config_path: str) -> Dict[str, Any]:
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

class ApplicationController:
    """Main application controller tying all components together."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.app = QApplication(sys.argv)
        self.main_window = MainWindow()

        self.discovery = DiscoveryBrowser(
            on_server_found=self.main_window.add_server,
            on_server_removed=self.main_window.remove_server
        )

        self.control = ControlClient(
            on_disconnected=self._on_disconnected,
            on_reconnected=self._on_reconnected
        )

        self.pipeline = RenderPipeline()
        self.input_hooks = InputHooks(on_input_event=self._on_input_event)

        # Connect UI signals
        self.main_window.connect_requested.connect(self._on_connect_requested)
        self.main_window.disconnect_requested.connect(self._on_disconnect_requested)
        self.main_window.settings_requested.connect(self._show_settings)

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self.config, self.main_window)
        if dialog.exec():
            self.config.update(dialog.get_settings())
            # Live update jitter buffer if playing
            self.pipeline.update_jitter_buffer(self.config.get("jitter_buffer_latency", 50))

    def _on_input_event(self, payload: Dict[str, Any]) -> None:
        if self.control.is_connected:
            asyncio.create_task(self.control.send_input_event(payload))

    def _on_connect_requested(self, server_info: Dict[str, Any]) -> None:
        asyncio.create_task(self._connect_to_server(server_info))

    def _on_disconnect_requested(self) -> None:
        asyncio.create_task(self._disconnect_from_server())

    async def _connect_to_server(self, server_info: Dict[str, Any]) -> None:
        host = server_info["address"]
        port = server_info["port"]

        try:
            await self.control.connect(host, port)

            res = self.config.get("default_resolution", "1920x1080")
            fps = self.config.get("default_fps", 60)

            ack = await self.control.send_hello(res, fps)
            udp_port = ack.get("udp_video_port", 5000)

            await self.control.send_start_stream()

            self.pipeline.start(udp_port, self.config.get("jitter_buffer_latency", 50))

            res_parts = ack.get("granted_res", res).split("x")
            if len(res_parts) == 2:
                self.input_hooks.update_resolution(int(res_parts[0]), int(res_parts[1]))
            self.input_hooks.start()

            self.main_window.set_connected_state(True)
            self.main_window.toggle_fullscreen_video(True)

        except Exception as e:
            logging.error("Connection flow failed: %s", e)
            self.main_window.set_connected_state(False)

    async def _disconnect_from_server(self) -> None:
        try:
            await self.control.send_stop_stream()
            await self.control.send_disconnect("User requested disconnect")
        except Exception:
            pass
        finally:
            self._cleanup_connection()

    def _on_disconnected(self, reason: str) -> None:
        self._cleanup_connection()

    def _on_reconnected(self) -> None:
        # If we reconnected, we might need to send hello/start_stream again
        # Depends on exact protocol flow for reconnects.
        pass

    def _cleanup_connection(self) -> None:
        self.input_hooks.stop()
        self.pipeline.stop()
        self.main_window.set_connected_state(False)
        self.main_window.toggle_fullscreen_video(False)

    def start(self) -> None:
        self.discovery.start()
        self.main_window.show()

    def shutdown(self) -> None:
        self.discovery.stop()
        self._cleanup_connection()
        if self.control.is_connected:
            asyncio.run(self.control.disconnect())

async def process_qt_events(app: Any) -> None:
    """Manually process Qt events in the asyncio event loop."""
    while True:
        app.processEvents()
        await asyncio.sleep(0.01)

def main() -> None:
    parser = argparse.ArgumentParser(description="ScreenLink Client")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    if QApplication is None:
        logging.error("PyQt6 is required but not installed.")
        sys.exit(1)

    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), args.config)
    config = load_config(config_path)

    controller = ApplicationController(config)

    if os.name == 'nt':
        # Handle Windows console close event
        try:
            import win32api
            def on_exit(sig: Any, func: Any = None) -> bool:
                controller.shutdown()
                return True
            win32api.SetConsoleCtrlHandler(on_exit, True)
        except ImportError:
            pass

    # Handle graceful shutdown on Unix
    def signal_handler(sig: Any, frame: Any) -> None:
        controller.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    loop = asyncio.get_event_loop()
    controller.start()

    # Run Qt and asyncio together
    try:
        loop.run_until_complete(process_qt_events(controller.app))
    except KeyboardInterrupt:
        pass
    finally:
        controller.shutdown()

if __name__ == "__main__":
    main()
