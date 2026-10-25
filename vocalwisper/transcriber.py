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

        kwargs = {"n_threads": min(8, os.cpu_count() or 4)}
        if self.language:
            kwargs["language"] = self.language
        if ctx_params:
            kwargs["context_params"] = ctx_params

        self.model = _Model(model_path, **kwargs)

    def transcribe(self, audio) -> str:
        """Transcribe a numpy float32 array (16kHz mono) -> text."""
        import numpy as np

        from .cleanup import clean_repetitions, is_filler, is_hallucination

        if audio is None or len(audio) == 0:
            return ""
        # Do not even decode near-silence: whisper loves to invent sentences there.
        rms = float(np.sqrt(np.mean(np.asarray(audio, dtype=np.float32) ** 2)))
        if rms < 0.001:
            return ""

        try:
            params = {
                "temperature": 0.0,
                # no fallback to higher temperatures: that is where whisper
                # starts inventing whole sentences on silence or noise
                "temperature_inc": 0.0,
                "no_context": True,
                "suppress_blank": True,
                "suppress_nst": True,
            }
            if self.language:
                params["language"] = self.language
            segments = self.model.transcribe(audio, extract_probability=True, **params)
        except Exception as e:
            logger.error("transcribe failed: %s", e)
            return ""
        texts = []
        probs = []
        for seg in segments or []:
            t = getattr(seg, "text", None)
            if t is None:
                t = str(seg)
            t = t.strip()
            if not t:
                continue
            # Low confidence segments are usually noise or hallucinations.
            try:
                prob = float(getattr(seg, "probability", 1.0))
                if prob == prob and prob < 0.30:  # NaN-safe
                    logger.debug("drop low confidence segment (%.2f): %r", prob, t)
                    continue
                if prob == prob:
                    probs.append(prob)
            except Exception:
                pass
            texts.append(t)
        out = " ".join(texts).strip()
        out = clean_repetitions(out)
        # Filter non-speech placeholders like [Musica], (blank), etc.
        import re
        if not out or re.fullmatch(r"\[[^\]]*\]|\([^)]*\)|[\s.,!?…-]*", out):
            return ""
        if is_hallucination(out) or is_filler(out, min(probs) if probs else 1.0):
            return ""
        return out
