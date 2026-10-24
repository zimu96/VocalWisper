"""System tray icon (PyQt6)."""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QImage, QColor, QPainter, QBrush
from PyQt6.QtCore import Qt

from .icons import make_mic_icon


def pil_to_qicon(img) -> QIcon:
    data = img.convert("RGBA").tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    pix = QPixmap.fromImage(qimg)
    return QIcon(pix)


class Tray:
    def __init__(self, on_toggle, on_settings, on_quit, on_toggle_autostart=None, on_toggle_minimized=None):
        self.on_toggle = on_toggle
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.on_toggle_autostart = on_toggle_autostart
        self.on_toggle_minimized = on_toggle_minimized
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(pil_to_qicon(make_mic_icon(64, "white", "idle")))
        menu = QMenu()
        menu.addAction("Toggle dictation", on_toggle)
        menu.addAction("Settings", on_settings)
        if on_toggle_autostart:
            menu.addAction("Toggle autostart", on_toggle_autostart)
        if on_toggle_minimized:
            menu.addAction("Toggle minimized", on_toggle_minimized)
        menu.addAction("Quit", on_quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def set_state(self, state: str):
        color = "#ff3b30" if state == "recording" else "white"
        st = "recording" if state == "recording" else "idle"
        self.tray.setIcon(pil_to_qicon(make_mic_icon(64, color, st)))
        self.tray.setToolTip(f"VocalWisper - {state}")
        try:
            self.tray.update()
        except Exception:
            pass
        print("tray state:", state)

    def notify(self, title: str, message: str):
        try:
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 8000)
        except Exception:
            pass

    def stop(self):
        self.tray.hide()
