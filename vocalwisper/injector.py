"""Text injection into the focused window (Wayland/X11)."""

import os
import shutil
import subprocess
import time

try:
    from pynput.keyboard import Controller as _KBC
    _HAS_PYNPUT = True
except Exception:
    _HAS_PYNPUT = False

_SOCKETS = [
    os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), ".ydotool_socket"),
    "/tmp/.ydotool_socket",
]


def _wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _socket_path():
    """Return the ydotoold socket only if something is really listening."""
    import socket
    for p in _SOCKETS:
        if not os.path.exists(p):
            continue
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            s.connect(p)
            return p
        except Exception:
            pass
        finally:
            s.close()
    return None


def ydotool_installed() -> bool:
    return bool(shutil.which("ydotool") and shutil.which("ydotoold"))


def ensure_ydotool_daemon() -> bool:
    """Make sure ydotoold is running (user service first, then direct spawn)."""
    if not ydotool_installed():
        return False
    if _socket_path():
        return True
    try:
        subprocess.run(["systemctl", "--user", "enable", "--now", "ydotool"],
                       capture_output=True, timeout=10)
    except Exception:
        pass
    for _ in range(20):
        if _socket_path():
            return True
        time.sleep(0.1)
    try:
        subprocess.Popen(["ydotoold"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        return False
    for _ in range(30):
        if _socket_path():
            return True
        time.sleep(0.1)
    return False


def install_ydotool() -> bool:
    """Install ydotool with a graphical privilege prompt (pkexec), then start it."""
    if ydotool_installed():
        return ensure_ydotool_daemon()
    if not shutil.which("pacman") or not shutil.which("pkexec"):
        return False
    try:
        r = subprocess.run(["pkexec", "pacman", "-S", "--needed", "--noconfirm", "ydotool"],
                           timeout=300)
        if r.returncode != 0:
            return False
    except Exception:
        return False
    return ensure_ydotool_daemon()


class Injector:
    def __init__(self):
        self.kb = _KBC() if _HAS_PYNPUT else None

    def can_type(self) -> bool:
        if _wayland():
            return ydotool_installed() and (_socket_path() is not None or ensure_ydotool_daemon())
        return bool(shutil.which("xdotool") and os.environ.get("DISPLAY"))

    @staticmethod
    def _clipboard_get():
        if not shutil.which("wl-paste"):
            return None
        try:
            types = subprocess.run(["wl-paste", "--list-types"], capture_output=True,
                                   text=True, timeout=2).stdout
            if "text/plain" not in types:
                return None
            r = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, timeout=2)
            return r.stdout if r.returncode == 0 else None
        except Exception:
            return None

    @staticmethod
    def _clipboard_set(data: bytes, primary: bool = False):
        cmd = ["wl-copy"] + (["--primary"] if primary else [])
        try:
            subprocess.run(cmd, input=data, timeout=2,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _paste_wayland(self, text: str) -> bool:
        """Paste text through the clipboard (needed for non-ASCII characters)."""
        if not shutil.which("wl-copy"):
            return False
        old = self._clipboard_get()
        data = text.encode("utf-8")
        self._clipboard_set(data)
        self._clipboard_set(data, primary=True)
        try:
            # Shift+Insert pastes in GUI apps and terminals alike
            subprocess.run(["ydotool", "key", "42:1", "110:1", "110:0", "42:0"],
                           capture_output=True, timeout=5)
        except Exception as e:
            print("ydotool paste failed:", e)
            return False
        time.sleep(0.5)
        if old is not None:
            self._clipboard_set(old)
        else:
            try:
                subprocess.run(["wl-copy", "--clear"], timeout=2,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        return True

    def type_text(self, text: str) -> None:
        if not text:
            return
        text = text + " "
        if _wayland() and ydotool_installed():
            ensure_ydotool_daemon()
            try:
                if text.isascii():
                    subprocess.run(["ydotool", "type", "--key-delay", "2", "--file", "-"],
                                   input=text.encode("utf-8"), timeout=15)
                    return
                if self._paste_wayland(text):
                    return
                # fallback: type only the ASCII part
                ascii_only = "".join(c for c in text if c.isascii())
                subprocess.run(["ydotool", "type", "--key-delay", "2", "--file", "-"],
                               input=ascii_only.encode("utf-8"), timeout=15)
                return
            except Exception as e:
                print("ydotool failed:", e)
        if shutil.which("xdotool") and os.environ.get("DISPLAY"):
            try:
                subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "5", text], timeout=10)
                return
            except Exception as e:
                print("xdotool failed:", e)
        if shutil.which("wtype"):
            try:
                subprocess.run(["wtype", text], timeout=10)
                return
            except Exception as e:
                print("wtype failed:", e)
        if self.kb:
            try:
                self.kb.type(text)
            except Exception as e:
                print("pynput type failed:", e)
