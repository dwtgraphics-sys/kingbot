"""v360: Windows OCR inside the bot (pywinrt) instead of starting PowerShell for every read.

Same engine as ocr.ps1 / ocr_boxes.ps1 / ocr_words.ps1 (Windows.Media.Ocr, English first), but no PowerShell
start-up per read (that took ~1 s of CPU each time). run(cmd, **kw) is a drop-in for subprocess.run on those three
scripts: it answers in the same text format, and falls back to the real PowerShell call when pywinrt is missing
or fails. The packages are installed once in the background (pip, needs internet on the server).
"""
import os
import subprocess
import sys
import threading
import time

PKGS = ["winrt-runtime", "winrt-Windows.Media.Ocr", "winrt-Windows.Graphics.Imaging", "winrt-Windows.Storage.Streams",
        "winrt-Windows.Globalization", "winrt-Windows.Foundation", "winrt-Windows.Foundation.Collections"]
_S = {"engine": None, "ok": None, "install_at": 0.0, "fails": 0, "said": False}
_LOCK = threading.Lock()


def _log(msg):
    try:
        from common import log
        log(msg)
    except Exception:
        pass


def _install_bg():
    if time.time() - _S["install_at"] < 12 * 3600:
        return
    _S["install_at"] = time.time()

    def go():
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check"] + PKGS,
                               capture_output=True, timeout=900, creationflags=0x08000000)
            if r.returncode == 0:
                _S["ok"] = None                     # try the import again on the next read
                _log("  OCR: in-process Windows OCR installed (pywinrt)")
            else:
                _log("  ! OCR: pywinrt install failed - PowerShell OCR stays in use: "
                     + (r.stderr or b"").decode("utf-8", "replace")[-200:])
        except Exception as e:
            _log(f"  ! OCR: pywinrt install failed: {e!r}")
    threading.Thread(target=go, daemon=True).start()


def _engine():
    if _S["ok"] is False:
        return None
    if _S["engine"] is not None:
        return _S["engine"]
    try:
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
    except Exception:
        _S["ok"] = False
        _install_bg()
        return None
    eng = None
    try:
        eng = OcrEngine.try_create_from_language(Language("en-US"))
    except Exception:
        eng = None
    if eng is None:
        try:
            for lg in OcrEngine.available_recognizer_languages:
                if str(lg.language_tag).lower().startswith("en"):
                    eng = OcrEngine.try_create_from_language(lg)
                    if eng is not None:
                        break
        except Exception:
            eng = None
    if eng is None:
        try:
            eng = OcrEngine.try_create_from_user_profile_languages()
        except Exception:
            eng = None
    if eng is None:
        _S["ok"] = False
        return None
    _S["engine"], _S["ok"] = eng, True
    return eng


def _bitmap(img_bgr):
    import cv2
    from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
    from winrt.windows.storage.streams import DataWriter
    bgra = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2BGRA) if img_bgr.ndim == 3 else cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGRA)
    h, w = bgra.shape[:2]
    dw = DataWriter()
    data = bgra.tobytes()
    try:
        dw.write_bytes(data)
    except TypeError:
        dw.write_bytes(list(data))
    buf = dw.detach_buffer()
    try:
        return SoftwareBitmap.create_copy_from_buffer(buf, BitmapPixelFormat.BGRA8, w, h, BitmapAlphaMode.PREMULTIPLIED)
    except TypeError:
        return SoftwareBitmap.create_copy_from_buffer(buf, BitmapPixelFormat.BGRA8, w, h)


def lines(img_bgr):
    """[(text, [(x1, y1, x2, y2, word), ...]), ...] or None when in-process OCR is not available."""
    eng = _engine()
    if eng is None:
        return None
    import asyncio
    with _LOCK:
        try:
            sb = _bitmap(img_bgr)

            async def rec():
                return await eng.recognize_async(sb)
            loop = asyncio.new_event_loop()
            try:
                res = loop.run_until_complete(rec())
            finally:
                loop.close()
            out = []
            for ln in res.lines:
                words = []
                for wd in ln.words:
                    r = wd.bounding_rect
                    words.append((int(r.x), int(r.y), int(r.x + r.width), int(r.y + r.height), wd.text))
                out.append((ln.text, words))
            if not _S["said"]:
                _S["said"] = True
                _log("  OCR: reading text inside the bot (no PowerShell)")
            _S["fails"] = 0
            return out
        except Exception as e:
            _S["fails"] += 1
            if _S["fails"] >= 5:
                _S["ok"] = False                    # broken here - stay on PowerShell for this run
                _log(f"  ! OCR: in-process OCR failed 5 times ({e!r}) - PowerShell OCR from now on")
            return None


def _format(script, res):
    if script == "ocr.ps1":
        return "\n".join(t for t, _ in res)
    if script == "ocr_boxes.ps1":
        rows = []
        for t, ws in res:
            if ws:
                rows.append("{}|{}|{}|{}|{}".format(min(w[0] for w in ws), min(w[1] for w in ws),
                                                    max(w[2] for w in ws), max(w[3] for w in ws), t))
        return "\n".join(rows)
    rows = []                                           # ocr_words.ps1
    for i, (t, ws) in enumerate(res):
        for x1, y1, x2, y2, wt in ws:
            rows.append(f"{x1}|{y1}|{x2}|{y2}|{i}|{wt}")
    return "\n".join(rows)


def run(cmd, **kw):
    """subprocess.run for ['powershell', ..., '<ocr script>.ps1', '<image path>']: answered in-process when possible."""
    try:
        script = next((os.path.basename(a) for a in cmd if str(a).lower().endswith(".ps1")), "")
        if script in ("ocr.ps1", "ocr_boxes.ps1", "ocr_words.ps1"):
            import cv2
            img = cv2.imread(str(cmd[-1]))
            res = lines(img) if img is not None else None
            if res is not None:
                txt = _format(script, res) + ("\n" if res else "")
                text_mode = bool(kw.get("encoding") or kw.get("text") or kw.get("universal_newlines"))
                return subprocess.CompletedProcess(cmd, 0, txt if text_mode else txt.encode("utf-8"),
                                                   "" if text_mode else b"")
    except Exception:
        pass
    return subprocess.run(cmd, **kw)
