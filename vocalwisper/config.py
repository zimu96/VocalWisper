"""Persistent configuration for VocalWisper."""

import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/vocalwisper")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_MODELS_DIR = os.path.expanduser("~/.local/share/vocalwisper/models")

DEFAULTS = {
    "model": "base",
    "language": "it",
    "backend": "auto",          # auto | cuda | cpu
    "hotkey": "ctrl+shift+space",
    "autostart": False,
    "start_minimized": True,
    "models_dir": DEFAULT_MODELS_DIR,
    "sample_rate": 16000,
    "chunk_seconds": 2.0,
    "silence_threshold": 0.002,
    "silence_hold": 1.2,
    "duck_enabled": True,
    "duck_level": 0.2,          # volume (0..1) used while dictating
    "duck_mode": "target",
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
    except Exception:
        pass
    if cfg.get("duck_mode") != "target":
        # the "reduce" experiment is gone: the slider is the volume used while dictating
        cfg["duck_mode"] = "target"
        try:
            save(cfg)
        except Exception:
            pass
    os.makedirs(cfg["models_dir"], exist_ok=True)
    return cfg


def save(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
