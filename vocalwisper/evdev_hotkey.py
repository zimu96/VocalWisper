"""Global hotkey by reading /dev/input directly (works on Wayland).

KDE's GlobalAccel sometimes fails to grab shortcuts (especially when the KWin
and kglobalaccel versions do not match). Reading the keyboard devices does not
depend on the compositor and needs the user to be in the `input` group.
"""

import glob
import os
import select
import struct
import threading
import time

_EVENT = struct.Struct("llHHi")  # struct input_event, 64-bit Linux

_KEYS = {
    "esc": 1, "enter": 28, "tab": 15, "space": 57, "backspace": 14,
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9,
    "9": 10, "0": 11,
    "q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21, "u": 22,
    "i": 23, "o": 24, "p": 25, "a": 30, "s": 31, "d": 32, "f": 33,
    "g": 34, "h": 35, "j": 36, "k": 37, "l": 38, "z": 44, "x": 45,
    "c": 46, "v": 47, "b": 48, "n": 49, "m": 50,
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
    "up": 103, "down": 108, "left": 105, "right": 106, "home": 102,
    "end": 107, "pageup": 104, "pagedown": 109, "insert": 110,
    "delete": 111,
}

_MODS = {
    "ctrl": {29, 97},
    "alt": {56, 100},
    "shift": {42, 54},
    "meta": {125, 126},
}


def _parse(hotkey: str):
    parts = [p.strip().lower() for p in (hotkey or "").split("+") if p.strip()]
    mods, key = set(), None
    for p in parts:
        if p in _MODS:
            mods.add(p)
        elif p in _KEYS:
            key = _KEYS[p]
        else:
            return None
    if key is None or not mods:
        return None
    return mods, key


class EvdevHotkey:
    def __init__(self, hotkey: str, callback):
        self.hotkey = hotkey
        self.callback = callback
        self._parsed = _parse(hotkey)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._fds = {}
        self._down = set()
        self._last = 0.0

    @property
    def active(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> bool:
        if not self._parsed:
            return False
        opened = {}
        for path in sorted(glob.glob("/dev/input/event*")):
            try:
                opened[os.open(path, os.O_RDONLY | os.O_NONBLOCK)] = path
            except OSError:
                pass
        if not opened:
            return False
        self._fds = opened
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="evdev-hotkey")
        self._thread.start()
        print(f"evdev hotkey active: {self.hotkey} ({len(opened)} devices)")
        return True

    def update(self, hotkey: str):
        parsed = _parse(hotkey)
        if parsed:
            with self._lock:
                self.hotkey = hotkey
                self._parsed = parsed
                self._down.clear()

    def _matches(self):
        with self._lock:
            parsed = self._parsed
            down = set(self._down)
        if not parsed:
            return False
        mods, key = parsed
        if key not in down:
            return False
        return all(down & codes for codes in (_MODS[m] for m in mods))

    def _run(self):
        while not self._stop.is_set():
            try:
                ready, _, _ = select.select(list(self._fds), [], [], 0.3)
            except (OSError, ValueError):
                break
            for fd in ready:
                try:
                    data = os.read(fd, _EVENT.size * 64)
                except BlockingIOError:
                    continue
                except OSError:
                    continue
                for off in range(0, len(data), _EVENT.size):
                    try:
                        _s, _us, typ, code, value = _EVENT.unpack_from(data, off)
                    except struct.error:
                        break
                    if typ != 1 or value == 2:  # key repeats are irrelevant
                        continue
                    if value == 1:
                        with self._lock:
                            self._down.add(code)
                        if self._matches():
                            now = time.time()
                            if now - self._last > 0.4:
                                self._last = now
                                try:
                                    self.callback()
                                except Exception as e:
                                    print("evdev hotkey callback error:", e)
                    else:
                        with self._lock:
                            self._down.discard(code)

    def stop(self):
        self._stop.set()
        for fd in list(self._fds):
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds = {}
