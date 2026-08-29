from __future__ import annotations

from typing import Any, Dict

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QComboBox,
        QDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSlider,
        QVBoxLayout,
    )
except ImportError:
    class QDialog:
        pass

class SettingsDialog(QDialog):
    """
    PyQt6 settings dialog for resolution, FPS, bitrate, and jitter buffer.
    """
    def __init__(self, current_settings: Dict[str, Any], parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(300, 200)

        self.settings = current_settings.copy()

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Resolution
        self.res_combo = QComboBox()
        self.res_combo.addItems(["1920x1080", "2560x1440", "1280x720"])
        idx = self.res_combo.findText(self.settings.get("default_resolution", "1920x1080"))
        if idx >= 0:
            self.res_combo.setCurrentIndex(idx)
        form.addRow("Resolution:", self.res_combo)

        # FPS
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["60", "30"])
        idx = self.fps_combo.findText(str(self.settings.get("default_fps", 60)))
        if idx >= 0:
            self.fps_combo.setCurrentIndex(idx)
        form.addRow("FPS:", self.fps_combo)

        # Bitrate
        self.bitrate_slider = QSlider(Qt.Orientation.Horizontal)
        self.bitrate_slider.setRange(1000, 20000)
        self.bitrate_slider.setSingleStep(1000)
        self.bitrate_slider.setValue(self.settings.get("default_bitrate", 8000))

        self.bitrate_label = QLabel(f"{self.bitrate_slider.value()} kbps")
        self.bitrate_slider.valueChanged.connect(
            lambda v: self.bitrate_label.setText(f"{v} kbps")
        )

        br_layout = QHBoxLayout()
        br_layout.addWidget(self.bitrate_slider)
        br_layout.addWidget(self.bitrate_label)
        form.addRow("Bitrate:", br_layout)

        # Jitter buffer
        self.jitter_slider = QSlider(Qt.Orientation.Horizontal)
        self.jitter_slider.setRange(10, 200)
        self.jitter_slider.setValue(self.settings.get("jitter_buffer_latency", 50))

        self.jitter_label = QLabel(f"{self.jitter_slider.value()} ms")
        self.jitter_slider.valueChanged.connect(
            lambda v: self.jitter_label.setText(f"{v} ms")
        )

        jb_layout = QHBoxLayout()
        jb_layout.addWidget(self.jitter_slider)
        jb_layout.addWidget(self.jitter_label)
        form.addRow("Jitter Buffer:", jb_layout)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def get_settings(self) -> Dict[str, Any]:
        """Returns the updated settings dictionary."""
        self.settings["default_resolution"] = self.res_combo.currentText()
        self.settings["default_fps"] = int(self.fps_combo.currentText())
        self.settings["default_bitrate"] = self.bitrate_slider.value()
        self.settings["jitter_buffer_latency"] = self.jitter_slider.value()
        return self.settings
