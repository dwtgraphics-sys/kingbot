"""BRAIN-01: the bot's memory of its own failures.

Every failure gets a signature (task + kind + message without numbers + the screen it was on), so the
same fault is counted as ONE incident instead of hundreds of log lines.  Each incident keeps:
  count, first / last time, the last log lines, a screenshot of the game, the fixes that were tried and
  whether they worked, and the admin's decision (solved / ignored / a note the bot can learn from).

Files:
  brain.json                                   on the server (survives restarts and updates)
  servers/<id>/outbox/brain.json               uploaded copy the admin page «🧠 أعطال البوت» reads
  servers/<id>/outbox/incidents/<key>.jpg      the screenshot of an incident

The admin's decisions come back in control.json  "brain_notes": {key: {"status": "solved|ignored|open", "note": "..."}}.
Phase 1 records and reports; phase 2 (fix playbook) uses note_fix()/best_fix() to try the fix that worked before.
"""
import collections
import datetime
import hashlib
import json
import os
import re
import tempfile
import threading
import time

from common import BASE, LOG_HOOKS, log

FILE = os.path.join(BASE, "brain.json")
MAX_INCIDENTS = 300
SHOT_AT = (1, 3, 10, 25, 100, 250)          # counts that earn a fresh screenshot
SHOT_EVERY = 6 * 3600                        # ... or one every 6 hours while it keeps happening
UPLOAD_EVERY = 60

_lock = threading.RLock()
_recent = collections.deque(maxlen=40)       # last log lines (context for an incident)
_task = {"name": None, "screen": None, "warns": []}
_state = {"dirty": False, "uploaded": 0.0, "data": None}


def _now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _load():
    if _state["data"] is None:
        try:
            with open(FILE, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        d.setdefault("version", 1)
        d.setdefault("incidents", {})
        d.setdefault("stats", {"recorded": 0, "since": _now()})
        _state["data"] = d
    return _state["data"]


def _save():
    d = _load()
    inc = d["incidents"]
    if len(inc) > MAX_INCIDENTS:                 # forget the oldest closed ones first
        order = sorted(inc, key=lambda k: (inc[k].get("status") == "open", inc[k].get("last", "")))
        for k in order[:len(inc) - MAX_INCIDENTS]:
            inc.pop(k, None)
    try:
        tmp = FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, FILE)
    except Exception as e:
        log(f"  ! brain: could not save: {e!r}")
    _state["dirty"] = True


_NUM = re.compile(r"\d+([.,:]\d+)*")
_HEX = re.compile(r"0x[0-9a-fA-F]+")


def _norm(msg):
    m = str(msg or "").strip()
    m = _HEX.sub("#", m)
    m = _NUM.sub("#", m)
    m = re.sub(r"\s+", " ", m)
    return m[:160]


def signature(task, kind, msg, screen=None):
    raw = f"{task or '-'}|{kind}|{_norm(msg)}|{screen or '-'}"
    return hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()[:10]


# ---------------------------------------------------------------- log hook: context + soft warnings
def _hook(msg):
    s = str(msg)
    _recent.append(f"{datetime.datetime.now():%H:%M:%S} {s}"[:220])
    t = s.strip()
    if _task["name"] and t.startswith("!") and not t.startswith("! brain"):
        _task["warns"].append(t[:200])


if _hook not in LOG_HOOKS:
    LOG_HOOKS.append(_hook)


def task_start(name, screen=None):
    _task.update(name=name, screen=screen, warns=[])


def task_end():
    _task.update(name=None, screen=None, warns=[])


def last_warning():
    return _task["warns"][-1] if _task["warns"] else ""


# ---------------------------------------------------------------- recording
def record(kind, msg, task=None, screen=None, shot=True, detail=None):
    """kind: error (exception) | fail (task returned False) | stuck | warn.  Returns the incident key."""
    task = task or _task["name"] or "-"
    screen = screen or _task["screen"]
    key = signature(task, kind, msg, screen)
    with _lock:
        d = _load()
        inc = d["incidents"].get(key)
        new = inc is None
        if new:
            inc = d["incidents"][key] = {"key": key, "task": task, "kind": kind, "msg": str(msg)[:300], "screen": screen,
                                         "count": 0, "first": _now(), "status": "open", "fixes": {}, "shots": 0}
        reopened = inc.get("status") == "solved"
        if reopened:                                  # it came back after being marked solved
            inc["status"] = "open"
            inc["reopened"] = inc.get("reopened", 0) + 1
        inc["count"] += 1
        inc["last"] = _now()
        inc["msg"] = str(msg)[:300]
        inc["log"] = list(_recent)[-12:]
        if detail:
            inc["detail"] = str(detail)[:300]
        d["stats"]["recorded"] = d["stats"].get("recorded", 0) + 1
        want_shot = shot and inc.get("status") != "ignored" and (
            inc["count"] in SHOT_AT or time.time() - inc.get("shot_ts", 0) > SHOT_EVERY or reopened)
        _save()
    log(f"  🧠 brain: {'new' if new else 'again'} {kind} #{key} ({task}) x{inc['count']}")
    if want_shot:
        threading.Thread(target=_shoot, args=(key,), daemon=True).start()
    if (new or reopened) and kind in ("error", "fail", "stuck") and inc.get("status") != "ignored":
        try:
            import alerts
            alerts.fire("bot_incident", f"{task}: {str(msg)[:160]}", screenshot=False)
        except Exception:
            pass
    return key


