# -*- coding: utf-8 -*-
"""
SEC-01: health telemetry, loop heartbeats and capped recovery for Kingbot.

Telemetry (status.json -> "health", shown in the dashboard):
    heartbeat_age   seconds since the main loop last showed progress (a log line, a wait, a click)
    process_state   starting | running | waiting | working | paused | sleeping | stalled | recovering
                    | backoff | recovery_capped  (+ any other state the bot reports)
    cpu_percent, memory_percent, disk_free_gb, disk_total_gb
    last_error      newest "! ..." log line (secrets hidden), with its age
    task / step     what the bot is doing and since when
    restarts_today, game_restarts_today, uptime_s, pid, encrypted
    level           ok | warn | critical, with `issues` (short codes the dashboard translates)

Recovery caps (stop endless restart loops):
    every automatic restart of the bot ("restart") or of the game ("game") is recorded in
    recovery_state.json (git-ignored). recovery_delay(kind) says how long to wait first:
      - 3+ recoveries in 30 minutes  -> back off 1, 2, 4 ... up to 30 minutes between them
      - the daily cap reached        -> at most one recovery every 30 minutes until the game day ends
    Caps: MAX_DAILY_RESTARTS (12) and MAX_DAILY_GAME_RESTARTS (8) in local_config.json.
    The bot is never left dead for good: after the cap it only slows down and says so.
"""
import os, sys, time, json, shutil, threading, datetime

import kb_paths
BASE = kb_paths.base_dir(__file__)   # SEC-04
STATE_FILE = os.path.join(BASE, "recovery_state.json")
STARTED = time.time()

WARN_AGE, CRIT_AGE = 150, 300           # heartbeat age (s) for warn / critical
WINDOW, BURST = 1800, 3                 # back-off: BURST recoveries inside WINDOW seconds
COOLDOWN = 1800                         # after the daily cap: one recovery per 30 minutes
DEFAULT_CAPS = {"restart": ("MAX_DAILY_RESTARTS", 12), "game": ("MAX_DAILY_GAME_RESTARTS", 8)}

_lock = threading.Lock()
_beat = {"at": time.time(), "task": "", "step": "", "step_at": time.time()}
_err = {"at": 0.0, "text": ""}
_state = {"process_state": "starting", "at": time.time(), "note": ""}
_clock = [None]                         # common.py: lambda: LAST_ACTIVITY[0]


# ------------------------------------------------------------------ heartbeat / state / errors
def set_clock(fn):
    _clock[0] = fn


def last_activity():
    try:
        if _clock[0]:
            return float(_clock[0]())
    except Exception:
        pass
    return _beat["at"]


def beat(task=None, step=None):
    now = time.time()
    with _lock:
        _beat["at"] = now
        if task is not None:
            _beat["task"] = str(task)[:80]
        if step is not None and str(step)[:80] != _beat["step"]:
            _beat["step"], _beat["step_at"] = str(step)[:80], now


def set_state(state, note=""):
    if not state:
        return
    with _lock:
        if _state["process_state"] != state or _state["note"] != note:
            _state.update(process_state=str(state)[:40], at=time.time(), note=str(note)[:160])


def record_error(text):
    try:
        import kb_secure
        text = kb_secure.redact(str(text))
    except Exception:
        text = str(text)
    with _lock:
        _err.update(at=time.time(), text=text.strip()[:240])


def heartbeat_age():
    return max(0, int(time.time() - last_activity()))


# ------------------------------------------------------------------ system metrics
_cpu_prev = [None]


