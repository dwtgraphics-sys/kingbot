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
        if d.get("lessons_version", 0) < max(x["since"] for x in LESSONS):
            d["lessons_version"] = max(x["since"] for x in LESSONS)
            threading.Timer(5, apply_lessons).start()     # BRAIN-02: close what the new lessons explain
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


# ---------------------------------------------------------------- BRAIN-02: lessons (known faults + how they are handled)
# Each lesson: what the fault looks like (message / log pattern), the real cause, and what the bot does about it.
# - an error whose message matches a lesson with env=True is a known state, not a code bug: it is kept as kind
#   "known", already solved, with the lesson attached - no alert, no Telegram, no screenshot.
# - old open incidents that match a lesson are closed with the lesson as the note (the admin page shows it).
# - a log line that matches a lesson's "handled" pattern counts as the bot applying that fix (stats per lesson).
LESSONS = [
    {"id": "no_screen", "since": 317, "env": True,
     "match": r"screen grab failed",
     "handled": r"screen is on again|moved it to the console|keep-screen: the screen is on",
     "cause": "انقطعت جلسة سطح المكتب البعيد (RDP) أو صُغّرت نافذتها، فلا يستطيع البوت رؤية الشاشة ولا الضغط (المؤشر عالق عند 0,0).",
     "fix": "يوقف البوت الجولة فوراً ولا يبدأ أي مهمة وهو أعمى، ينقل الجلسة إلى الكونسول (tscon) ثم يكمل بعد 20 ثانية، أو ينتظر 5 دقائق ويحاول مجدداً.",
     "owner": "اقطع اتصال RDP بملف switch_to_hidden.bat بدل إغلاق النافذة أو تصغيرها."},
    {"id": "game_closed", "since": 320, "env": True,
     "match": r"Game window closed",
     "handled": r"Game window opened|Launcher START pressed",
     "cause": "أُغلقت اللعبة أثناء المهمة (انهيار، طرد من جهاز آخر، أو ضغطة على نافذة الخروج).",
     "fix": "توقف الجولة، يُرسل تنبيه، ويعيد البوت فتح اللعبة ويضغط START في المشغّل ثم 'Click to Start'.",
     "owner": ""},
    {"id": "double_login", "since": 321, "env": True,
     "match": r"another device|already logged in",
     "handled": r"relogin: reconnected after the cooldown",
     "cause": "نفس حساب اللعبة مفتوح على سيرفر أو جهاز آخر؛ كل واحد يطرد الآخر وقد تُغلق اللعبة مع الطرد.",
     "fix": "ينتظر البوت 10 دقائق، وتتضاعف المدة مع كل طرد خلال 3 ساعات (حتى ساعتين)، وفي الطرد الثالث ينبّه المالك.",
     "owner": "اترك كل حساب لعبة على سيرفر واحد فقط (بريد مختلف لكل سيرفر)."},
    {"id": "exit_confirm", "since": 322, "env": False,
     "match": r"CONFIRM button off-centre|'Exit the game\?' was open",
     "handled": r"CONFIRM button off-centre|'Exit the game\?' was open - pressing CANCEL",
     "cause": "نافذة 'Exit the game?' فيها CONFIRM على اليسار وCANCEL على اليمين؛ ضغط CONFIRM يغلق اللعبة.",
     "fix": "لا يضغط البوت CONFIRM إلا إذا كان وحيداً في منتصف الشاشة (بطاقة مكافأة)؛ في نافذة الخروج يضغط CANCEL أو يتركها.",
     "owner": ""},
    {"id": "launcher_front", "since": 323, "env": False,
     "match": r"launcher was in front",
     "handled": r"launcher was in front of the game - minimised it",
     "cause": "مشغّل اللعبة (START / Pre-Download) ظهر فوق اللعبة، فكانت الصور والضغطات تذهب إليه.",
     "fix": "يصغّر البوت المشغّل دون أي ضغطة عليه ويعيد اللعبة للأمام قبل كل مهمة.",
     "owner": ""},
    {"id": "obs_runtime", "since": 319, "env": True,
     "match": r"MSVCP140_1|Visual C\+\+ runtime|OBS closed right after starting",
     "handled": r"Visual C\+\+ runtime installed|closed .* OBS error window",
     "cause": "مكتبة Microsoft Visual C++ غير مثبتة، فـ OBS لا يعمل ويُظهر نافذة خطأ فوق اللعبة.",
     "fix": "يمنع البوت نافذة الخطأ، يثبّت المكتبة بصمت من مايكروسوفت (مرة كل 6 ساعات)، ويؤجل إعادة تشغيل OBS بدل التكرار كل دقيقة.",
     "owner": "إن استمر: شغّل أمر install_obs من لوحة التحكم."},
    {"id": "telegram_401", "since": 323, "env": True,
     "match": r"Telegram connection failed: .*401",
     "handled": r"Telegram connection OK",
     "cause": "رمز بوت تيليجرام (التوكن) في إعدادات هذا السيرفر خاطئ أو أُلغي - ليس خطأ برمجياً.",
     "fix": "البوت يكمل عمله بدون تيليجرام ويُظهر التنبيهات في لوحة التحكم فقط.",
     "owner": "أنشئ توكن جديداً من BotFather وضعه في إعدادات السيرفر."},
]
_LESSON_RE = [(l, re.compile(l["match"], re.I), re.compile(l["handled"], re.I)) for l in LESSONS]


