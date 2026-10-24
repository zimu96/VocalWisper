#!/usr/bin/env python3
"""VocalWisper entry point (PyQt6)."""

import argparse
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from vocalwisper import config, audio, transcriber, injector, overlay, tray, hotkey, downloader, vad


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimized", action="store_true")
    args = parser.parse_args()

    from vocalwisper import ipc as _ipc
    if _ipc.is_running():
        print("VocalWisper is already running")
        return

    cfg = config.load()

    app = QApplication(sys.argv)
    app.setApplicationName("vocalwisper")
    app.setApplicationDisplayName("VocalWisper")
    app.setDesktopFileName("vocalwisper")
    app.setQuitOnLastWindowClosed(False)
    # window icon
    from PyQt6.QtGui import QIcon
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    from vocalwisper import window as winmod
    winmod.start_tracker()
    from PyQt6.QtCore import QTimer as _QT
    _wake = _QT()
    _wake.timeout.connect(lambda: None)
    _wake.start(200)
    ov = overlay.Overlay()
    cap = audio.AudioCapture(sample_rate=cfg["sample_rate"])
    inj = injector.Injector()
    from vocalwisper import ducker
    duck = ducker.Ducker()
    import atexit, signal
    atexit.register(duck.restore)
    for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(_sig, lambda *a: (duck.restore(), os._exit(0)))
    tr = {"obj": None}
    vad_det = vad.make_vad(threshold=cfg["silence_threshold"])

    tr_lock = threading.Lock()

    def get_transcriber():
        with tr_lock:
            if tr["obj"] is None:
                try:
                    path = downloader.ensure_model(cfg["models_dir"], cfg["model"])
                    tr["obj"] = transcriber.Transcriber(path, language=cfg["language"], backend=cfg["backend"])
                    print("transcriber ready, model:", cfg["model"])
                except Exception as e:
                    print("transcriber init failed:", e)
                    return None
            return tr["obj"]

    def preload_transcriber():
        threading.Thread(target=get_transcriber, daemon=True).start()

    state = {"recording": False, "paused": False, "stop": threading.Event()}

    def toggle_autostart():
        cfg["autostart"] = not cfg.get("autostart", False)
        config.save(cfg)
        try:
            import sys, os
            from vocalwisper.autostart import set_autostart
            exec_path = sys.executable + " " + os.path.abspath(sys.argv[0])
            set_autostart(cfg["autostart"], exec_path, cfg.get("start_minimized", True))
        except Exception:
            pass
        print("autostart:", cfg["autostart"])

    def toggle_minimized():
        cfg["start_minimized"] = not cfg.get("start_minimized", True)
        config.save(cfg)
        print("start_minimized:", cfg["start_minimized"])

    from PyQt6.QtCore import QTimer
    _last_toggle = [0.0]
    def safe_toggle():
        import time
        now = time.time()
        if now - _last_toggle[0] < 0.6:
            print("debounce skip")
            return
        _last_toggle[0] = now
        print("safe_toggle called")
        QTimer.singleShot(0, toggle)
    def safe_autostart():
        QTimer.singleShot(0, toggle_autostart)
    def safe_minimized():
        QTimer.singleShot(0, toggle_minimized)

    tray_icon = tray.Tray(on_toggle=safe_toggle, on_settings=lambda: open_settings(), on_quit=lambda: quit_app(),
                          on_toggle_autostart=safe_autostart, on_toggle_minimized=safe_minimized)

    def toggle():
        if state["recording"]:
            stop_recording()
        else:
            start_recording()

    def start_recording():
        if state["recording"]:
            return
        print("start_recording")
        state["recording"] = True
        state["paused"] = False
        ov.reset_manual_pause()
        state["stop"].clear()
        if cfg.get("duck_enabled", True):
            duck.duck(cfg.get("duck_level", 0.2))
        try:
            cap.start()
        except Exception as e:
            print("audio start failed:", e)
            state["recording"] = False
            duck.restore()
            return
        tray_icon.set_state("recording")
        if not inj.can_type():
            tray_icon.notify("VocalWisper", "Impossibile scrivere nel campo: ydotool mancante o non attivo "
                             "(sudo pacman -S ydotool && systemctl --user enable --now ydotool)")
        ov.show()
        ov.set_paused(False)
        threading.Thread(target=record_loop, daemon=True).start()

    def stop_recording():
        if not state["recording"]:
            return
        state["recording"] = False
        state["paused"] = False
        state["stop"].set()
        cap.stop()
        duck.restore()
        tray_icon.set_state("idle")
        ov.hide(instant=True)

    seg_buf = []
    last_speech = [time.time()]

    def set_pause(paused):
        if not state["recording"]:
            return
        state["paused"] = bool(paused)
        last_speech[0] = time.time()
        ov.set_paused(state["paused"])
        if state["paused"]:
            duck.restore()
        elif cfg.get("duck_enabled", True):
            duck.duck(cfg.get("duck_level", 0.2))
        print("paused:", state["paused"])

    ov.on_pause = set_pause
    ov.on_stop = lambda: QTimer.singleShot(0, stop_recording)

    def process_segment(arr):
        if arr is None or len(arr) == 0:
            return
        t_obj = get_transcriber()
        if t_obj is None:
            return
        try:
            text = t_obj.transcribe(arr.astype("float32"))
            print("transcribed:", repr(text))
            if text:
                inj.type_text(text)
        except Exception as e:
            print("process error:", e)

    def record_loop():
        nonlocal seg_buf
        sr = cfg["sample_rate"]
        silence_hold = min(cfg["silence_hold"], 0.6)
        max_samples = int(4.0 * sr)
        while state["recording"] and not state["stop"].is_set():
            time.sleep(0.2)
            arr = cap.read_all()
            if state["paused"]:
                ov.push_level(0.0)
                ov.set_paused(True)
                continue
            if arr is None or len(arr) == 0:
                continue
            rms = cap.rms(arr)
            ov.push_level(rms)
            is_sp = vad_det.is_speech(arr)
            if is_sp:
                seg_buf.append(arr)
                last_speech[0] = time.time()
                ov.set_paused(False)
                if sum(len(a) for a in seg_buf) >= max_samples:
                    import numpy as np
                    process_segment(np.concatenate(seg_buf))
                    seg_buf = []
            else:
                # silence
                if seg_buf:
                    seg_buf.append(arr)
                if seg_buf and (time.time() - last_speech[0]) >= silence_hold:
                    # end of utterance
                    import numpy as np
                    full = np.concatenate(seg_buf)
                    process_segment(full)
                    seg_buf = []
                    ov.set_paused(True)
                else:
                    ov.set_paused(True)
        # final flush
        if seg_buf:
            import numpy as np
            full = np.concatenate(seg_buf)
            process_segment(full)
            seg_buf = []

    tr_sig = [(cfg["model"], cfg["language"], cfg["backend"])]

    from PyQt6.QtCore import QObject, pyqtSignal

    class _Bridge(QObject):
        installed = pyqtSignal(bool)
        message = pyqtSignal(str)

    bridge = _Bridge()
    bridge.message.connect(lambda t: tray_icon.notify("VocalWisper", t))
    bridge.installed.connect(lambda ok: tray_icon.notify(
        "VocalWisper",
        "ydotool installato: ora il testo viene scritto nel campo attivo." if ok
        else "Installazione di ydotool non riuscita. Installalo con: sudo pacman -S ydotool"))

    class _Restart(QObject):
        go = pyqtSignal()

    restarter = _Restart()
    restarter.go.connect(lambda: os.execv(sys.executable, [sys.executable] + sys.argv))

    def setup_deps():
        """Offer to install whisper.cpp bindings if they are missing."""
        from vocalwisper import deps
        if deps.available("pywhispercpp"):
            return
        from PyQt6.QtWidgets import QMessageBox
        ans = QMessageBox.question(
            None, "VocalWisper",
            "Manca pywhispercpp (il motore whisper.cpp).\nVuoi installarlo ora? (serve internet)")
        if ans != QMessageBox.StandardButton.Yes:
            return

        def work():
            if deps.pip_install("pywhispercpp"):
                restarter.go.emit()
            else:
                bridge.message.emit("Installazione di pywhispercpp non riuscita: "
                                    "pip install --user pywhispercpp")
        threading.Thread(target=work, daemon=True).start()

    def setup_typing():
        """Wayland: make sure ydotool is installed and its daemon is running."""
        if not os.environ.get("WAYLAND_DISPLAY"):
            return
        if injector.ydotool_installed():
            threading.Thread(target=injector.ensure_ydotool_daemon, daemon=True).start()
            return
        from PyQt6.QtWidgets import QMessageBox
        ans = QMessageBox.question(
            None, "VocalWisper",
            "Per scrivere il testo nel campo attivo su Wayland serve ydotool.\n"
            "Vuoi installarlo ora? (verrà chiesta la password)")
        if ans == QMessageBox.StandardButton.Yes:
            threading.Thread(target=lambda: bridge.installed.emit(injector.install_ydotool()),
                             daemon=True).start()

    def open_settings():
        from vocalwisper.settings import SettingsDialog
        def on_save(c):
            sig = (c["model"], c["language"], c["backend"])
            if sig != tr_sig[0]:
                tr_sig[0] = sig
                with tr_lock:
                    tr["obj"] = None
                preload_transcriber()
            try:
                if kde is not None:
                    kde.register(c.get("hotkey", cfg["hotkey"]), safe_toggle)
                elif hk is not None:
                    hk.update(c.get("hotkey", cfg["hotkey"]))
            except Exception:
                pass
        dlg = SettingsDialog(None, cfg, on_save)
        dlg.exec()

    def quit_app():
        stop_recording()
        try:
            if hk is not None:
                hk.stop()
            if kde is not None:
                kde.unregister()
        except Exception:
            pass
        try:
            ipc_server.stop()
        except Exception:
            pass
        try:
            winmod.stop_tracker()
        except Exception:
            pass
        tray_icon.stop()
        app.quit()

    # IPC socket for external hotkey (KDE Wayland custom shortcut)
    from vocalwisper import ipc
    ipc_server = ipc.IPCServer(safe_toggle)
    ipc_server.start()

    # Prefer KDE GlobalAccel on Wayland; pynput works on X11
    kde = None
    hk = None
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("KDE_FULL_SESSION"):
        from vocalwisper import kde_shortcut
        kde = kde_shortcut.KdeShortcut()
        if not kde.register(cfg["hotkey"], safe_toggle):
            kde = None
    if kde is None:
        hk = hotkey.HotkeyListener(cfg["hotkey"], safe_toggle)
        hk.start()

    setup_deps()
    preload_transcriber()
    setup_typing()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
