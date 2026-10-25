"""Run a function on the Qt GUI thread from a worker thread and wait for its result."""

import threading

from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot


class GuiCall(QObject):
    _call = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._call.connect(self._run, Qt.ConnectionType.QueuedConnection)

    @pyqtSlot(object)
    def _run(self, job):
        try:
            job["res"] = job["fn"]()
        except Exception:
            job["res"] = None
        job["ev"].set()

    def run(self, fn, timeout: float = 3.0):
        job = {"fn": fn, "ev": threading.Event(), "res": None}
        self._call.emit(job)
        job["ev"].wait(timeout)
        return job["res"]
