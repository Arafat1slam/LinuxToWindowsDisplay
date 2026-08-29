from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import uinput

logger = logging.getLogger(__name__)

class InputInjector:
    """
    uinput virtual device injection.
    See ARCHITECTURE.md §12.
    """
    def __init__(self, screen_width: int, screen_height: int) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.device: Optional[uinput.Device] = None

    def setup(self) -> None:
        """Initializes the virtual uinput device for mouse and keyboard."""
        logger.info("Setting up uinput virtual device.")

        events = [
            uinput.REL_X,
            uinput.REL_Y,
            uinput.REL_WHEEL,
            uinput.BTN_LEFT,
            uinput.BTN_RIGHT,
            uinput.BTN_MIDDLE,
        ]

        # Add basic keys, can expand as needed based on common usage
        for key_name in dir(uinput):
            if key_name.startswith("KEY_"):
                events.append(getattr(uinput, key_name))

        self.device = uinput.Device(events, name="ScreenLink Virtual Input")
        logger.info("uinput virtual device created.")

    def teardown(self) -> None:
        """Tears down the virtual uinput device."""
        if self.device:
            logger.info("Tearing down uinput virtual device.")
            self.device.destroy()
            self.device = None

    def handle_input_event(self, payload: Dict[str, Any]) -> None:
        """Dispatches an input event based on its kind."""
        if not self.device:
            logger.warning("Input event received but uinput device not set up.")
            return

        kind = payload.get("kind")
        try:
            if kind == "mouse_move":
                # x = int(payload.get("x", 0.0) * self.screen_width)
                # y = int(payload.get("y", 0.0) * self.screen_height)
                # Note: REL_X/Y are relative, ABS_X/Y are absolute.
                # For proper absolute mapping uinput needs ABS events, but using basic REL
                # for now as standard python-uinput supports REL easily.
                # A full implementation would use ABS_X/ABS_Y with ranges.
                pass # placeholder for exact implementation matching REL vs ABS
            elif kind == "mouse_button":
                button = payload.get("button")
                action = payload.get("action")
                btn_map = {
                    "left": uinput.BTN_LEFT,
                    "right": uinput.BTN_RIGHT,
                    "middle": uinput.BTN_MIDDLE,
                }
                if button in btn_map:
                    self.device.emit(btn_map[button], 1 if action == "down" else 0)
            elif kind == "scroll":
                delta_y = payload.get("delta_y", 0)
                if delta_y != 0:
                    self.device.emit(uinput.REL_WHEEL, delta_y)
            elif kind == "key":
                code_name = payload.get("code", "")
                action = payload.get("action")
                if hasattr(uinput, code_name):
                    key_code = getattr(uinput, code_name)
                    self.device.emit(key_code, 1 if action == "down" else 0)
        except Exception as e:
            logger.error(f"Error handling input event: {e}")
