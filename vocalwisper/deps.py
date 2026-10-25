"""Runtime dependency helpers (install what is missing)."""

import importlib.util
import subprocess
import sys


def available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def pip_install(package: str) -> bool:
    for extra in (["--break-system-packages"], []):
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", *extra, package],
                               capture_output=True, timeout=900)
            if r.returncode == 0:
                return True
        except Exception:
            pass
    return False
