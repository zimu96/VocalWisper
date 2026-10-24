"""Audio ducking: lower the playback volume while dictating, then restore it."""

import json
import os
import re
import shutil
import subprocess

STATE_FILE = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "vocalwisper_duck_volume.json")


def _pactl(*args, timeout=5):
    try:
        return subprocess.run(["pactl", *args], capture_output=True, text=True,
                              timeout=timeout).stdout
    except Exception:
        return ""


def _sink_volume(name: str):
    m = re.search(r"(\d+)%", _pactl("get-sink-volume", name))
    return int(m.group(1)) / 100.0 if m else None


def _set_sink_volume(name: str, vol: float):
    _pactl("set-sink-volume", name, f"{max(0, round(vol * 100))}%")


def _active_sinks():
    """Default sink plus every sink that currently has playing streams."""
    names = []
    default = _pactl("get-default-sink").strip()
    if default:
        names.append(default)
    sinks = {}
    for line in _pactl("list", "short", "sinks").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            sinks[parts[0]] = parts[1]
    for line in _pactl("list", "short", "sink-inputs").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1] in sinks and sinks[parts[1]] not in names:
            names.append(sinks[parts[1]])
    return names


class Ducker:
    def __init__(self):
        self._saved = {}  # sink name -> original volume (0..1+)
        self.recover()

    def recover(self):
        """Restore the volume left lowered by a previous crashed run."""
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, vol in data.items():
                _set_sink_volume(name, float(vol))
        except Exception:
            pass
        self._clear_file()

    def _clear_file(self):
        try:
            os.unlink(STATE_FILE)
        except Exception:
            pass

    def duck(self, level: float = 0.2):
        """Read the current volume, save it and lower it to `level` (0..1)."""
        if self._saved or not shutil.which("pactl"):
            return  # already ducked: keep the original volume
        saved = {}
        for name in _active_sinks():
            vol = _sink_volume(name)
            if vol is not None:
                saved[name] = vol
        if not saved:
            return
        self._saved = saved
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(saved, f)
        except Exception:
            pass
        for name, vol in saved.items():
            _set_sink_volume(name, min(vol, level))  # never raise the volume

    def restore(self):
        if not self._saved:
            return
        for name, vol in self._saved.items():
            _set_sink_volume(name, vol)
        self._saved = {}
        self._clear_file()
