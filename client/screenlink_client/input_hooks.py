from __future__ import annotations

import logging
from typing import Any, Callable, Union, Dict, Optional

try:
    from pynput import keyboard, mouse
except ImportError:
    mouse = None
    keyboard = None

logger = logging.getLogger(__name__)

class InputHooks:
    """
    Global input hooks (ARCHITECTURE.md §12).
    Captures mouse and keyboard events and normalizes them.
    """

    def __init__(
        self,
        on_input_event: Callable[[Dict[str, Any]], None],
        screen_width: int = 1920,
        screen_height: int = 1080,
    ) -> None:
        self.on_input_event = on_input_event
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.mouse_listener: Optional[mouse.Listener] = None
        self.keyboard_listener: Optional[keyboard.Listener] = None
        self._running: bool = False

    def start(self) -> None:
        """Starts capturing input events."""
        if self._running or mouse is None or keyboard is None:
            return

        logger.info("Starting input hooks")
        self.mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll
        )
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )

        self.mouse_listener.start()
        self.keyboard_listener.start()
        self._running = True

    def stop(self) -> None:
        """Stops capturing input events."""
        if not self._running:
            return

        logger.info("Stopping input hooks")
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        self._running = False

    def update_resolution(self, width: int, height: int) -> None:
        """Updates screen resolution for mouse normalization."""
        self.screen_width = width
        self.screen_height = height

    def _on_mouse_move(self, x: float, y: float) -> None:
        norm_x = min(max(x / self.screen_width, 0.0), 1.0)
        norm_y = min(max(y / self.screen_height, 0.0), 1.0)

        self.on_input_event({
            "kind": "mouse_move",
            "x": norm_x,
            "y": norm_y
        })

    def _on_mouse_click(self, x: float, y: float, button: mouse.Button, pressed: bool) -> None:
        btn_name = "left"
        if button == mouse.Button.right:
            btn_name = "right"
        elif button == mouse.Button.middle:
            btn_name = "middle"

        self.on_input_event({
            "kind": "mouse_button",
            "button": btn_name,
            "action": "down" if pressed else "up"
        })

    def _on_mouse_scroll(self, x: float, y: float, dx: float, dy: float) -> None:
        self.on_input_event({
            "kind": "scroll",
            "delta_x": int(dx),
            "delta_y": int(dy)
        })

    def _map_key(self, key: Union[keyboard.Key, keyboard.KeyCode]) -> str:
        """Maps pynput key to evdev key name."""
        if hasattr(key, 'char') and key.char:
            char = key.char.upper()
            return f"KEY_{char}"

        # Basic mapping for special keys
        key_map = {
            keyboard.Key.space: "KEY_SPACE",
            keyboard.Key.enter: "KEY_ENTER",
            keyboard.Key.shift: "KEY_LEFTSHIFT",
            keyboard.Key.shift_r: "KEY_RIGHTSHIFT",
            keyboard.Key.ctrl: "KEY_LEFTCTRL",
            keyboard.Key.ctrl_r: "KEY_RIGHTCTRL",
            keyboard.Key.alt: "KEY_LEFTALT",
            keyboard.Key.alt_gr: "KEY_RIGHTALT",
            keyboard.Key.backspace: "KEY_BACKSPACE",
            keyboard.Key.tab: "KEY_TAB",
            keyboard.Key.esc: "KEY_ESC",
            keyboard.Key.up: "KEY_UP",
            keyboard.Key.down: "KEY_DOWN",
            keyboard.Key.left: "KEY_LEFT",
            keyboard.Key.right: "KEY_RIGHT",
        }
        return key_map.get(key, "KEY_UNKNOWN")

    def _on_key_press(self, key: Union[keyboard.Key, keyboard.KeyCode]) -> None:
        evdev_key = self._map_key(key)
        self.on_input_event({
            "kind": "key",
            "code": evdev_key,
            "action": "down"
        })

    def _on_key_release(self, key: Union[keyboard.Key, keyboard.KeyCode]) -> None:
        evdev_key = self._map_key(key)
        self.on_input_event({
            "kind": "key",
            "code": evdev_key,
            "action": "up"
        })