def _shoot(key):
    try:
        from control import take_screenshot
        path = take_screenshot(os.path.join(tempfile.gettempdir(), f"kingbot_incident_{key}.jpg"))
    except Exception:
        path = None
    if not path or not os.path.isfile(path):
        return
    keep = os.path.join(BASE, "claude_out", "incidents")
    try:
        os.makedirs(keep, exist_ok=True)
        import shutil
        shutil.copyfile(path, os.path.join(keep, f"{key}.jpg"))
    except Exception:
        pass
    ok = False
    try:
        import control, server_config
        folder = os.path.dirname(server_config.path("status"))
        ok = control._gh_put_bytes(f"{folder}/incidents/{key}.jpg", control._seal_bytes(open(path, "rb").read()),
                                   f"bot: incident {key}")
    except Exception as e:
        log(f"  ! brain: screenshot upload failed: {e!r}")
    with _lock:
        inc = _load()["incidents"].get(key)
        if inc is not None:
            inc["shot_ts"] = time.time()
            inc["shot_at"] = _now()
            inc["shots"] = inc.get("shots", 0) + 1
            inc["shot_up"] = bool(ok)
            _save()
    upload(force=True)


# ---------------------------------------------------------------- fixes (phase 2 uses these)
def note_fix(key, fix, worked):
    with _lock:
        inc = _load()["incidents"].get(key)
        if inc is None:
            return
        f = inc["fixes"].setdefault(fix, {"tried": 0, "worked": 0})
        f["tried"] += 1
        f["worked"] += 1 if worked else 0
        f["last"] = _now()
        _save()


def best_fix(key, choices):
    """The fix that worked most often for this incident (ties -> the order given)."""
    inc = _load()["incidents"].get(key) or {}
    fx = inc.get("fixes") or {}
    def score(c):
        f = fx.get(c) or {}
        return (f.get("worked", 0) / f["tried"]) if f.get("tried") else 0.5
    return sorted(choices, key=lambda c: -score(c))


# ---------------------------------------------------------------- admin decisions + upload
def apply_admin(notes):
    """control.json brain_notes -> incident status / note."""
    if not isinstance(notes, dict):
        return
    changed = False
    with _lock:
        inc = _load()["incidents"]
        for key, v in notes.items():
            if key not in inc or not isinstance(v, dict):
                continue
            st = v.get("status")
            if st in ("open", "solved", "ignored") and inc[key].get("status") != st and v.get("at", "") > inc[key].get("admin_at", ""):
                inc[key]["status"] = st
                inc[key]["admin_at"] = v.get("at", _now())
                changed = True
            note = str(v.get("note") or "")[:300]
            if note and note != inc[key].get("admin_note"):
                inc[key]["admin_note"] = note
                changed = True
        if changed:
            _save()


def summary():
    d = _load()
    inc = list(d["incidents"].values())
    return {"open": sum(1 for i in inc if i.get("status") == "open"),
            "total": len(inc), "recorded": d["stats"].get("recorded", 0)}


def upload(force=False):
    """Send the incident list to kingbot-syn (at most once a minute unless forced)."""
    if not _state["dirty"] or (not force and time.time() - _state["uploaded"] < UPLOAD_EVERY):
        return
    _state["uploaded"] = time.time()
    try:
        import control, server_config
        with _lock:
            d = json.loads(json.dumps(_load()))
        for i in d["incidents"].values():
            i.pop("shot_ts", None)
        d["updated"] = _now()
        d["summary"] = summary()
        folder = os.path.dirname(server_config.path("status"))
        body = json.dumps(control._seal_json(d, ("updated",)), ensure_ascii=False, indent=1).encode("utf-8")
        if control._gh_put_bytes(f"{folder}/brain.json", body, "bot: brain"):
            _state["dirty"] = False
    except Exception as e:
        log(f"  ! brain: upload failed: {e!r}")


if __name__ == "__main__":
    k = record("fail", "could not find the gather button 12 times", task="gather", screen="map", shot=False)
    record("fail", "could not find the gather button 3 times", task="gather", screen="map", shot=False)
    print(k, _load()["incidents"][k]["count"], summary())