def lesson_for(text):
    """The lesson whose pattern matches this message / log line, or None."""
    t = str(text or "")
    for l, m, _h in _LESSON_RE:
        if m.search(t):
            return l
    return None


def _lesson_note(l):
    note = f"🧠 {l['id']} (v{l['since']}): السبب: {l['cause']} — ما يفعله البوت: {l['fix']}"
    if l.get("owner"):
        note += f" — المطلوب منك: {l['owner']}"
    return note[:600]


def _learned(lid, field):
    """Count a lesson event: 'seen' (the fault happened) or 'handled' (the bot applied the fix)."""
    with _lock:
        d = _load()
        st = d.setdefault("lessons", {}).setdefault(lid, {"seen": 0, "handled": 0})
        st[field] = st.get(field, 0) + 1
        st["last_" + field] = _now()
        _state["dirty"] = True


def apply_lessons():
    """Close old open incidents that a lesson explains (once per load; the admin can reopen them)."""
    changed = 0
    with _lock:
        d = _load()
        for inc in d["incidents"].values():
            l = lesson_for(inc.get("msg")) if inc.get("status") == "open" else None
            if not l or inc.get("lesson") == l["id"]:
                continue
            inc["lesson"] = l["id"]
            inc["status"] = "solved"
            inc["admin_note"] = _lesson_note(l)
            inc["admin_at"] = _now()
            changed += 1
        if changed:
            d["lessons_version"] = max(x["since"] for x in LESSONS)
            _save()
    if changed:
        log(f"  🧠 brain: {changed} old incident(s) closed with a known lesson")
    return changed


# ---------------------------------------------------------------- log hook: context + soft warnings
def _hook(msg):
    s = str(msg)
    _recent.append(f"{datetime.datetime.now():%H:%M:%S} {s}"[:220])
    t = s.strip()
    if _task["name"] and t.startswith("!") and not t.startswith("! brain"):
        _task["warns"].append(t[:200])
    if "brain" not in t:                                  # BRAIN-02: the bot applied a known fix
        for l, _m, h in _LESSON_RE:
            if h.search(t):
                try:
                    _learned(l["id"], "handled")
                except Exception:
                    pass
                break


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
    lesson = lesson_for(msg) if kind in ("error", "fail") else None
    if lesson and lesson.get("env"):
        # v317/v320 + BRAIN-02: a known environment state (no screen, game closed, double login, ...).
        # Remembered as kind "known", already solved, with its lesson - no bug report, alert or screenshot.
        kind, shot = "known", False
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
        if lesson:
            inc["lesson"] = lesson["id"]
            if lesson.get("env"):
                inc["status"] = "solved"
                inc["admin_note"] = _lesson_note(lesson)
                inc.setdefault("admin_at", _now())
        reopened = inc.get("status") == "solved" and kind != "known"
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
    if lesson:
        _learned(lesson["id"], "seen")
    log(f"  🧠 brain: {'new' if new else 'again'} {kind} #{key} ({task}) x{inc['count']}"
        + (f" - known: {lesson['id']}" if lesson else ""))
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
            "total": len(inc), "recorded": d["stats"].get("recorded", 0),
            "known": sum(1 for i in inc if i.get("lesson")), "lessons": len(LESSONS)}


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
        d["playbook"] = [{k: l[k] for k in ("id", "since", "cause", "fix", "owner")} for l in LESSONS]
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
