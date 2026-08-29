from __future__ import annotations

import logging
import re
import subprocess
from typing import Tuple

logger = logging.getLogger(__name__)

class DisplayManager:
    """
    Virtual X11 display creation.
    See ARCHITECTURE.md §9.
    """
    def __init__(self) -> None:
        self.current_width: int = 0
        self.current_height: int = 0
        self.virtual_output: str = "VIRTUAL1"
        self.mode_name: str = ""

    def _run_command(self, cmd: list[str]) -> str:
        """Runs a subprocess command and returns output."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}\nError: {e.stderr}")
            raise RuntimeError(f"Command failed: {e}") from e

    def _generate_modeline(self, width: int, height: int, fps: float = 60.0) -> str:
        """Generates a modeline using the cvt command."""
        output = self._run_command(["cvt", str(width), str(height), str(fps)])
        match = re.search(r'Modeline\s+"([^"]+)"\s+(.*)', output)
        if not match:
            raise ValueError("Could not parse modeline from cvt output.")
        self.mode_name = match.group(1)
        return match.group(2)

    def create_virtual_display(self, width: int, height: int) -> None:
        """Creates a virtual X11 display output."""
        logger.info(f"Creating virtual display {width}x{height}")
        self.remove_virtual_display()

        try:
            modeline = self._generate_modeline(width, height)
            self._run_command(["xrandr", "--newmode", self.mode_name] + modeline.split())
            self._run_command(["xrandr", "--addmode", self.virtual_output, self.mode_name])

            xrandr_out = self._run_command(["xrandr"])
            primary_match = re.search(r'^(\S+) connected primary', xrandr_out, re.MULTILINE)
            if not primary_match:
                primary_match = re.search(r'^(\S+) connected', xrandr_out, re.MULTILINE)

            right_of_arg = []
            if primary_match:
                right_of_arg = ["--right-of", primary_match.group(1)]

            self._run_command(
                ["xrandr", "--output", self.virtual_output, "--mode", self.mode_name] + right_of_arg
            )

            self.current_width = width
            self.current_height = height
            logger.info("Virtual display created successfully.")
        except Exception as e:
            logger.error(f"Failed to create virtual display: {e}")
            self.remove_virtual_display()
            raise

    def remove_virtual_display(self) -> None:
        """Tears down the virtual X11 display output."""
        logger.info("Removing virtual display if exists.")
        try:
            self._run_command(["xrandr", "--output", self.virtual_output, "--off"])
            if self.mode_name:
                subprocess.run(
                    ["xrandr", "--delmode", self.virtual_output, self.mode_name],
                    capture_output=True,
                )
                subprocess.run(["xrandr", "--rmmode", self.mode_name], capture_output=True)
            self.mode_name = ""
            self.current_width = 0
            self.current_height = 0
        except Exception as e:
            logger.warning(f"Error while removing virtual display: {e}")

    def get_geometry(self) -> Tuple[int, int, int, int]:
        """Gets the geometry (startx, starty, endx, endy) for the virtual display."""
        if not self.current_width or not self.current_height:
            raise ValueError("Virtual display is not currently active.")

        xrandr_out = self._run_command(["xrandr"])
        pattern = re.compile(
            r"^" + re.escape(self.virtual_output) + r"\s+connected.*?(\d+)x(\d+)\+(\d+)\+(\d+)",
            re.MULTILINE,
        )
        match = pattern.search(xrandr_out)
        if not match:
            raise RuntimeError("Could not find virtual display geometry in xrandr output.")

        w, h, x, y = map(int, match.groups())
        return (x, y, x + w, y + h)
