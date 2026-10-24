"""GPU detection helpers."""

import subprocess
import shutil


def cuda_available() -> bool:
    if not shutil.which("nvidia-smi"):
        return False
    try:
        r = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def vulkan_available() -> bool:
    return shutil.which("vulkaninfo") is not None
