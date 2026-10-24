"""Voice Activity Detection (energy-based, optional Silero)."""

import numpy as np

try:
    import onnxruntime as ort
    _HAS_ORT = True
except Exception:
    _HAS_ORT = False


class EnergyVAD:
    def __init__(self, threshold: float = 0.01):
        self.threshold = threshold

    def is_speech(self, arr) -> bool:
        if arr is None or len(arr) == 0:
            return False
        rms = float(np.sqrt(np.mean(arr ** 2)))
        return rms >= self.threshold


def make_vad(threshold: float = 0.01):
    # Silero optional; fallback to energy
    return EnergyVAD(threshold=threshold)
