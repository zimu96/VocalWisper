"""Voice Activity Detection: energy based with an adaptive noise floor."""

import numpy as np


class AdaptiveVAD:
    def __init__(self, threshold: float = 0.01):
        self.min_threshold = threshold
        self.floor = None

    def reset(self):
        self.floor = None

    def is_speech(self, arr) -> bool:
        if arr is None or len(arr) == 0:
            return False
        rms = float(np.sqrt(np.mean(arr ** 2)))
        if self.floor is None:
            self.floor = rms
        if rms < self.floor:
            self.floor = 0.7 * self.floor + 0.3 * rms
        else:
            self.floor = self.floor * 1.02 + 1e-5  # rises slowly while somebody talks
        # a noisy room raises the bar, but never above what normal speech reaches
        threshold = max(self.min_threshold, min(self.floor * 2.5, 0.04))
        return rms >= threshold


def make_vad(threshold: float = 0.01):
    return AdaptiveVAD(threshold=threshold)
