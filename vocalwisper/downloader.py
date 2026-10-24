"""Download whisper.cpp ggml models from Hugging Face."""

import os
import urllib.request

REPO = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
MODELS = {
    "tiny": ("ggml-tiny.bin", 74 * 1024 * 1024),
    "base": ("ggml-base.bin", 141 * 1024 * 1024),
    "small": ("ggml-small.bin", 465 * 1024 * 1024),
}


def model_path(models_dir: str, name: str) -> str:
    fname = MODELS[name][0] if name in MODELS else f"ggml-{name}.bin"
    return os.path.join(models_dir, "whispercpp", fname)


def ensure_model(models_dir: str, name: str, progress_cb=None) -> str:
    path = model_path(models_dir, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 1024 * 1024:
        return path
    fname = os.path.basename(path)
    url = f"{REPO}/{fname}"
    tmp = path + ".tmp"
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = r.read(1024 * 64)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress_cb and total:
                progress_cb(done / total)
    os.replace(tmp, path)
    return path
