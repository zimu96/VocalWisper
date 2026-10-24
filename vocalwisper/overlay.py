"""Floating overlay with audio waveform animation (PyQt6)."""

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, pyqtSlot


class Overlay(QWidget):
    _level_sig = pyqtSignal(float)
    _paused_sig = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.WindowDoesNotAcceptFocus |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("VocalWisper Overlay")
        self.width_ = 200
        self.height_ = 44
        self.resize(self.width_, self.height_)
        self._alpha = 0.0
        self._target = 0.0
        self._visible = False
        self._paused = False
        self.on_pause = None
        self.on_stop = None
        self._manual_pause = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._target_pos = None
        self._pending_rect = None
        self._place_attempts = 0
        self._placed = False
        self._placing = False
        self._same_count = 0
        self._trying = False
        self._bars = 14
        self._levels = [0.0] * self._bars
        self._targets = [0.0] * self._bars
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)
        self._level_sig.connect(self._apply_level)
        self._paused_sig.connect(self._apply_paused)

        from .window import add_listener
        add_listener(self._on_active_rect)

    def set_paused(self, paused: bool):
        self._paused_sig.emit(paused)

    def reset_manual_pause(self):
        self._manual_pause = False

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        x = int(e.position().x())
        if x <= 30:
            self._manual_pause = not self._manual_pause
            self._paused = self._manual_pause
            self.update()
            if self.on_pause:
                self.on_pause(self._manual_pause)
        elif x >= self.width_ - 30:
            if self.on_stop:
                self.on_stop()
        e.accept()

    @pyqtSlot(bool)
    def _apply_paused(self, paused: bool):
        self._paused = paused
        self.update()

    def show(self):
        if not self._visible:
            self._visible = True
            self._placed = False
            self._placing = True  # keep the fade timer from hiding us meanwhile
            self._position()
            super().show()
            if self._kde_wayland():
                # stay invisible until KWin has moved us to the right spot
                self._place_attempts = 0
                self._same_count = 0
                QTimer.singleShot(20, self._try_place)
                return
            self._placing = False
        self._target = 1.0

    @staticmethod
    def _kde_wayland() -> bool:
        import os
        return bool(os.environ.get("WAYLAND_DISPLAY")) and bool(
            os.environ.get("KDE_FULL_SESSION") or
            "kde" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower())

    def _try_place(self):
        if self._trying:
            return
        if not self._visible or self._target_pos is None or self._placed:
            self._placing = False
            return
        self._trying = True
        try:
            self._try_place_once()
        finally:
            self._trying = False

    def _try_place_once(self):
        from .window import place_overlay
        x, y = self._target_pos
        try:
            res = place_overlay(x, y, self.width_, self.height_)
            if res == "same":
                self._same_count += 1
                if self._same_count >= 3:  # stable for a while: now it can fade in
                    self._placed = True
                    self._placing = False
                    self._target = 1.0
                    QTimer.singleShot(500, self._verify_place)
                    return
                self._place_attempts += 1
                QTimer.singleShot(60, self._try_place)
                return
            self._same_count = 0
        except Exception:
            pass
        self._place_attempts += 1
        if self._place_attempts < 25:
            QTimer.singleShot(30, self._try_place)
        else:
            self._placing = False
            self._target = 1.0

    def _verify_place(self):
        """Late check: KWin may re-place a window right after it is mapped."""
        if not self._visible or self._target_pos is None:
            return
        from .window import place_overlay
        x, y = self._target_pos
        try:
            place_overlay(x, y, self.width_, self.height_)
        except Exception:
            pass

    def _on_active_rect(self, rect):
        if not self._visible or not rect:
            return
        self._pending_rect = rect
        QTimer.singleShot(0, self._reposition)

    def _reposition(self):
        rect = self._pending_rect
        if not self._visible or not rect:
            return
        if not self._apply_rect(rect):
            return
        if self._kde_wayland():
            self._placed = False
            self._place_attempts = 0
            self._same_count = 0
            if not self._placing:
                QTimer.singleShot(0, self._try_place)

    def _position(self):
        from .window import active_window_rect
        self._apply_rect(active_window_rect())

    def _apply_rect(self, rect):
        screen = self.screen() or QApplication.primaryScreen()
        if rect:
            wx, wy, ww, wh = rect
            scr = QApplication.screenAt(QPoint(wx + ww // 2, wy + wh // 2)) or screen
            sg = scr.availableGeometry() if scr else None
            x = wx + (ww - self.width_) // 2
            y = wy + wh - self.height_ - 28
        else:
            sg = screen.availableGeometry() if screen else None
            if sg:
                x = sg.x() + (sg.width() - self.width_) // 2
                y = sg.y() + sg.height() - self.height_ - 70
            else:
                x, y = 0, 0
        if sg:
            x = max(sg.x() + 4, min(x, sg.x() + sg.width() - self.width_ - 4))
            y = max(sg.y() + 4, min(y, sg.y() + sg.height() - self.height_ - 4))
        if self._target_pos == (x, y):
            return False
        self._target_pos = (x, y)
        self.move(x, y)
        return True

    def hide(self, instant: bool = False):
        self._target = 0.0
        if instant:
            self._alpha = 0.0
            self._visible = False
            self._placed = False
            self._placing = False
            self._target_pos = None
            super().hide()

    def push_level(self, level: float):
        self._level_sig.emit(level)

    @pyqtSlot(float)
    def _apply_level(self, level: float):
        # scroll history left, add the newest sample on the right
        self._levels = self._levels[1:] + [0.0]
        self._targets = self._targets[1:] + [min(1.0, max(0.0, level * 8.0))]
        self.update()

    def _tick(self):
        step = 0.09
        if self._alpha < self._target:
            self._alpha = min(self._target, self._alpha + step)
        elif self._alpha > self._target:
            self._alpha = max(self._target, self._alpha - step)

        # ease bar heights toward their targets and let old targets decay
        for i in range(self._bars):
            self._targets[i] *= 0.97
            self._levels[i] += (self._targets[i] - self._levels[i]) * 0.35
            if self._levels[i] < 0.0:
                self._levels[i] = 0.0

        self.update()
        if (self._alpha <= 0.01 and self._target == 0.0 and self._visible
                and not self._placing):
            self._visible = False
            self._placed = False
            self._target_pos = None
            super().hide()

    def paintEvent(self, event):
        a = max(0.0, min(1.0, self._alpha))
        p = QPainter(self)
        if a <= 0.0:
            # invisible but still mapped, so KWin can find and move the window
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(self.rect(), QColor(0, 0, 0, 1))
            p.end()
            return
        ai = int(255 * a)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # opaque rounded background
        p.setBrush(QBrush(QColor(28, 28, 32, ai)))
        p.setPen(QPen(QColor(80, 80, 90, ai), 1.2))
        p.drawRoundedRect(2, 2, self.width_ - 4, self.height_ - 4, 10, 10)

        mid = self.height_ // 2
        color = QColor(255, 196, 0, ai) if self._paused else QColor(255, 59, 48, ai)

        # microphone icon (vector) or compact pause bars
        if self._paused:
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(11, mid - 7, 3, 14, 1, 1)
            p.drawRoundedRect(16, mid - 7, 3, 14, 1, 1)
        else:
            p.setPen(QPen(QColor(235, 235, 235, ai), 1.7))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(11, mid - 9, 8, 13, 4, 4)
            p.drawArc(8, mid - 5, 14, 12, 200 * 16, 140 * 16)
            p.drawLine(15, mid + 7, 15, mid + 9)
            p.drawLine(11, mid + 9, 19, mid + 9)

        # waveform bars (mirrored around the centre line)
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen)
        for i, lvl in enumerate(self._levels):
            x = 34 + i * 10
            h = max(1, int(lvl * (mid - 6)))
            p.drawRoundedRect(x, mid - h, 5, h * 2, 2, 2)

        # stop button (rounded square)
        p.setBrush(QBrush(QColor(235, 235, 235, ai)))
        p.drawRoundedRect(self.width_ - 24, mid - 5, 10, 10, 2, 2)
        p.end()
