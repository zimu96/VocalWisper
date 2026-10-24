#!/usr/bin/env bash
# VocalWisper installer: checks what is missing and installs it.
#
#   ./install.sh            install missing dependencies + menu entry + icon
#   ./install.sh --check    only report what is missing
#   ./install.sh --gpu      also build whisper.cpp for GPU (CUDA/Vulkan/ROCm)
#   ./install.sh --yes      do not ask for confirmation
set -u
cd "$(dirname "$(readlink -f "$0")")"
APP_DIR="$(pwd)"
PYTHON="${PYTHON:-python3}"

CHECK_ONLY=0; WITH_GPU=0; ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    --check) CHECK_ONLY=1 ;;
    --gpu) WITH_GPU=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a"; exit 1 ;;
  esac
done

ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
miss() { printf '  \033[31m✘\033[0m %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }
pyhas() { "$PYTHON" -c "import $1" >/dev/null 2>&1; }

confirm() {
  [ "$ASSUME_YES" = 1 ] && return 0
  read -r -p "$1 [S/n] " ans
  case "${ans:-s}" in [sSyY]*) return 0 ;; *) return 1 ;; esac
}

MISSING_PKGS=()      # system packages (pacman)
MISSING_PIP=()       # python packages (pip --user)

echo "== Python moduli =="
declare -A PYMOD=( [PyQt6.QtWidgets]="python-pyqt6" [numpy]="python-numpy" [PIL]="python-pillow" [pyaudio]="python-pyaudio" )
for mod in "${!PYMOD[@]}"; do
  if pyhas "$mod"; then ok "$mod"; else miss "$mod"; MISSING_PKGS+=("${PYMOD[$mod]}"); fi
done
if pyhas PyQt6.QtDBus; then ok "PyQt6.QtDBus"; else miss "PyQt6.QtDBus"; fi
if pyhas pywhispercpp; then ok "pywhispercpp (whisper.cpp)"; else miss "pywhispercpp (whisper.cpp)"; MISSING_PIP+=("pywhispercpp"); fi
if pyhas pynput; then ok "pynput (opzionale)"; else echo "  - pynput (opzionale, non installato)"; fi

echo "== Programmi di sistema =="
for pair in "pactl:libpulse" "wl-copy:wl-clipboard"; do
  bin="${pair%%:*}"; pkg="${pair##*:}"
  if have "$bin"; then ok "$bin"; else miss "$bin"; MISSING_PKGS+=("$pkg"); fi
done
if [ -n "${WAYLAND_DISPLAY:-}" ]; then
  if have ydotool && have ydotoold; then ok "ydotool (scrittura su Wayland)"; else miss "ydotool (scrittura su Wayland)"; MISSING_PKGS+=("ydotool"); fi
fi
if [ ! -e "$HOME/.local/share/applications/vocalwisper.desktop" ]; then miss "voce di menu"; else ok "voce di menu"; fi

[ "$CHECK_ONLY" = 1 ] && exit 0

# --- system packages -------------------------------------------------------
if [ "${#MISSING_PKGS[@]}" -gt 0 ]; then
  UNIQ=($(printf '%s\n' "${MISSING_PKGS[@]}" | sort -u))
  echo; echo "Pacchetti di sistema mancanti: ${UNIQ[*]}"
  if have pacman; then
    if confirm "Installarli con pacman (serve la password)?"; then
      sudo pacman -S --needed --noconfirm "${UNIQ[@]}" || echo "pacman: alcuni pacchetti non installati (es. python-pyaudio e' in AUR)"
    fi
  else
    echo "Installa manualmente i pacchetti equivalenti per la tua distribuzione."
  fi
fi

# pyaudio: AUR/pip fallback
if ! pyhas pyaudio; then
  echo "Installo pyaudio con pip..."
  "$PYTHON" -m pip install --user --break-system-packages pyaudio 2>/dev/null || \
    echo "  pyaudio non installato: serve 'portaudio' + compilatore (sudo pacman -S portaudio base-devel)"
fi

# --- python packages -------------------------------------------------------
for pkg in "${MISSING_PIP[@]}"; do
  echo "Installo $pkg con pip..."
  "$PYTHON" -m pip install --user --break-system-packages "$pkg" || echo "  installazione di $pkg non riuscita"
done

# --- ydotool daemon (user service) ----------------------------------------
if [ -n "${WAYLAND_DISPLAY:-}" ] && have ydotoold; then
  systemctl --user enable --now ydotool >/dev/null 2>&1 && ok "ydotool attivo" || echo "  avvia a mano: systemctl --user enable --now ydotool"
fi

# --- menu entry + icon -----------------------------------------------------
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$ICON_DIR" "$APPS_DIR"
cp -f assets/icon.png "$ICON_DIR/vocalwisper.png"
cat > "$APPS_DIR/vocalwisper.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=VocalWisper
Comment=Dettatura vocale locale con whisper.cpp
Exec=$APP_DIR/run.sh
Icon=vocalwisper
Terminal=false
Categories=Utility;Audio;
StartupNotify=false
StartupWMClass=vocalwisper
EOF
chmod +x run.sh toggle.sh build.sh install.sh 2>/dev/null
have update-desktop-database && update-desktop-database "$APPS_DIR" >/dev/null 2>&1
have gtk-update-icon-cache && gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1
ok "voce di menu e icona installate"

# --- GPU backend -----------------------------------------------------------
if [ "$WITH_GPU" = 1 ]; then
  echo "== Compilazione whisper.cpp per GPU =="
  ./build.sh auto
fi

echo; echo "Fatto. Avvia VocalWisper dal menu applicazioni oppure con ./run.sh"
