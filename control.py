# -*- coding: utf-8 -*-
"""
Link between the bot and the Kingbot dashboard via GitHub REST API (dwtgraphics-sys/kingbot-syn).
  control/control.json  -> settings sent from the dashboard
  outbox/status.json    -> bot status for the dashboard
  outbox/screen.jpg     -> screenshot when requested
"""
import os, json, base64, datetime, urllib.request, urllib.error

from updater import local_version
from common import LOG_FILE, ROUTINES_FILE, load_json, log

GITHUB_OWNER = "dwtgraphics-sys"
GITHUB_REPO = "kingbot-syn"
TOKEN_FILE = r"C:\RisBot\github_token.txt"

ALLOWED_KEYS = {
    "running", "loop_minutes", "tasks", "run_now", "shot_request", "sent_at",
    "schedule", "probe_request", "daily_pause", "action_request", "freeze_until",
    "presets", "char_rotation", "keep_screen"
}

RESOURCES = {}
CITY = {}

def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")

def _get_token():
    if os.path.isfile(TOKEN_FILE):
        try:
            return open(TOKEN_FILE, "r", encoding="utf-8").read().strip()
        except Exception:
            pass
    return os.environ.get("KINGBOT_GH_TOKEN", "").strip()

_BAD_TOKEN = {"at": 0.0, "logged": 0.0}

def _gh_request(path, method="GET", payload=None):
    """GitHub contents API. The repo is public, so reads also work with no token
    (or with a revoked one); writes need a valid token in github_token.txt."""
    import time as _t
    token = _get_token()
    if _t.time() - _BAD_TOKEN["at"] < 600:
        token = ""          # token was refused lately: read anonymously
    if not token and method != "GET":
        return None
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    if method == "GET":
        url += f"?t={int(datetime.datetime.now().timestamp())}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Kingbot-VPS"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401 and token:
            _BAD_TOKEN["at"] = _t.time()
            if _t.time() - _BAD_TOKEN["logged"] > 600:
                _BAD_TOKEN["logged"] = _t.time()
                log("! GitHub token in github_token.txt was refused (401: expired or revoked). "
                    "Control is still read without it, but status cannot be sent - put a new token in github_token.txt.")
            if method == "GET":
                return _gh_request(path, method, payload)
            return None
        if e.code != 404 and not (e.code == 401 and method != "GET"):
            log(f"! GitHub API {method} {path} HTTP {e.code}")
        return None
    except Exception as e:
        log(f"! GitHub API {method} {path} error: {e}")
        return None

def _gh_put_bytes(path, raw_bytes, message):
    existing = _gh_request(path, "GET")
    sha = existing.get("sha") if isinstance(existing, dict) else None
    body = {
        "message": message,
        "content": base64.b64encode(raw_bytes).decode("ascii")
    }
    if sha:
        body["sha"] = sha
    return _gh_request(path, "PUT", body) is not None

def _smart_names():
    try:
        import smart
        return list(smart.SMART)
    except Exception:
        return []

def _opt_ok(v):
    if isinstance(v, (bool, int, float)):
        return True
    if isinstance(v, str):
        return len(v) <= 60
    if isinstance(v, list):
        return len(v) <= 12 and all(isinstance(x, (bool, int, float)) or (isinstance(x, str) and len(x) <= 30) for x in v)
    return False

def _clean_tasks(lst):
    tasks = []
    for t in lst or []:
        if isinstance(t, dict) and isinstance(t.get("routine"), str):
            try:
                times = max(1, min(int(t.get("times", 1) or 1), 10))
            except Exception:
                times = 1
            d = {"routine": t["routine"][:40], "times": times, "enabled": bool(t.get("enabled", True))}
            for k, v in list(t.items())[:30]:
                if k not in d and isinstance(k, str) and len(k) <= 30 and not k.startswith("_") and _opt_ok(v):
                    d[k] = v
            tasks.append(d)
    return tasks

def _hhmm(v):
    h, m = str(v).split(":")[:2]
    return f"{max(0, min(int(h), 23)):02d}:{max(0, min(int(m), 59)):02d}"

def _clean(d):
    out = {k: v for k, v in d.items() if k in ALLOWED_KEYS}
    out["running"] = bool(out.get("running", True))
    try:
        out["loop_minutes"] = max(5, min(int(out.get("loop_minutes", 60)), 24 * 60))
    except Exception:
        out["loop_minutes"] = 60
    out["tasks"] = _clean_tasks(out.get("tasks"))
    pr = out.get("presets") if isinstance(out.get("presets"), dict) else {}
    out["presets"] = {}
    for name, p in list(pr.items())[:30]:
        if isinstance(p, dict) and isinstance(p.get("tasks"), list):
            q = {"tasks": _clean_tasks(p["tasks"])}
            try:
                q["loop_minutes"] = max(5, min(int(p.get("loop_minutes") or out["loop_minutes"]), 24 * 60))
            except Exception:
                q["loop_minutes"] = out["loop_minutes"]
            out["presets"][str(name)[:40]] = q
    rot = out.get("char_rotation") if isinstance(out.get("char_rotation"), dict) else {}
    slots = []
    for x in (rot.get("slots") or [])[:10]:
        if isinstance(x, dict) and str(x.get("name") or "").strip():
            try:
                mins = max(10, min(int(x.get("minutes") or 120), 24 * 60))
            except Exception:
                mins = 120
            slots.append({
                "name": str(x["name"])[:48],
                "kingdom": str(x.get("kingdom") or "")[:40],
                "preset": str(x.get("preset") or "")[:40],
                "minutes": mins
            })
    out["char_rotation"] = {
        "enabled": bool(rot.get("enabled")) and bool(slots),
        "slots": slots,
        "collect_on_switch": bool(rot.get("collect_on_switch", True))
    }
    sc = out.get("schedule") or {}
    try:
        out["schedule"] = {
            "enabled": bool(sc.get("enabled")),
            "from": _hhmm(sc.get("from", "00:00")),
            "to": _hhmm(sc.get("to", "23:59")),
            "days": [int(d) for d in sc.get("days", list(range(7))) if 0 <= int(d) <= 6]
        }
    except Exception:
        out["schedule"] = {"enabled": False}
    return out

