"""Audio capture utilities (pyaudio)."""

import threading
import numpy as np

try:
    import pyaudio
    _HAS_PA = True
except Exception:
    _HAS_PA = False


class AudioCapture:
    def __init__(self, sample_rate: int = 16000, chunk: int = 1024):
        self.sr = sample_rate
        self.chunk = chunk
        self._pa = None
        self._stream = None
        self._buf = []
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        if not _HAS_PA:
            raise RuntimeError("pyaudio not available")
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sr,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self._cb,
        )
        self._running = True
        self._stream.start_stream()

    def _cb(self, in_data, frame_count, time_info, status):
        data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        with self._lock:
            self._buf.append(data)
        return (None, pyaudio.paContinue)

    def read_all(self) -> np.ndarray:
        with self._lock:
            if not self._buf:
                return np.zeros(0, dtype=np.float32)
            out = np.concatenate(self._buf)
            self._buf = []
            return out

    def rms(self, arr) -> float:
        if arr is None or len(arr) == 0:
            return 0.0
        return float(np.sqrt(np.mean(arr ** 2)))

    def stop(self):
        self._running = False
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        try:
            if self._pa:
                self._pa.terminate()
        except Exception:
            pass
        self._stream = None
        self._pa = None
        with self._lock:
            self._buf = []
