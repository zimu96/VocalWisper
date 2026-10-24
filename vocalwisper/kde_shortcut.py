"""KDE GlobalAccel shortcut registration (works on Wayland)."""

import os

try:
    from PyQt6.QtDBus import QDBusConnection, QDBusMessage
    from PyQt6.QtCore import QObject, pyqtSlot
    _HAS = True
except Exception:
    _HAS = False

COMPONENT = "vocalwisper"
ACTION = "toggle"
ACTION_ID = [COMPONENT, ACTION, "VocalWisper", "Toggle dictation"]

_MOD = {"ctrl": 0x04000000, "control": 0x04000000,
        "shift": 0x02000000, "alt": 0x08000000, "meta": 0x10000000}


def hotkey_to_qt(s: str) -> int:
    mod = 0
    key = 0
    for p in [x.strip().lower() for x in s.split("+") if x.strip()]:
        if p in _MOD:
            mod |= _MOD[p]
        elif p == "space":
            key = 0x20
        elif p == "enter":
            key = 0x01000004
        elif p == "tab":
            key = 0x01000001
        elif p == "esc":
            key = 0x01000000
        elif p.startswith("f") and p[1:].isdigit():
            key = 0x01000030 + int(p[1:]) - 1
        elif len(p) == 1:
            key = ord(p.upper())
    return mod | key


class KdeShortcut(QObject):
    def __init__(self):
        super().__init__()
        self.bus = None
        self.callback = None
        self._connected = False

    def register(self, hotkey_str: str, callback) -> bool:
        if not _HAS:
            return False
        try:
            self.bus = QDBusConnection.sessionBus()
            if not self.bus.isConnected():
                return False
            self.callback = callback
            self._call("doRegister", [ACTION_ID])
            keycode = hotkey_to_qt(hotkey_str)
            if keycode:
                self._call("setShortcut", [ACTION_ID, [keycode], 2])  # 2 = SetPresent
            path = f"/component/{COMPONENT}"
            if self._connected:
                print("KDE shortcut updated:", hotkey_str, hex(keycode))
                return True
            self._connected = True
            self.bus.connect("org.kde.kglobalaccel", path,
                             "org.kde.kglobalaccel.Component",
                             "globalShortcutPressed", self._on_pressed)
            print("KDE shortcut registered:", hotkey_str, hex(keycode))
            return True
        except Exception as e:
            print("KDE shortcut failed:", e)
            return False

    def _call(self, method, args):
        msg = QDBusMessage.createMethodCall(
            "org.kde.kglobalaccel", "/kglobalaccel", "org.kde.KGlobalAccel", method)
        msg.setArguments(args)
        self.bus.call(msg)

    @pyqtSlot(str, str, "qlonglong")
    def _on_pressed(self, component, shortcut, timestamp):
        if self.callback:
            self.callback()

    def unregister(self):
        if self.bus:
            try:
                self._call("unRegister", [ACTION_ID])
            except Exception:
                pass
