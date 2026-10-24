"""Active window geometry helpers (KDE Wayland via KWin scripting, X11 fallback)."""

import os
import re
import shutil
import subprocess
import tempfile
import time

_cache = {"rect": None, "ts": 0.0}
_receiver = None
_busy = {"v": False}
_listeners = []
_tracker = {"id": -1, "name": "vocalwisper-tracker", "file": None}


def _parse_rect(value):
    if not value or ";" not in value:
        return None
    parts = value.split(";")
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (int(p) for p in parts)
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


def _handle_active(value):
    rect = _parse_rect(value)
    if not rect:
        return
    _cache["rect"] = rect
    _cache["ts"] = time.monotonic()
    for cb in list(_listeners):
        try:
            cb(rect)
        except Exception:
            pass


def add_listener(cb):
    if cb not in _listeners:
        _listeners.append(cb)


def remove_listener(cb):
    if cb in _listeners:
        _listeners.remove(cb)


def _ensure_receiver():
    """Register a DBus receiver used by the KWin scripts to send results back."""
    global _receiver
    if _receiver is not None:
        return _receiver
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QObject, pyqtSlot
        from PyQt6.QtDBus import QDBusConnection

        if QApplication.instance() is None:
            return None
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return None

        class _Receiver(QObject):
            def __init__(self):
                super().__init__()
                self.value = None

            @pyqtSlot(str)
            def result(self, s):
                self.value = s

            @pyqtSlot(str)
            def active(self, s):
                _handle_active(s)

        r = _Receiver()
        if not bus.registerObject("/", r, QDBusConnection.RegisterOption.ExportAllSlots):
            return None
        _receiver = (bus, r, bus.baseService())
        return _receiver
    except Exception:
        return None


def _on_gui_thread() -> bool:
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QThread

        app = QApplication.instance()
        return app is not None and QThread.currentThread() is app.thread()
    except Exception:
        return False


def _kde_session() -> bool:
    return bool(os.environ.get("KDE_FULL_SESSION") or
                "kde" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower())


