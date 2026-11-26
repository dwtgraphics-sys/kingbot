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

import server_config
import kb_crypto

# v196: encryption. On when C:\RisBot\local_config.json has "KB_PASSPHRASE" (never uploaded to GitHub).
PUBLIC_STATUS = ("updated", "version", "state", "task", "server_id", "sys", "shot_request_done")
_ENC_WARN = {"at": 0.0}

def enc_key():
    p = server_config.get("KB_PASSPHRASE")
    return kb_crypto.derive(p) if p else None

def _seal_bytes(b):
    k = enc_key()
    return kb_crypto.seal_bytes(k, b) if k else b

def _seal_json(obj, public=()):
    k = enc_key()
    return kb_crypto.seal_json(k, obj, public) if k else obj

def _open_json(obj):
    """Decrypt a sealed envelope; None when it cannot be read here (no / wrong passphrase)."""
    if not kb_crypto.is_sealed(obj):
        return obj
    import time as _t
    k = enc_key()
    try:
        if not k:
            raise ValueError("it is encrypted but this server has no KB_PASSPHRASE in local_config.json")
        return kb_crypto.open_json(k, obj)
    except Exception as e:
        if _t.time() - _ENC_WARN["at"] > 900:
            _ENC_WARN["at"] = _t.time()
            log(f"! dashboard settings cannot be decrypted: {e}")
        return None
GITHUB_OWNER = "dwtgraphics-sys"
GITHUB_REPO = "kingbot-syn"
TOKEN_FILE = r"C:\RisBot\github_token.txt"

