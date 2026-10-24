"""Unix socket IPC for external hotkey triggers (KDE Wayland)."""

import os
import socket
import threading

SOCKET_PATH = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "vocalwisper.sock")


def is_running() -> bool:
    """True if another VocalWisper instance is already listening."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(SOCKET_PATH)
        return True
    except Exception:
        return False
    finally:
        s.close()


class IPCServer:
    def __init__(self, callback):
        self.callback = callback
        self._sock = None
        self._running = False

    def start(self):
        try:
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.bind(SOCKET_PATH)
            self._sock.listen(5)
            self._running = True
            threading.Thread(target=self._loop, daemon=True).start()
            print("IPC listening on", SOCKET_PATH)
        except Exception as e:
            print("IPC start failed:", e)

    def _loop(self):
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except Exception:
                break
            try:
                data = conn.recv(64).decode("utf-8", "ignore").strip()
                if data == "toggle":
                    self.callback()
            except Exception:
                pass
            finally:
                conn.close()

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass
        try:
            os.unlink(SOCKET_PATH)
        except Exception:
            pass
