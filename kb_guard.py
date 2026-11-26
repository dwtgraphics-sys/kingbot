# -*- coding: utf-8 -*-
"""Kingbot guard: live health + dashboard command tracking + resilient Remote Desktop session recovery.

Everything here is cheap and never clicks. bot.py feeds it, control.write_status() publishes snapshot()
into outbox/status.json so the dashboard can show:

    heartbeat_at        last heartbeat of the bot process (UTC ISO, every 15 s from the watchdog thread)
    health.state        running / paused / frozen / recovering / waiting / error   ("offline" = no fresh status, decided by the dashboard)
    active_routine      the activity running right now (None between activities)
    last_error          last error text + when
    last_sync_at        last time control.json was read from GitHub
    last_command        {kind, id, do, status, detail, at}  status: received / queued / running / done / failed / skipped
    command_status      = last_command.status   (flat copies for simple readers)
    command_updated_at  = last_command.at
    commands            the last 8 commands, newest first
"""
import datetime
import os
import subprocess
import sys
import threading
import time

_LOCK = threading.Lock()
HEALTH = {"heartbeat_at": None, "active_routine": None, "routine_since": None, "last_error": None,
          "last_error_at": None, "last_sync_at": None, "state": None, "session": "active", "session_note": ""}
COMMANDS = []          # newest first, max 8
_ACKED = {}            # (kind, id) -> last status written (no duplicate history lines)


def _iso(t=None):
    return datetime.datetime.utcfromtimestamp(t or time.time()).strftime("%Y-%m-%dT%H:%M:%SZ")


def beat():
    HEALTH["heartbeat_at"] = _iso()


def synced():
    HEALTH["last_sync_at"] = _iso()


def routine(name):
    """The activity that runs now (None when it ended)."""
    HEALTH["active_routine"] = name or None
    HEALTH["routine_since"] = _iso() if name else None


def error(text):
    HEALTH["last_error"] = str(text)[:300]
    HEALTH["last_error_at"] = _iso()


def state(name):
    HEALTH["state"] = name


def command(kind, cid, do=None, status="received", detail=""):
    """Record what happened to one dashboard command. kind: action / probe / shot / run_now / settings."""
    if not cid:
        return
    key = (kind, str(cid))
    with _LOCK:
        if _ACKED.get(key) == status and status not in ("running",):
            return
        _ACKED[key] = status
        item = next((c for c in COMMANDS if c["kind"] == kind and c["id"] == str(cid)), None)
        if item is None:
            item = {"kind": kind, "id": str(cid), "do": do, "received_at": _iso()}
            COMMANDS.insert(0, item)
            del COMMANDS[8:]
        if do:
            item["do"] = do
        item.update(status=status, detail=str(detail or "")[:200], at=_iso())
        if len(_ACKED) > 200:
            for k in list(_ACKED)[:100]:
                _ACKED.pop(k, None)


def _future(v):
    if not v:
        return False
    try:
        t = datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        return t.timestamp() > time.time()
    except Exception:
        return False


def snapshot(info_state=None, freeze_until=None, running=True):
    """Fields merged into status.json."""
    st = info_state or HEALTH.get("state") or ""
    if HEALTH.get("session") == "disconnected":
        hs = "recovering"
    elif _future(freeze_until):
        hs = "frozen"
    elif running is False or st in ("paused", "stopped"):
        hs = "paused"
    elif st in ("restarting", "no_screen", "error", "captcha_required"):
        hs = "recovering" if st != "error" else "error"
    elif st in ("waiting", "sleeping"):
        hs = "waiting"
    else:
        hs = "running"
    last = COMMANDS[0] if COMMANDS else None
    return {
        "heartbeat_at": HEALTH["heartbeat_at"],
        "active_routine": HEALTH["active_routine"],
        "last_error": HEALTH["last_error"],
        "last_sync_at": HEALTH["last_sync_at"],
        "last_command": dict(last) if last else None,
        "command_status": last["status"] if last else None,
        "command_updated_at": last["at"] if last else None,
        "health": {"state": hs, "routine_since": HEALTH["routine_since"], "last_error_at": HEALTH["last_error_at"],
                   "session": HEALTH["session"], "session_note": HEALTH["session_note"],
                   "commands": [dict(c) for c in COMMANDS]},
    }


# ---------------- Remote Desktop session guard ----------------
# When RDP disconnects, Windows turns the session's screen off and every click is lost. tscon moves the
# session to the server console. It can hang or fail (session switch in progress, another user, no rights):
# never call it more than once per backoff step, always with a timeout, and verify the result.
_SESS = {"next": 0.0, "fails": 0, "logged": ""}
BACKOFF = (60, 120, 300, 600)


def session_disconnected():
    """True when this session has no input desktop (WTSConnectState 4 = disconnected)."""
    try:
        import ctypes
        from ctypes import wintypes
        sid = wintypes.DWORD()
        ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
        buf, n = ctypes.POINTER(ctypes.c_void_p)(), wintypes.DWORD()
        if not ctypes.windll.wtsapi32.WTSQuerySessionInformationW(None, sid.value, 8, ctypes.byref(buf), ctypes.byref(n)):
            return False
        try:
            return ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] == 4
        finally:
            ctypes.windll.wtsapi32.WTSFreeMemory(buf)
    except Exception:
        return False


def _tscon(log):
    import ctypes
    sid = ctypes.c_ulong()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Sysnative" if sys.maxsize <= 2 ** 32 else "System32", "tscon.exe")
    try:
        r = subprocess.run([exe, str(sid.value), "/dest:console"], capture_output=True, text=True, timeout=20,
                           creationflags=0x08000000)
        return r.returncode, (r.stdout + r.stderr).strip()[:120]
    except subprocess.TimeoutExpired:
        return -1, "tscon timed out after 20 s"
    except Exception as e:
        return -2, repr(e)[:120]


def session_guard(log, after_ok=None):
    """Call often (cheap). Returns True when the session is (now) usable.
    Disconnected -> tscon with backoff 1, 2, 5, 10 min; success is checked, not assumed."""
    if not session_disconnected():
        if HEALTH["session"] != "active":
            log("  session: the screen is back (session active)")
        HEALTH["session"], HEALTH["session_note"] = "active", ""
        _SESS["fails"] = 0
        _SESS["next"] = 0.0
        return True
    HEALTH["session"] = "disconnected"
    now = time.time()
    if now < _SESS["next"]:
        return False
    rc, out = _tscon(log)
    time.sleep(5)
    ok = not session_disconnected()
    step = BACKOFF[min(_SESS["fails"], len(BACKOFF) - 1)]
    if ok:
        log(f"  session: moved to the server console (rc {rc}) - screen on")
        HEALTH["session"], HEALTH["session_note"] = "active", ""
        _SESS["fails"] = 0
        _SESS["next"] = 0.0
        if after_ok:
            try:
                after_ok()
            except Exception:
                pass
        return True
    _SESS["fails"] += 1
    _SESS["next"] = now + step
    note = f"tscon failed (rc {rc}: {out}) - next try in {step // 60} min"
    HEALTH["session_note"] = note
    if _SESS["logged"] != note[:40]:
        log("  ! session: " + note)
        _SESS["logged"] = note[:40]
    return False