ALLOWED_KEYS = {
    "running", "loop_minutes", "tasks", "run_now", "shot_request", "sent_at",
    "schedule", "probe_request", "daily_pause", "action_request", "freeze_until",
    "presets", "char_rotation", "keep_screen", "stream",
    # v227: dashboard sections that were read by the bot but dropped here before
    "march_control", "commander_presets", "smart_schedule", "events_hunter", "merchant_tavern",
    "relogin_cooldown_min", "conduct_min", "schedule_profiles",
    "automation_rules", "sched_ranges",         # TASK-15, GUIDE-18
    "telegram_reset",                           # GUIDE-20
    "alerts",                                   # TASK-18
    "sign_out_schedule",                        # v258
    "plan"                                      # PLAN-01: solo | leader | solo_leader_bundle | group
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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIVE_FILE = os.path.join(BASE_DIR, "live_state.json")         # read by stream_bot.py
STREAM_FILE = os.path.join(BASE_DIR, "stream_status.json")    # written by stream_bot.py

def _raw_get(path):
    """Public read with no token, through raw.githubusercontent.com (no 60-an-hour API limit;
    the CDN may serve a copy up to a few minutes old). Same shape as the contents API."""
    import hashlib, time as _t
    url = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/{path}?t={int(_t.time())}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Kingbot-VPS", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read()
        return {"content": base64.b64encode(raw).decode("ascii"), "sha": hashlib.sha1(raw).hexdigest()}
    except urllib.error.HTTPError as e:
        if e.code != 404:
            log(f"! GitHub read {path} HTTP {e.code}")
    except Exception as e:
        log(f"! GitHub read {path} error: {e}")
    return None

_CPU_PREV = [None]

def _sys_stats():
    """v194: CPU % (since the previous status) and RAM % of this server, for the dashboard's server list."""
    import ctypes
    out = {}
    try:
        class MEM(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                       [(n, ctypes.c_ulonglong) for n in ("t", "a", "tp", "ap", "tv", "av", "ae")]
        m = MEM(); m.dwLength = ctypes.sizeof(MEM)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            out["ram"] = int(m.dwMemoryLoad)
        FT = ctypes.c_ulonglong
        idle, kern, user = FT(), FT(), FT()
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
            cur = (idle.value, kern.value + user.value)
            prev = _CPU_PREV[0]
            _CPU_PREV[0] = cur
            if prev and cur[1] > prev[1]:
                out["cpu"] = max(0, min(100, round(100 * (1 - (cur[0] - prev[0]) / (cur[1] - prev[1])))))
    except Exception:
        pass
    try:                                        # ADM-01: disk use of the bot's drive
        import shutil
        du = shutil.disk_usage(os.path.dirname(os.path.abspath(__file__)))
        out["disk"] = round(100 * du.used / du.total)
        out["disk_free_gb"] = round(du.free / 2 ** 30, 1)
    except Exception:
        pass
    return out

def _write_live(data=None, info=None):
    """What the dashboard wants + what the bot does now, for stream_bot.py (local file, no API calls)."""
    try:
        cur = load_json(LIVE_FILE, {}) if os.path.isfile(LIVE_FILE) else {}
        if data is not None:
            cur.update(running=bool(data.get("running", True)), freeze_until=data.get("freeze_until"),
                       stream=data.get("stream") if isinstance(data.get("stream"), dict) else {})
        if info:
            cur.update({k: info.get(k) for k in ("state", "task") if k in info})
        import time as _t
        cur["ts"] = _t.time()
        tmp = LIVE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False)
        os.replace(tmp, LIVE_FILE)
    except Exception:
        pass

def _gh_request(path, method="GET", payload=None):
    """GitHub contents API. The repo is public, so reads also work with no token
    (or with a revoked one); writes need a valid token in github_token.txt."""
    import time as _t
    token = _get_token()
    if _t.time() - _BAD_TOKEN["at"] < 600:
        token = ""          # token was refused lately: read anonymously
    if not token and method != "GET":
        return None
    if not token:
        return _raw_get(path)
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
    if isinstance(v, dict):                     # v252: small option maps (e.g. upgrade_troops.counts) were dropped silently
        return len(v) <= 16 and all(isinstance(k, str) and len(k) <= 30 and (isinstance(x, (bool, int, float)) or
                                    (isinstance(x, str) and len(x) <= 30)) for k, x in v.items())
    return False

DROPPED = {}                                    # routine -> option keys the bot could not accept (shown in status)

def _clean_tasks(lst):
    tasks = []
    for t in lst or []:
        if isinstance(t, dict) and isinstance(t.get("routine"), str):
            try:
                times = max(1, min(int(t.get("times", 1) or 1), 10))
            except Exception:
                times = 1
            d = {"routine": t["routine"][:40], "times": times, "enabled": bool(t.get("enabled", True))}
            bad = []
            for k, v in list(t.items())[:60]:
                if k in d or not isinstance(k, str) or k.startswith("_"):
                    continue
                if len(k) <= 30 and _opt_ok(v):
                    d[k] = v
                else:
                    bad.append(str(k)[:30])
            if len(t) > 60:
                bad.append(f"+{len(t) - 60} more")
            if bad:
                DROPPED[d["routine"]] = bad[:10]
            else:
                DROPPED.pop(d["routine"], None)
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
        self.root = "github://dwtgraphics-sys/kingbot-syn"
        self.file = server_config.path("control")
        self.data = None
        self.shot_done = None
        self.pending_change = False
        self.seen = False
        self.last = {}
        self._last_sha = None
        self._last_poll_ts = 0.0

    def poll(self):
        import time
        self.root = "github://dwtgraphics-sys/kingbot-syn"
        if not self.root:
            return None, False
        now_ts = time.time()
        if self.seen and (now_ts - self._last_poll_ts) < 4.0:
            return self.data, False
        self._last_poll_ts = now_ts
        first = not self.seen
        self.seen = True
        res = _gh_request(server_config.path("control"), "GET")
        if self.data is not None:
            _write_live(self.data)
        if not isinstance(res, dict) or "content" not in res:
            return self.data, False
        try:
            import kb_guard
            kb_guard.synced()
        except Exception:
            pass
        if res.get("sha") == self._last_sha and self.data is not None:
            return self.data, False
        try:
            raw = base64.b64decode(res["content"]).decode("utf-8-sig")
            d = _open_json(json.loads(raw))
            if d is None:
                return self.data, False
            d = _clean(d)
        except Exception:
            return self.data, False
        self._last_sha = res.get("sha")
        self.data = d
        _write_live(d)
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
        try:
            import kb_guard
        except Exception:
            kb_guard = None
        tmp_jpg = os.path.join(tempfile.gettempdir(), "kingbot_gh_screen.jpg")
        path = take_screenshot(tmp_jpg)
        if path and os.path.isfile(path):
            ok = _gh_put_bytes(server_config.path("screen"), _seal_bytes(open(path, "rb").read()), "bot: screenshot")
            log("Screenshot uploaded to GitHub." if ok else "! GitHub screenshot upload failed.")
        else:
            ok = False
            log("! Screenshot failed.")
        if kb_guard:
            kb_guard.command("shot", req, "screenshot", "done" if ok else "failed", "" if ok else "upload or capture failed")

    def upload_screen(self, message="bot: screenshot"):
        """TASK-09: upload the game picture now (the same file the dashboard shows as the latest screenshot)."""
        if not self.root:
            return False
        import tempfile
        path = take_screenshot(os.path.join(tempfile.gettempdir(), "kingbot_gh_screen.jpg"))
        if path and os.path.isfile(path):
            return _gh_put_bytes(server_config.path("screen"), _seal_bytes(open(path, "rb").read()), message)
        return False

    def send_settings(self, changes):
        if not self.root:
            return False
        d = dict(self.data or {"running": True, "loop_minutes": 60, "tasks": []})
        d.update(changes)
        d["sent_at"] = _now()
        ok = _gh_put_bytes(server_config.path("control"), json.dumps(_seal_json(d, ("sent_at",)), ensure_ascii=False, indent=2).encode("utf-8"), "bot: update settings")
        if ok:
            self.data = _clean(d)
        return ok

    def write_status(self, **info):
        if RESOURCES:
            info.setdefault("resources", dict(RESOURCES))
        if CITY:
            info.setdefault("city", dict(CITY))
        info.setdefault("server_id", server_config.server_id())
        info.setdefault("sys", _sys_stats())
        self.last = dict(info, version=local_version(), updated=_now())
        _write_live(None, info)
        st = load_json(STREAM_FILE, None) if os.path.isfile(STREAM_FILE) else None
        if isinstance(st, dict):
            info.setdefault("stream", st)
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
        try:                                    # v252: health + command acknowledgements for the dashboard
            import kb_guard
            d = self.data or {}
            status.update(kb_guard.snapshot(info.get("state"), d.get("freeze_until"), d.get("running", True)))
            if DROPPED:
                status["dropped_options"] = dict(DROPPED)
            import updater                              # ADM-02: version, backups, rollback hold, last updates
            status["update"] = updater.update_info()
            try:                                        # PLAN-01: tier + activities it skipped
                import plans
                status["plan"] = dict(plans.info(d), skipped=dict(CITY.get("plan_skipped") or {}))
            except Exception:
                pass
            from common import _scale_table             # v254: pictures re-learned for the current window size
            status["vision"] = {k: len([n for n in v if not n.startswith("_")]) for k, v in _scale_table().items()}
        except Exception:
            pass
        _gh_put_bytes(server_config.path("status"), json.dumps(_seal_json(status, PUBLIC_STATUS), ensure_ascii=False, indent=2).encode("utf-8"), "bot: status")
