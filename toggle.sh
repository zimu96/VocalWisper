#!/usr/bin/env bash
# Toggle VocalWisper dictation (usable as a KDE custom shortcut command)
python3 - <<'PY'
import os, socket
path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "vocalwisper.sock")
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    s.sendall(b"toggle")
    s.close()
except Exception as e:
    print("VocalWisper not running or socket unavailable:", e)
PY
