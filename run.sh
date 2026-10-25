#!/usr/bin/env bash
# Start VocalWisper (runs the installer first if something is missing).
cd "$(dirname "$(readlink -f "$0")")"
PYTHON=${PYTHON:-python3}

if ! $PYTHON - <<'PY' 2>/dev/null
import PyQt6.QtWidgets, PyQt6.QtDBus, numpy, PIL, pyaudio, pywhispercpp
PY
then
  echo "Mancano alcune dipendenze: avvio l'installer..."
  ./install.sh --yes
fi

exec $PYTHON -u main.py "$@"
