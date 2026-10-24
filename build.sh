#!/usr/bin/env bash
# Build pywhispercpp with the desired backend.
# Usage: ./build.sh [auto|cuda|vulkan|rocm|cpu]
set -e
cd "$(dirname "$0")"

BACKEND="${1:-auto}"

if [ "$BACKEND" = "auto" ]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    BACKEND="cuda"
  elif command -v vulkaninfo >/dev/null 2>&1; then
    BACKEND="vulkan"
  elif command -v rocminfo >/dev/null 2>&1; then
    BACKEND="rocm"
  else
    BACKEND="cpu"
  fi
fi

echo "Building pywhispercpp backend: $BACKEND"

# Build dependencies
if command -v pacman >/dev/null 2>&1; then
  sudo pacman -S --needed --noconfirm git cmake ninja base-devel python-build python-installer python-wheel python-setuptools python-setuptools-scm 2>/dev/null || true
fi

WORKDIR="${XDG_CACHE_HOME:-$HOME/.cache}/vocalwisper-build"
rm -rf "$WORKDIR"
git clone --depth 1 https://github.com/Absadiki/pywhispercpp.git "$WORKDIR"
cd "$WORKDIR"
git submodule update --init --recursive

export CMAKE_ARGS="-DPython_EXECUTABLE=$(command -v python3)"
case "$BACKEND" in
  cuda)
    export GGML_CUDA=ON
    export PATH="/opt/cuda/bin:$PATH"
    export CUDACXX="${CUDACXX:-/opt/cuda/bin/nvcc}"
    ;;
  vulkan)
    export GGML_VULKAN=ON
    ;;
  rocm)
    export GGML_HIPBLAS=ON
    ;;
  cpu)
    ;;
  *)
    echo "Unknown backend: $BACKEND"; exit 1
    ;;
esac

python3 -m pip install --break-system-packages . 2>/dev/null || python3 -m pip install .

echo "Done. Installed pywhispercpp with $BACKEND support."
