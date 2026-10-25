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
    from vocalwisper import ducker, mic
    from vocalwisper.guicall import GuiCall
    duck = ducker.Ducker()
    micgain = mic.MicGain(cfg.get("mic_volume", 0.25))
    gui = GuiCall()
    import atexit, signal
    atexit.register(duck.restore)
    atexit.register(micgain.end)
    for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(_sig, lambda *a: (duck.restore(), micgain.end(), os._exit(0)))
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

    from PyQt6.QtCore import QTimer, QObject, pyqtSignal, pyqtSlot, Qt

    class _ToggleDispatcher(QObject):
        requested = pyqtSignal()

        def __init__(self):
            super().__init__()
            self.requested.connect(self._run, Qt.ConnectionType.QueuedConnection)

        @pyqtSlot()
        def _run(self):
            toggle()

    dispatcher = _ToggleDispatcher()
    _last_toggle = [0.0]

    def safe_toggle():
        import time
        now = time.time()
        if now - _last_toggle[0] < 0.6:
            print("debounce skip")
            return
        _last_toggle[0] = now
        print("safe_toggle called")
        dispatcher.requested.emit()
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
        vad_det.reset()
        ov.follow_focus = cfg.get("overlay_follow_focus", False)
        # remember the window dictation starts in: the text is written there
        state["pin"] = None if ov.follow_focus else winmod.capture_active_id()
        if cfg.get("mic_protect", True):
            micgain.begin(cfg.get("mic_volume", 0.25))
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
        if cfg.get("mic_protect", True):
            cfg["mic_volume"] = round(micgain.end(), 3)
            config.save(cfg)
        tray_icon.set_state("idle")
        ov.hide(instant=True)

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

    import queue
    import numpy as np
    work_q = queue.Queue()

    def type_pinned(text):
        pin = state.get("pin")
        if not pin:
            inj.type_text(text)
            return
        status, prev = winmod.activate_window_threadsafe(gui, pin)
        if status == "gone":
            state["pin"] = None   # window closed: fall back to the focused one
            bridge.message.emit("La finestra della dettatura è stata chiusa: scrivo dove c'è il cursore.")
        elif status == "ok" and prev and prev != pin:
            time.sleep(0.12)      # let KWin finish moving the focus
        inj.type_text(text)
        if status == "ok" and prev and prev != pin:
            winmod.activate_window_threadsafe(gui, prev)   # give the focus back

    def process_segment(arr):
        t_obj = get_transcriber()
        if t_obj is None:
            return
        try:
            text = t_obj.transcribe(arr.astype("float32"))
            print("transcribed:", repr(text))
            if text:
                type_pinned(text)
        except Exception as e:
            print("process error:", e)

    def transcribe_worker():
        # decoding runs here so the audio loop (and the pause indicator) never stalls
        while True:
            arr = work_q.get()
            if arr is not None and len(arr):
                process_segment(arr)

    threading.Thread(target=transcribe_worker, daemon=True).start()

    def record_loop():
        import collections
        sr = cfg["sample_rate"]
        hold_cut = 0.5     # silence that ends a phrase
        hold_ui = 0.3      # silence that shows the pause icon
        max_samples = int(6.0 * sr)
        preroll = collections.deque(maxlen=3)   # keep ~0.3 s before the first word
        seg = []
        speech_chunks = 0

        def flush():
            nonlocal seg, speech_chunks
            if seg and speech_chunks >= 2:
                work_q.put(np.concatenate(seg))
            seg = []
            speech_chunks = 0

        while state["recording"] and not state["stop"].is_set():
            time.sleep(0.1)
            arr = cap.read_all()
            if state["paused"]:
                flush()
                preroll.clear()
                ov.push_level(0.0)
                ov.set_paused(True)
                continue
            if arr is None or len(arr) == 0:
                continue
            ov.push_level(cap.rms(arr))
            now = time.time()
            sp = vad_det.is_speech(arr)
            if cfg.get("mic_protect", True):
                micgain.update(arr, sp, now)
            if sp:
                if not seg:
                    seg.extend(preroll)
                    preroll.clear()
                seg.append(arr)
                speech_chunks += 1
                last_speech[0] = now
                ov.set_paused(False)
                if sum(len(a) for a in seg) >= max_samples:
                    flush()
            else:
                if seg:
                    seg.append(arr)
                    if now - last_speech[0] >= hold_cut:
                        flush()
                else:
                    preroll.append(arr)
                if now - last_speech[0] >= hold_ui:
                    ov.set_paused(True)
        flush()

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
                if ev is not None:
                    ev.update(c.get("hotkey", cfg["hotkey"]))
                elif kde is not None:
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
            if ev is not None:
                ev.stop()
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

    # On Wayland read the keyboard devices directly: KDE GlobalAccel often
    # fails to grab the key when KWin and kglobalaccel versions differ.
    kde = None
    hk = None
    ev = None
    if os.environ.get("WAYLAND_DISPLAY"):
        from vocalwisper import evdev_hotkey
        ev = evdev_hotkey.EvdevHotkey(cfg["hotkey"], safe_toggle)
        if not ev.start():
            ev = None
    if ev is None and os.environ.get("WAYLAND_DISPLAY") and os.environ.get("KDE_FULL_SESSION"):
        from vocalwisper import kde_shortcut
        kde = kde_shortcut.KdeShortcut()
        if not kde.register(cfg["hotkey"], safe_toggle):
            kde = None
    if ev is None and kde is None:
        hk = hotkey.HotkeyListener(cfg["hotkey"], safe_toggle)
        hk.start()

    setup_deps()
    preload_transcriber()
    setup_typing()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
