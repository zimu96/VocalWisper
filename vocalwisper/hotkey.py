"""Global hotkey handling (pynput)."""

try:
    from pynput import keyboard as _kb
    _HAS = True
except Exception:
    _HAS = False


def to_pynput(s: str) -> str:
    """Convert 'ctrl+shift+space' to pynput format '<ctrl>+<shift>+<space>'."""
    parts = [p.strip().lower() for p in s.split("+") if p.strip()]
    out = []
    for p in parts:
        if p in ("ctrl", "control"):
            out.append("<ctrl>")
        elif p == "shift":
            out.append("<shift>")
        elif p == "alt":
            out.append("<alt>")
        elif p == "space":
            out.append("<space>")
        elif len(p) == 1:
            out.append(p)
        else:
            out.append(f"<{p}>")
    return "+".join(out)


class HotkeyListener:
    def __init__(self, hotkey_str: str, callback):
        self.hotkey_str = hotkey_str
        self.callback = callback
        self._listener = None

    def start(self):
        if not _HAS or not self.hotkey_str:
            return
        try:
            hk = to_pynput(self.hotkey_str)
            print("registering hotkey:", hk)
            self._listener = _kb.GlobalHotKeys({hk: lambda: (print("hotkey triggered"), self.callback())})
            self._listener.daemon = True
            self._listener.start()
            print("hotkey listener started")
        except Exception as e:
            print("hotkey start failed:", e)

    def stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def update(self, hotkey_str: str):
        self.stop()
        self.hotkey_str = hotkey_str
        self.start()
