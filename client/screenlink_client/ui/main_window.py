from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from PyQt6.QtCore import pyqtSignal
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QMainWindow,
        QMenu,
        QPushButton,
        QStatusBar,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    # Dummy classes to avoid errors when PyQt6 is missing
    QMainWindow = object
    def pyqtSignal(*args: Any) -> Any:
        return None

    class DummyWidget:
        pass
    QWidget = DummyWidget

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """
    PyQt6 main window.
    Shows discovered servers and handles connections.
    """
    connect_requested = pyqtSignal(dict)
    disconnect_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ScreenLink Client")
        self.resize(400, 300)

        self.servers: Dict[str, Dict[str, Any]] = {}
        self.is_connected = False

        self._init_ui()
        self._init_tray()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # Server list
        layout.addWidget(QLabel("Discovered Servers:"))
        self.server_list = QListWidget()
        layout.addWidget(self.server_list)

        # Buttons
        btn_layout = QHBoxLayout()

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        btn_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self._on_disconnect_clicked)
        self.btn_disconnect.setEnabled(False)
        btn_layout.addWidget(self.btn_disconnect)

        self.btn_settings = QPushButton("Settings")
        self.btn_settings.clicked.connect(lambda: self.settings_requested.emit())
        btn_layout.addWidget(self.btn_settings)

        layout.addLayout(btn_layout)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Disconnected")

    def _init_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        # Use a default icon or standard icon
        # In a real app we'd load an image file here
        # self.tray.setIcon(QIcon("icon.png"))

        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def closeEvent(self, event: Any) -> None:
        """Hide to tray on close if connected, else quit."""
        if self.is_connected:
            event.ignore()
            self.hide()
            self.tray.showMessage("ScreenLink", "Minimized to tray while connected.")
        else:
            event.accept()

    def add_server(self, name: str, info: Dict[str, Any]) -> None:
        """Adds a server to the list."""
        self.servers[name] = info
        self._update_list()

    def remove_server(self, name: str) -> None:
        """Removes a server from the list."""
        if name in self.servers:
            del self.servers[name]
            self._update_list()

    def _update_list(self) -> None:
        self.server_list.clear()
        for name, info in self.servers.items():
            self.server_list.addItem(f"{name} ({info['address']}:{info['port']})")

    def _on_connect_clicked(self) -> None:
        selected = self.server_list.currentItem()
        if not selected:
            return

        text = selected.text()
        name = text.split(" (")[0]
        if name in self.servers:
            self.connect_requested.emit(self.servers[name])

    def _on_disconnect_clicked(self) -> None:
        self.disconnect_requested.emit()

    def set_connected_state(self, connected: bool) -> None:
        """Updates UI state based on connection status."""
        self.is_connected = connected
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        self.btn_settings.setEnabled(not connected)
        self.server_list.setEnabled(not connected)

        if connected:
            self.status.showMessage("Connected")
        else:
            self.status.showMessage("Disconnected")

    def toggle_fullscreen_video(self, enable: bool) -> None:
        """Toggles a full-screen window overlay (placeholder)."""
        if enable:
            logger.info("Entering fullscreen mode")
            # In a real implementation, this would handle GStreamer video overlay
        else:
            logger.info("Exiting fullscreen mode")