def in_schedule(settings, now=None):
    sc = (settings or {}).get("schedule") or {}
    if not sc.get("enabled"):
        return True
    now = now or datetime.datetime.now()
    day = (now.weekday() + 1) % 7
    cur = now.strftime("%H:%M")
    a, b = sc.get("from", "00:00"), sc.get("to", "23:59")
    if a <= b:
        return day in sc.get("days", []) and a <= cur <= b
    if cur >= a:
        return day in sc.get("days", [])
    return ((day - 1) % 7) in sc.get("days", []) and cur <= b

def take_screenshot(dest):
    import shutil, tempfile
    img, errors = None, []
    try:
        from PIL import ImageGrab
        from common import CURRENT_GAME, find_window, client_rect
        g = CURRENT_GAME[0]
        hwnd = g.hwnd if g is not None else find_window()
        if hwnd:
            x, y, w, h = client_rect(hwnd)
            if w > 100 and h > 100:
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
    except Exception as e:
        errors.append(f"game window: {e}")
    if img is None:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True)
        except Exception as e:
            errors.append(f"ImageGrab: {e}")
    if img is None:
        try:
            import pyautogui
            img = pyautogui.screenshot()
        except Exception as e:
            errors.append(f"pyautogui: {e}")
    if img is None:
        log("! Screenshot failed: " + " | ".join(errors))
        return None
    try:
        img.thumbnail((1400, 1400))
        tmp = os.path.join(tempfile.gettempdir(), "kingbot_screen.jpg")
        img.convert("RGB").save(tmp, "JPEG", quality=75)
        if dest != tmp:
            shutil.copyfile(tmp, dest)
        return dest
    except Exception as e:
        log(f"! Screenshot save failed: {e}")
        return None

class Control:
    def __init__(self):
        self.root = "github://dwtgraphics-sys/kingbot-syn" if _get_token() else None
        self.file = "control/control.json"
        self.data = None
        self.shot_done = None
        self.pending_change = False
        self.seen = False
        self.last = {}
        self._last_sha = None
        self._last_poll_ts = 0.0

    def poll(self):
        import time
        self.root = "github://dwtgraphics-sys/kingbot-syn" if _get_token() else None
        if not self.root:
            return None, False
        now_ts = time.time()
        if self.seen and (now_ts - self._last_poll_ts) < 4.0:
            return self.data, False
        self._last_poll_ts = now_ts
        first = not self.seen
        self.seen = True
        res = _gh_request("control/control.json", "GET")
        if not isinstance(res, dict) or "content" not in res:
            return self.data, False
        if res.get("sha") == self._last_sha and self.data is not None:
            return self.data, False
        try:
            raw = base64.b64decode(res["content"]).decode("utf-8-sig")
            d = _clean(json.loads(raw))
        except Exception:
            return self.data, False
        self._last_sha = res.get("sha")
        self.data = d
        sig = json.dumps(
            {k: v for k, v in d.items() if k not in ("shot_request", "action_request", "probe_request", "sent_at")},
            sort_keys=True, ensure_ascii=False, default=str
        )
        changed = (not first) and sig != getattr(self, "sig", None)
        self.sig = sig
        if changed:
            self.pending_change = True
        return d, changed

    def screenshot_if_asked(self):
        if not self.data or not self.root:
            return
        req = self.data.get("shot_request")
        if not req or req == self.shot_done:
            return
        self.shot_done = req
        import tempfile
        tmp_jpg = os.path.join(tempfile.gettempdir(), "kingbot_gh_screen.jpg")
        path = take_screenshot(tmp_jpg)
        if path and os.path.isfile(path):
            ok = _gh_put_bytes("outbox/screen.jpg", open(path, "rb").read(), "bot: screenshot")
            log("Screenshot uploaded to GitHub." if ok else "! GitHub screenshot upload failed.")
        else:
            log("! Screenshot failed.")

    def send_settings(self, changes):
        if not self.root:
            return False
        d = dict(self.data or {"running": True, "loop_minutes": 60, "tasks": []})
        d.update(changes)
        d["sent_at"] = _now()
        ok = _gh_put_bytes("control/control.json", json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8"), "bot: update settings")
        if ok:
            self.data = _clean(d)
        return ok

    def write_status(self, **info):
        if RESOURCES:
            info.setdefault("resources", dict(RESOURCES))
        if CITY:
            info.setdefault("city", dict(CITY))
        self.last = dict(info, version=local_version(), updated=_now())
        if not self.root:
            return
        try:
            with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
                tail = f.readlines()[-15:]
        except Exception:
            tail = []
        status = {
            "updated": _now(),
            "version": local_version(),
            "recorded": sorted(set(load_json(ROUTINES_FILE, {}).keys()) | set(_smart_names())),
            "settings_file": "control.json",
            "shot_request_done": self.shot_done,
            "log": [l.rstrip("\n") for l in tail],
        }
        status.update(info)
        _gh_put_bytes("outbox/status.json", json.dumps(status, ensure_ascii=False, indent=2).encode("utf-8"), "bot: status")