def _run_kwin_script(body: str, timeout_ms: int = 600):
    """Run a one-shot KWin script; `body` must call the DBus 'result' callback."""
    if not _kde_session() or not _on_gui_thread() or _busy["v"]:
        return None
    rec = _ensure_receiver()
    if not rec:
        return None
    bus, r, svc = rec
    _busy["v"] = True
    try:
        from PyQt6.QtCore import QEventLoop, QTimer
        from PyQt6.QtDBus import QDBusMessage

        script = "try {\n" + body + \
            '\n} catch (e) { callDBus("%s", "/", "", "result", "error:" + String(e)); }\n' % svc
        f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False)
        f.write(script)
        f.close()
        name = f"vocalwisper-{os.getpid()}-{time.time_ns()}"
        script_id = -1
        try:
            msg = QDBusMessage.createMethodCall(
                "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "loadScript")
            msg.setArguments([f.name, name])
            reply = bus.call(msg)
            if (reply.type() != QDBusMessage.MessageType.ReplyMessage or
                    not reply.arguments()):
                return None
            script_id = int(reply.arguments()[0])

            msg = QDBusMessage.createMethodCall(
                "org.kde.KWin", f"/Scripting/Script{script_id}",
                "org.kde.kwin.Script", "run")
            bus.call(msg)

            r.value = None
            loop = QEventLoop()
            QTimer.singleShot(timeout_ms, loop.quit)
            poll = QTimer()
            poll.timeout.connect(lambda: loop.quit() if r.value is not None else None)
            poll.start(15)
            loop.exec()
            poll.stop()
            return r.value
        finally:
            _busy["v"] = False
            if script_id >= 0:
                try:
                    bus.call(QDBusMessage.createMethodCall(
                        "org.kde.KWin", f"/Scripting/Script{script_id}",
                        "org.kde.kwin.Script", "stop"))
                except Exception:
                    pass
            try:
                msg = QDBusMessage.createMethodCall(
                    "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "unloadScript")
                msg.setArguments([name])
                bus.call(msg)
            except Exception:
                pass
            try:
                os.unlink(f.name)
            except Exception:
                pass
    except Exception:
        _busy["v"] = False
        return None


def _kwin_script_rect():
    """Ask a one-shot KWin script for the active window geometry."""
    rec = _ensure_receiver()
    if not rec:
        return None
    svc = rec[2]
    body = '''
  var w = workspace.activeWindow;
  if (!w) { callDBus("%s", "/", "", "result", "none"); }
  else {
    var cls = String(w.resourceClass || "");
    if (cls.indexOf("vocalwisper") >= 0) {
      callDBus("%s", "/", "", "result", "overlay");
    } else {
      var g = w.frameGeometry;
      callDBus("%s", "/", "", "result",
               Math.round(g.x) + ";" + Math.round(g.y) + ";" +
               Math.round(g.width) + ";" + Math.round(g.height));
    }
  }
''' % (svc, svc, svc)
    value = _run_kwin_script(body)
    if value and ";" in value:
        parts = value.split(";")
        if len(parts) == 4:
            try:
                x, y, w, h = (int(p) for p in parts)
            except ValueError:
                return None
            if w > 0 and h > 0:
                _cache["rect"] = (x, y, w, h)
                _cache["ts"] = time.monotonic()
                return (x, y, w, h)
    return None


def place_overlay(x: int, y: int, w: int, h: int):
    """Move the overlay with KWin (Wayland clients cannot move themselves).

    Returns "same" when it was already in place, "moved", "notfound" or None.
    """
    rec = _ensure_receiver()
    if not rec:
        return False
    svc = rec[2]
    body = '''
  var list = workspace.windowList();
  var moved = false;
  var same = false;
  for (var i = 0; i < list.length; i++) {
    var w = list[i];
    var cls = String(w.resourceClass || "");
    var cap = String(w.caption || "");
    if (cls.indexOf("vocalwisper") >= 0 && cap.indexOf("VocalWisper Overlay") >= 0) {
      var g0 = w.frameGeometry;
      same = (Math.round(g0.x) == %d && Math.round(g0.y) == %d);
      w.frameGeometry = {x: %d, y: %d, width: %d, height: %d};
      w.keepAbove = true;
      w.skipTaskbar = true;
      w.skipPager = true;
      workspace.raiseWindow(w);
      moved = true;
    }
  }
  callDBus(SVC, "/", "", "result", moved ? (same ? "same" : "moved") : "notfound");
'''.replace("SVC", '"%s"' % svc) % (x, y, x, y, w, h)
    return _run_kwin_script(body)


def start_tracker() -> bool:
    """Load a persistent KWin script that reports the active window geometry."""
    if not _kde_session() or not _on_gui_thread():
        return False
    rec = _ensure_receiver()
    if not rec:
        return False
    bus, r, svc = rec
    try:
        from PyQt6.QtDBus import QDBusMessage

        # Remove a stale instance from a previous run
        try:
            msg = QDBusMessage.createMethodCall(
                "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "unloadScript")
            msg.setArguments([_tracker["name"]])
            bus.call(msg)
        except Exception:
            pass

        script = '''
var current = null;
var lastReal = null;
function isOverlay(w) {
  return String(w.resourceClass || "").indexOf("vocalwisper") >= 0 &&
         String(w.caption || "").indexOf("VocalWisper Overlay") >= 0;
}
function sendRect(w) {
  if (!w) return;
  var cls = String(w.resourceClass || "");
  if (cls.indexOf("vocalwisper") >= 0) return;
  var g = w.frameGeometry;
  callDBus("SVC", "/", "", "active",
           Math.round(g.x) + ";" + Math.round(g.y) + ";" +
           Math.round(g.width) + ";" + Math.round(g.height));
}
function sendCurrent() { sendRect(current); }
function attach() {
  var w = workspace.activeWindow;
  if (w && isOverlay(w)) {
    // the overlay must never keep keyboard focus: give it back
    if (lastReal && workspace.windowList().indexOf(lastReal) >= 0) {
      workspace.activeWindow = lastReal;
    }
    return;
  }
  if (current) {
    try { current.frameGeometryChanged.disconnect(sendCurrent); } catch (e) {}
  }
  current = w;
  if (w) lastReal = w;
  if (current) {
    try { current.frameGeometryChanged.connect(sendCurrent); } catch (e) {}
  }
  sendCurrent();
}
workspace.windowActivated.connect(attach);
attach();
'''.replace("SVC", svc)
        path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
                            "vocalwisper_tracker.js")
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)

        msg = QDBusMessage.createMethodCall(
            "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "loadScript")
        msg.setArguments([path, _tracker["name"]])
        reply = bus.call(msg)
        if (reply.type() != QDBusMessage.MessageType.ReplyMessage or
                not reply.arguments()):
            return False
        sid = int(reply.arguments()[0])
        if sid < 0:
            return False
        msg = QDBusMessage.createMethodCall(
            "org.kde.KWin", f"/Scripting/Script{sid}",
            "org.kde.kwin.Script", "run")
        bus.call(msg)
        _tracker["id"] = sid
        _tracker["file"] = path
        return True
    except Exception:
        return False


def stop_tracker():
    if _tracker["id"] < 0:
        return
    rec = _ensure_receiver()
    if not rec:
        return
    bus = rec[0]
    try:
        from PyQt6.QtDBus import QDBusMessage
        bus.call(QDBusMessage.createMethodCall(
            "org.kde.KWin", f"/Scripting/Script{_tracker['id']}",
            "org.kde.kwin.Script", "stop"))
        msg = QDBusMessage.createMethodCall(
            "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "unloadScript")
        msg.setArguments([_tracker["name"]])
        bus.call(msg)
    except Exception:
        pass
    _tracker["id"] = -1


def _kdotool_rect():
    try:
        r = subprocess.run(
            ["kdotool", "getactivewindow", "getwindowgeometry"],
            capture_output=True, text=True, timeout=2)
        if r.returncode != 0:
            return None
        pos = re.search(r"Position:\s*(-?\d+),(-?\d+)", r.stdout)
        geo = re.search(r"Geometry:\s*(\d+)x(\d+)", r.stdout)
        if pos and geo:
            return (int(pos.group(1)), int(pos.group(2)),
                    int(geo.group(1)), int(geo.group(2)))
    except Exception:
        pass
    return None


def _xdotool_rect():
    try:
        r = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowgeometry", "--shell"],
            capture_output=True, text=True, timeout=2)
        if r.returncode != 0:
            return None
        vals = {}
        for line in r.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
        if all(k in vals for k in ("X", "Y", "WIDTH", "HEIGHT")):
            return (int(vals["X"]), int(vals["Y"]),
                    int(vals["WIDTH"]), int(vals["HEIGHT"]))
    except Exception:
        pass
    return None


def active_window_rect():
    """Return (x, y, w, h) of the active window, or None."""
    now = time.monotonic()
    ttl = 2.0 if _tracker["id"] >= 0 else 0.4
    if _cache["rect"] and now - _cache["ts"] < ttl:
        return _cache["rect"]
    rect = _kwin_script_rect()
    if rect:
        return rect
    if shutil.which("kdotool"):
        rect = _kdotool_rect()
        if rect:
            return rect
    if shutil.which("xdotool") and os.environ.get("DISPLAY"):
        rect = _xdotool_rect()
        if rect:
            return rect
    return _cache["rect"]
