"""Settings dialog (PyQt6)."""

from PyQt6.QtWidgets import (QDialog, QFormLayout, QComboBox, QLineEdit,
                             QCheckBox, QPushButton, QHBoxLayout, QMessageBox, QLabel)
from PyQt6.QtCore import Qt

from . import config
from .autostart import set_autostart


class SettingsDialog(QDialog):
    def __init__(self, parent, cfg, on_save):
        super().__init__(parent)
        self.cfg = cfg
        self.on_save = on_save
        self.setWindowTitle("VocalWisper Settings")
        self.setMinimumWidth(520)
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.png")
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        layout = QFormLayout(self)

        self.model_cb = QComboBox()
        self.model_cb.addItems(["tiny", "base", "small", "medium", "large-v3-turbo"])
        self.model_cb.setCurrentText(cfg["model"])
        layout.addRow("Model:", self.model_cb)

        self.lang_cb = QComboBox()
        self.lang_cb.addItems(["auto", "en", "it", "es", "fr", "de"])
        self.lang_cb.setCurrentText(cfg["language"])
        layout.addRow("Language:", self.lang_cb)

        self.backend_cb = QComboBox()
        self.backend_cb.addItems(["auto", "cuda", "cpu"])
        self.backend_cb.setCurrentText(cfg["backend"])
        layout.addRow("Backend:", self.backend_cb)

        from . import gpu
        status = "CUDA: disponibile" if gpu.cuda_available() else "CUDA: non disponibile (CPU)"
        layout.addRow("Stato GPU:", QLabel(status))

        from PyQt6.QtWidgets import QHBoxLayout
        hk_row = QHBoxLayout()
        self.hotkey_edit = QLineEdit(cfg["hotkey"])
        hk_row.addWidget(self.hotkey_edit)
        capture_btn = QPushButton("Cattura")
        capture_btn.clicked.connect(self._capture_hotkey)
        hk_row.addWidget(capture_btn)
        layout.addRow("Hotkey:", hk_row)

        import os as _os
        if _os.environ.get("KDE_FULL_SESSION"):
            note = QLabel("Scorciatoia globale registrata automaticamente in KDE")
            note.setStyleSheet("color: gray")
            layout.addRow(note)

        self.autostart_cb = QCheckBox("Start at login")
        self.autostart_cb.setChecked(cfg["autostart"])
        layout.addRow(self.autostart_cb)

        self.min_cb = QCheckBox("Start minimized")
        self.min_cb.setChecked(cfg["start_minimized"])
        layout.addRow(self.min_cb)

        self.follow_cb = QCheckBox("Popup e scrittura seguono la finestra attiva (altrimenti restano nella finestra di partenza)")
        self.follow_cb.setChecked(cfg.get("overlay_follow_focus", False))
        layout.addRow(self.follow_cb)

        self.mic_cb = QCheckBox("Regola da solo il volume del microfono durante la dettatura (poi lo rimette com'era)")
        self.mic_cb.setChecked(cfg.get("mic_protect", True))
        layout.addRow(self.mic_cb)

        self.duck_cb = QCheckBox("Abbassa l'audio durante la dettatura")
        self.duck_cb.setChecked(cfg.get("duck_enabled", True))
        layout.addRow(self.duck_cb)

        from PyQt6.QtWidgets import QSlider, QHBoxLayout
        from PyQt6.QtCore import Qt as _Qt
        row = QHBoxLayout()
        self.duck_slider = QSlider(_Qt.Orientation.Horizontal)
        self.duck_slider.setRange(0, 100)
        self.duck_slider.setMinimumWidth(260)
        self.duck_slider.setValue(int(cfg.get("duck_level", 0.5) * 100))
        self.duck_label = QLabel(self._duck_text(self.duck_slider.value()))
        self.duck_label.setMinimumWidth(40)
        self.duck_slider.valueChanged.connect(lambda v: self.duck_label.setText(self._duck_text(v)))
        row.addWidget(self.duck_slider)
        row.addWidget(self.duck_label)
        layout.addRow("Volume durante la dettatura:", row)

        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btns.addWidget(save_btn)
        btns.addWidget(close_btn)
        layout.addRow(btns)
        self.adjustSize()

    @staticmethod
    def _duck_text(v: int) -> str:
        return f"{v}%"

    def _capture_hotkey(self):
        from .hotkey_capture import HotkeyCaptureDialog
        dlg = HotkeyCaptureDialog(self)
        if dlg.exec() and dlg.result_str:
            self.hotkey_edit.setText(dlg.result_str)

    def _apply(self):
        self.cfg["model"] = self.model_cb.currentText()
        self.cfg["language"] = self.lang_cb.currentText()
        self.cfg["backend"] = self.backend_cb.currentText()
        self.cfg["hotkey"] = self.hotkey_edit.text()
        self.cfg["autostart"] = self.autostart_cb.isChecked()
        self.cfg["start_minimized"] = self.min_cb.isChecked()
        self.cfg["overlay_follow_focus"] = self.follow_cb.isChecked()
        self.cfg["mic_protect"] = self.mic_cb.isChecked()
        self.cfg["duck_enabled"] = self.duck_cb.isChecked()
        self.cfg["duck_level"] = self.duck_slider.value() / 100.0
        config.save(self.cfg)
        try:
            import sys, os
            exec_path = sys.executable + " " + os.path.abspath(sys.argv[0])
            set_autostart(self.cfg["autostart"], exec_path, self.cfg["start_minimized"])
        except Exception:
            pass
        self.on_save(self.cfg)

    def _save(self):
        self._apply()
        QMessageBox.information(self, "Saved", "Settings saved.")
        self.close()

    def closeEvent(self, event):
        # Persist settings even when closing without pressing Save
        try:
            self._apply()
        except Exception:
            pass
        super().closeEvent(event)
