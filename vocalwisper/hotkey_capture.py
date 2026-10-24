"""Dialog to capture a hotkey combination."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent


def key_name(key: int) -> str | None:
    # Letters
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return chr(key).lower()
    # Digits
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key)
    special = {
        Qt.Key.Key_Space: "space",
        Qt.Key.Key_Return: "enter",
        Qt.Key.Key_Enter: "enter",
        Qt.Key.Key_Tab: "tab",
        Qt.Key.Key_Escape: "esc",
        Qt.Key.Key_Backspace: "backspace",
        Qt.Key.Key_Delete: "delete",
        Qt.Key.Key_Up: "up",
        Qt.Key.Key_Down: "down",
        Qt.Key.Key_Left: "left",
        Qt.Key.Key_Right: "right",
        Qt.Key.Key_Home: "home",
        Qt.Key.Key_End: "end",
        Qt.Key.Key_PageUp: "pageup",
        Qt.Key.Key_PageDown: "pagedown",
        Qt.Key.Key_Insert: "insert",
        Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
        Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
        Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
        Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
    }
    if key in special:
        return special[key]
    # fallback: use Qt key name
    try:
        name = Qt.Key(key).name
        if name:
            return name.replace("Key_", "").lower()
    except Exception:
        pass
    return None


class HotkeyCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Capture hotkey")
        self.resize(300, 120)
        layout = QVBoxLayout(self)
        self.label = QLabel("Premi la combinazione di tasti...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        btn = QPushButton("Annulla")
        btn.clicked.connect(self.reject)
        layout.addWidget(btn)
        self.result_str = None

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return  # wait for full combo

        mods = []
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            mods.append("ctrl")
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            mods.append("shift")
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            mods.append("alt")

        kn = key_name(key)
        if kn and mods:
            self.result_str = "+".join(mods + [kn])
            self.label.setText(self.result_str)
            self.accept()
        elif mods:
            self.label.setText("+".join(mods) + "+...")
        else:
            self.label.setText("Serve almeno un modificatore (Ctrl/Shift/Alt)")

    def keyReleaseEvent(self, event):
        pass