def _cpu_mem_windows():
    import ctypes
    out = {}

    class MEM(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                   [(n, ctypes.c_ulonglong) for n in ("t", "a", "tp", "ap", "tv", "av", "ae")]
    m = MEM()
    m.dwLength = ctypes.sizeof(MEM)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        out["memory_percent"] = int(m.dwMemoryLoad)
    FT = ctypes.c_ulonglong
    idle, kern, user = FT(), FT(), FT()
    if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
        cur = (idle.value, kern.value + user.value)
        prev, _cpu_prev[0] = _cpu_prev[0], cur
        if prev and cur[1] > prev[1]:
            out["cpu_percent"] = max(0, min(100, round(100 * (1 - (cur[0] - prev[0]) / (cur[1] - prev[1])))))
    return out


def _cpu_mem_proc():
    out = {}
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    cur = (v[3] + (v[4] if len(v) > 4 else 0), sum(v))
    prev, _cpu_prev[0] = _cpu_prev[0], cur
    if prev and cur[1] > prev[1]:
        out["cpu_percent"] = max(0, min(100, round(100 * (1 - (cur[0] - prev[0]) / (cur[1] - prev[1])))))
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, val = line.split(":", 1)
            info[k] = int(val.split()[0])
    if info.get("MemTotal"):
        avail = info.get("MemAvailable", info.get("MemFree", 0))
        out["memory_percent"] = round(100 * (1 - avail / info["MemTotal"]))
    return out


def sys_metrics():
    """cpu_percent (since the previous call), memory_percent, disk_free_gb / disk_total_gb of the bot's drive."""
    out = {}
    try:
        out.update(_cpu_mem_windows() if os.name == "nt" else _cpu_mem_proc())
    except Exception:
        pass
    try:
        du = shutil.disk_usage(BASE)
        out["disk_free_gb"] = round(du.free / 1024 ** 3, 1)
        out["disk_total_gb"] = round(du.total / 1024 ** 3, 1)
    except Exception:
        pass
    return out


# ------------------------------------------------------------------ recovery caps
def _game_day():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")      # the game resets at 00:00 UTC


def _load_state():
    try:
        from kb_safeio import safe_load_json
        st = safe_load_json(STATE_FILE, {})
    except Exception:
        st = {}
    if not isinstance(st, dict) or st.get("day") != _game_day():
        st = {"day": _game_day(), "restart": [], "game": [], "notified": {}}
    for k in DEFAULT_CAPS:
        st.setdefault(k, [])
    st.setdefault("notified", {})
    return st


def _save_state(st):
    try:
        from kb_safeio import atomic_write_json
        atomic_write_json(STATE_FILE, st, make_backup=False)
    except Exception:
        pass


def cap(kind):
    key, default = DEFAULT_CAPS.get(kind, ("", 10))
    try:
        import server_config
        return max(1, min(int(server_config.get(key, default)), 200))
    except Exception:
        return default


def recovery_delay(kind, now=None):
    """(seconds to wait before the next automatic recovery of `kind`, reason). 0 = go ahead now."""
    now = now or time.time()
    st = _load_state()
    times = sorted(float(t) for t in st.get(kind, []))
    if not times:
        return 0, ""
    last = times[-1]
    if len(times) >= cap(kind):
        wait = COOLDOWN - (now - last)
        return (max(0, int(wait)), f"daily cap {cap(kind)} reached") if wait > 0 else (0, "")
    recent = [t for t in times if now - t < WINDOW]
    if len(recent) >= BURST:
        step = min(COOLDOWN, 60 * 2 ** (len(recent) - BURST))
        wait = step - (now - last)
        if wait > 0:
            return int(wait), f"{len(recent)} recoveries in {WINDOW // 60} min"
    return 0, ""


def record_recovery(kind, reason=""):
    st = _load_state()
    st[kind].append(round(time.time(), 1))
    st[kind] = st[kind][-200:]
    st.setdefault("last", {})[kind] = {"at": round(time.time(), 1), "reason": str(reason)[:160]}
    _save_state(st)
    return len(st[kind])


def counts():
    st = _load_state()
    return {k: len(st.get(k, [])) for k in DEFAULT_CAPS}


def notify_once(kind, key):
    """True the first time today for (kind, key) - so a capped recovery is announced once, not every loop."""
    st = _load_state()
    tag = f"{kind}:{key}"
    if st["notified"].get(tag):
        return False
    st["notified"][tag] = time.time()
    _save_state(st)
    return True


# ------------------------------------------------------------------ snapshot
def classify(h):
    """(level, issues) from a snapshot dict."""
    issues, level = [], "ok"

    def bump(lv, code):
        nonlocal level
        issues.append(code)
        if lv == "critical" or (lv == "warn" and level == "ok"):
            level = lv
    age, ps = h.get("heartbeat_age") or 0, h.get("process_state") or ""
    idle_states = ("paused", "sleeping", "frozen", "stopped")
    if ps in ("recovery_capped",):
        bump("critical", "recovery_capped")
    elif ps in ("stalled", "backoff", "recovering"):
        bump("critical" if ps == "stalled" and age >= CRIT_AGE else "warn", ps)
    if ps not in idle_states:
        if age >= CRIT_AGE and "stalled" not in issues:
            bump("critical", "no_heartbeat")
        elif age >= WARN_AGE and "stalled" not in issues:
            bump("warn", "slow_heartbeat")
    df = h.get("disk_free_gb")
    if isinstance(df, (int, float)):
        if df < 2:
            bump("critical", "disk_low")
        elif df < 5:
            bump("warn", "disk_low")
    if (h.get("memory_percent") or 0) >= 95:
        bump("warn", "memory_high")
    if (h.get("cpu_percent") or 0) >= 95:
        bump("warn", "cpu_high")
    le = h.get("last_error") or {}
    if le.get("age_s") is not None and le["age_s"] < 900:
        bump("warn", "recent_error")
    if h.get("restarts_today", 0) >= max(3, cap("restart") // 2):
        bump("warn", "many_restarts")
    if h.get("encrypted") is False:
        issues.append("unencrypted")                       # shown, but not a health problem by itself
    return level, issues


def snapshot(metrics=None):
    now = time.time()
    with _lock:
        b, e, s = dict(_beat), dict(_err), dict(_state)
    h = {
        "heartbeat_age": heartbeat_age(),
        "process_state": s["process_state"],
        "state_since": int(now - s["at"]),
        "task": b["task"],
        "step": b["step"],
        "step_age": int(now - b["step_at"]),
        "uptime_s": int(now - STARTED),
        "pid": os.getpid(),
        "last_error": ({"text": e["text"], "age_s": int(now - e["at"]),
                        "at": datetime.datetime.fromtimestamp(e["at"]).astimezone().isoformat(timespec="seconds")}
                       if e["at"] else None),
    }
    if s["note"]:
        h["note"] = s["note"]
    h.update(metrics if metrics is not None else sys_metrics())
    c = counts()
    h["restarts_today"], h["game_restarts_today"] = c.get("restart", 0), c.get("game", 0)
    try:
        import kb_secure
        h["encrypted"] = kb_secure.encryption_on()
    except Exception:
        pass
    h["level"], h["issues"] = classify(h)
    return h


def public(h):
    """What may be readable outside the encryption envelope: no error text, no task names."""
    keep = ("heartbeat_age", "process_state", "level", "issues", "cpu_percent", "memory_percent",
            "disk_free_gb", "disk_total_gb", "restarts_today", "game_restarts_today", "uptime_s", "encrypted")
    p = {k: h[k] for k in keep if k in h}
    le = h.get("last_error") or None
    if le:
        p["last_error_age_s"] = le.get("age_s")
    return p
