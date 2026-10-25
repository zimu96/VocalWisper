"""Microphone level management through pactl.

While dictating the level is tuned automatically (up if the voice is too weak
to be recognised, down if the signal clips); afterwards the previous level is
restored, so calls and browsers keep the level the user configured.
"""

import json
import os
import re
import shutil
import subprocess

import numpy as np

SOURCE = "@DEFAULT_SOURCE@"
STATE_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp",
                          "vocalwisper_mic_volume.json")


def _pactl(*args):
    try:
        return subprocess.run(["pactl", *args], capture_output=True, text=True,
                              timeout=3).stdout
    except Exception:
        return ""


def get_volume():
    if not shutil.which("pactl"):
        return None
    m = re.search(r"(\d+)%", _pactl("get-source-volume", SOURCE))
    return int(m.group(1)) / 100.0 if m else None


def set_volume(frac: float):
    _pactl("set-source-volume", SOURCE, f"{max(0, round(frac * 100))}%")


class MicGain:
    LOW, HIGH = 0.04, 0.15      # speech RMS range we aim for
    MIN_VOL, MAX_VOL = 0.08, 0.35   # above ~35% PipeWire turns on the hardware boost -> clipping

    def __init__(self, start: float = 0.25):
        self.start = start
        self.vol = start
        self._orig = None
        self._hist = []
        self._last_step = 0.0
        self.recover()

    def recover(self):
        """Restore the level left behind by a crashed run."""
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                set_volume(float(json.load(f)["orig"]))
        except Exception:
            pass
        self._clear_file()

    def _clear_file(self):
        try:
            os.unlink(STATE_FILE)
        except Exception:
            pass

    def begin(self, start: float = None):
        if self._orig is not None or get_volume() is None:
            return
        self._orig = get_volume()
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"orig": self._orig}, f)
        except Exception:
            pass
        self.vol = min(self.MAX_VOL, max(self.MIN_VOL, start or self.start))
        self._hist = []
        self._last_step = 0.0
        set_volume(self.vol)
        print(f"mic volume {round(self._orig * 100)}% -> {round(self.vol * 100)}% (dictation)")

    def _step(self, factor: float, now: float, why: str):
        new = min(self.MAX_VOL, max(self.MIN_VOL, self.vol * factor))
        self._hist = []
        self._last_step = now
        if abs(new - self.vol) < 0.005:
            return
        print(f"mic volume {round(self.vol * 100)}% -> {round(new * 100)}% ({why})")
        self.vol = new
        set_volume(new)

    def update(self, arr, is_speech: bool, now: float):
        if self._orig is None or arr is None or len(arr) == 0:
            return
        if int(np.sum(np.abs(arr) >= 0.99)) >= 3 and now - self._last_step > 0.8:
            self._step(0.85, now, "clipping")
            return
        if not is_speech:
            return
        self._hist.append(float(np.sqrt(np.mean(arr ** 2))))
        if len(self._hist) >= 12 and now - self._last_step > 2.5:
            med = float(np.median(self._hist))
            if med < self.LOW:
                self._step(1.15, now, "voice too weak")
            elif med > self.HIGH:
                self._step(0.87, now, "voice too loud")
            else:
                self._hist = self._hist[-6:]

    def end(self):
        """Restore the previous level; returns the level that worked for dictation."""
        if self._orig is None:
            return self.vol
        set_volume(self._orig)
        print(f"mic volume restored to {round(self._orig * 100)}%")
        self._orig = None
        self._clear_file()
        return self.vol
