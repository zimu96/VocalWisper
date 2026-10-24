"""Autostart desktop entry management."""

import os

AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
DESKTOP_FILE = os.path.join(AUTOSTART_DIR, "vocalwisper.desktop")


def set_autostart(enabled: bool, exec_path: str, minimized: bool = True) -> None:
    if enabled:
        os.makedirs(AUTOSTART_DIR, exist_ok=True)
        args = exec_path
        if minimized:
            args += " --minimized"
        content = f"""[Desktop Entry]
Type=Application
Name=VocalWisper
Exec={args}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""
        with open(DESKTOP_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        try:
            os.remove(DESKTOP_FILE)
        except FileNotFoundError:
            pass
