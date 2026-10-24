"""Whisper.cpp transcription wrapper (CUDA/CPU)."""

import logging
import os

logger = logging.getLogger(__name__)

try:
    from pywhispercpp.model import Model as _Model
    _HAS = True
except Exception as e:  # pragma: no cover
    _HAS = False
    _ERR = e


class Transcriber:
    def __init__(self, model_path: str, language: str = "auto", backend: str = "auto"):
        if not _HAS:
            raise RuntimeError(f"pywhispercpp not available: {_ERR}")
        self.model_path = model_path
        self.language = language if language and language != "auto" else None

        from . import gpu

        ctx_params = {}
        if backend == "cpu":
            ctx_params = {"use_gpu": False}
        elif backend == "cuda":
            ctx_params = {"use_gpu": True}
        elif backend == "auto":
            ctx_params = {"use_gpu": gpu.cuda_available()}

        kwargs = {}
        if self.language:
            kwargs["language"] = self.language
        if ctx_params:
            kwargs["context_params"] = ctx_params

        self.model = _Model(model_path, **kwargs)

    def transcribe(self, audio) -> str:
        """Transcribe a numpy float32 array (16kHz mono) -> text."""
        try:
            params = {}
            if self.language:
                params["language"] = self.language
            segments = self.model.transcribe(audio, **params)
        except Exception as e:
            logger.error("transcribe failed: %s", e)
            return ""
        texts = []
        for seg in segments or []:
            t = getattr(seg, "text", None)
            if t is None:
                t = str(seg)
            texts.append(t)
        out = " ".join(t.strip() for t in texts if t and t.strip()).strip()
        # Filter non-speech placeholders like [Musica], (blank), etc.
        import re
        if re.fullmatch(r"\[[^\]]*\]|\([^)]*\)", out):
            return ""
        return out
