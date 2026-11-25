# -*- coding: utf-8 -*-
"""
Runs your recorded routines on a schedule.

Settings come from the Kingbot dashboard (through Google Drive) when available,
otherwise from tasks.json.
Stop the bot completely: hold F12, or move the mouse into any screen corner.
"""
import os, sys, time, random, datetime
from common import *
from updater import check_and_update, local_version
from control import Control, in_schedule
import smart
import claude_channel
START_VER = [0]
RUN_NOW = [False]        # v150: the dashboard's "run now" button starts a round even while paused
TASK_NOW = [0.0, ""]     # v154: (started at, task name) - a task that never ends is aborted
TASK_LIMIT = 900         # v154: one activity may not run longer than 15 minutes

RESTART_CODE = 3  # 3_start_bot.bat restarts the bot when it exits with this code


class Stop(Exception):
    pass


class NewSettings(Exception):
    pass


class ArmyBack(Exception):
    pass


LAST_ROUND = [0.0]
EFF = [None]      # v136: the settings in effect (character rotation: the preset of the active character)


def cur_data():
    return EFF[0] or ctl.data or {}
WATCH = [0.0]
SHIELD_WATCH = [0.0]
PROBE_WATCH = [0.0]


def rally_probe_watch():
    """Every 2 minutes while waiting: join alliance fort rallies (they only last a few minutes)."""
    if time.time() - PROBE_WATCH[0] < 120:
        return
    PROBE_WATCH[0] = time.time()
    d = cur_data()
    t = next((x for x in d.get("tasks", []) if x.get("routine") == "join_rally"), None)
    if t is not None and not t.get("enabled"):
        return
    t = t or {}
    try:
        if find_window():
            smart.join_rally(Game(), sleep, max_troops=t.get("max_troops", 600000),
                             max_armies=t.get("max_armies", 2), quiet=True)
    except Exception as e:
        if "screen grab failed" not in str(e):
            log(f"! join_rally watch failed: {e!r}")


PAUSE_LOGGED = [0]


def in_daily_pause(settings=None):
    """v82: the bot rests every day before the game reset (00:00 UTC) and starts again right at the reset.
    Default 23:30-00:00 UTC (= 03:30-04:00 Muscat). Dashboard key daily_pause {"from": "HH:MM", "to": "HH:MM"} (UTC)."""
    d = (settings or ctl.data or {}).get("daily_pause") or {"from": "23:30", "to": "00:00"}
    if d.get("off"):
        return False
    now = datetime.datetime.utcnow()
    cur = now.hour * 60 + now.minute
    def mins(t):
        h, m = str(t).split(":")
        return int(h) * 60 + int(m)
    a, b = mins(d.get("from", "23:30")), mins(d.get("to", "00:00"))
    return (a <= cur < b) if a < b else (cur >= a or cur < b)


HELP_WATCH = [0]


def help_watch():
    """v88: press the alliance Help bubble whenever it shows while the bot waits (about once a minute)."""
    if time.time() - HELP_WATCH[0] < 60:
        return
    HELP_WATCH[0] = time.time()
    d = cur_data()
    t = next((x for x in d.get("tasks", []) if x.get("routine") == "alliance_help"), None)
    if t is not None and not t.get("enabled"):
        return
    try:
        if find_window():
            g = Game()
            if g.find_image("alliance_help", 0.75):
                log("Alliance help bubble seen - helping.")
                smart.alliance_help(g, sleep)
    except Exception as e:
        log(f"! help watch failed: {e!r}")


TAVERN_WATCH = [0]


def tavern_watch():
    """v79: every ~9 minutes while waiting: open the free tavern chests (silver chest has a short cooldown)."""
    if time.time() - TAVERN_WATCH[0] < 540:
        return
    TAVERN_WATCH[0] = time.time()
    d = cur_data()
    t = next((x for x in d.get("tasks", []) if x.get("routine") == "tavern"), None)
    if t is not None and not t.get("enabled"):
        return
    try:
        if find_window():
            smart.tavern(Game(), sleep)
    except Exception as e:
        log(f"! tavern watch failed: {e!r}")


ATTACK_WATCH = [0]


WATCH_ERR = [0.0, ""]        # last watchdog fault: (time, text), so a repeating one is logged once


def watch_error(prefix, e):
    """Log a watchdog failure without flooding log.txt.

    v148: attack_watch / auto_shield run every 20-30 s; an empty picture while the screen is off
    raised a cv2 assertion that was written to the log dozens of times a minute. Screen-off
    failures are ignored (the round loop already handles them) and the same fault is logged at
    most once every 10 minutes.
    """
    msg = repr(e)
    if "screen grab failed" in msg or "-215" in msg or "!_src.empty()" in msg:
        return
    now = time.time()
    if WATCH_ERR[1] != msg or now - WATCH_ERR[0] > 600:
        log(f"! {prefix}: {msg}")
        WATCH_ERR[0], WATCH_ERR[1] = now, msg


def attack_watch():
    """v105: every 20 s - red warning border -> notification (dashboard + Telegram)."""
    if time.time() - ATTACK_WATCH[0] < 20:
        return
    ATTACK_WATCH[0] = time.time()
    try:
        if find_window():
            smart.attack_watch(Game())
    except Exception as e:
        watch_error("attack watch failed", e)


def shield_watch():
    """Every 30 s while waiting: if Auto Shield is switched on in the dashboard, look for an attack."""
    if time.time() - SHIELD_WATCH[0] < 30:
        return
    SHIELD_WATCH[0] = time.time()
    d = cur_data()
    t = next((x for x in d.get("tasks", []) if x.get("routine") == "auto_shield" and x.get("enabled")), None)
    if not t:
        return
    try:
        if not find_window():
            return
        g = Game()
        smart.auto_shield(g, sleep, mode=t.get("mode", "on_attack"), pct=t.get("pct", 20),
                          react_scout=t.get("react_scout", False))
    except Exception as e:
        watch_error("auto_shield check failed", e)


def army_back():
    """True when an army came back (march counter is no longer 5/5) and a round may start."""
    if time.time() - WATCH[0] < 120 or time.time() - LAST_ROUND[0] < 600:
        return False
    WATCH[0] = time.time()
    try:
        if not find_window():
            return False
        g = Game()
        return not smart._queue_full(g)
    except Exception:
        return False


ctl = Control()


def check_stop():
    if key_down(VK["F12"]):
        raise Stop()


QUICK = [0.0, False]


def quick_requests():
    """v137: answer a screenshot request right away, even in the middle of a round (it does not click)."""
    if QUICK[1] or time.time() - QUICK[0] < 3:
        return
    QUICK[0], QUICK[1] = time.time(), True
    try:
        ctl.poll()
        ctl.screenshot_if_asked()
    except Exception:
        pass
    finally:
        QUICK[1] = False


def sleep(sec):
    end = time.time() + sec
    while time.time() < end:
        check_stop()
        LAST_ACTIVITY[0] = time.time()
        quick_requests()
        time.sleep(0.1)


def _status_then_exit(**status):
    """v193: tell the dashboard, then exit - but never wait more than 15 s for GitHub.
    (14:02 on 25-11: write_status hung on the network, os._exit was never reached and the bot stayed dead.)"""
    import threading
    t = threading.Thread(target=lambda: ctl.write_status(**status), daemon=True)
    t.start()
    t.join(15)
    os._exit(RESTART_CODE)


def watchdog(limit=600):
    """If the bot shows no activity for `limit` seconds (stuck on a frozen window), restart it.

    v170: the limit was 3 minutes, which was reached by tasks that legitimately block for a while
    (an OCR subprocess, a slow window) - the bot then restarted 35 times in one night. It now
    warns at 2.5 minutes and restarts only after 10, naming the task that is stuck.
    """
    import threading
    warned = [0.0]

    hung_since = [0.0]

    def game_hung_check():
        """v193: the game window stopped answering Windows (\"Not Responding\") for 3 minutes -> close it.
        The next round starts the game again."""
        try:
            hwnd = find_window()
            if hwnd and ctypes.windll.user32.IsHungAppWindow(hwnd):
                if not hung_since[0]:
                    hung_since[0] = time.time()
                    log_raw("  ! the game window is not responding - waiting up to 3 minutes")
                elif time.time() - hung_since[0] > 180:
                    log("! the game has been frozen for 3 minutes - closing it (it is started again)")
                    import subprocess
                    subprocess.run(["taskkill", "/IM", "MASS.exe", "/F"], capture_output=True, timeout=20,
                                   creationflags=0x08000000)
                    hung_since[0] = 0.0
            else:
                hung_since[0] = 0.0
        except Exception:
            pass

    def run():
        n = 0
        while True:
            time.sleep(15)
            n += 1
            try:                                  # v193: heartbeat for the external watchdog (watchdog.ps1)
                with open(HEARTBEAT_FILE, "w") as f:
                    f.write(f"{os.getpid()} {time.time():.0f}")
            except Exception:
                pass
            if n % 4 == 0:
                game_hung_check()
            t0, tname = TASK_NOW[0], TASK_NOW[1]
            if t0 and time.time() - t0 > TASK_LIMIT:
                log(f"! task '{tname}' has been running for over {TASK_LIMIT // 60} minutes "
                    f"- aborting it and restarting the bot")
                _status_then_exit(state="restarting", task=f"{tname} took too long")
            quiet = time.time() - LAST_ACTIVITY[0]
            if quiet > 150 and time.time() - warned[0] > 300:
                warned[0] = time.time()
                log_raw(f"  ! no progress for {quiet / 60:.1f} minutes"
                        + (f" in task '{tname}'" if tname else "")
                        + f" - will restart after {limit // 60} minutes")
            if quiet > limit:
                log(f"! Kingbot was stuck for over {limit // 60} minutes"
                    + (f" in task '{tname}'" if tname else "") + ". Restarting ...")
                _status_then_exit(state="restarting")
    threading.Thread(target=run, daemon=True).start()


def idle(sec, **status):
    """Wait, while answering the dashboard. Raises NewSettings when new settings arrive."""
    end = time.time() + sec
    last_status = 0
    while time.time() < end:
        check_stop()
        _, changed = ctl.poll()
        ctl.screenshot_if_asked()
        probe_if_asked()
        action_if_asked()
        claude_channel.check(sleep)
        shield_watch()
        attack_watch()
        session_watch()
        stream_keeper()
        rn = (ctl.data or {}).get("run_now")
        if rn and rn != getattr(ctl, "run_now_done", None):
            ctl.run_now_done = rn
            RUN_NOW[0] = True
            log("Dashboard asked for a round right now.")
            raise NewSettings()
        if status.get("state") == "waiting" and in_daily_pause():
            return                                           # daily pause starts now
        if status.get("state") == "waiting":
            rally_probe_watch()
            tavern_watch()
            help_watch()
        if status.get("state") == "waiting" and army_back():
            raise ArmyBack()
        if local_version() != START_VER[0]:
            log("New Kingbot version found. Restarting ...")
            sys.exit(RESTART_CODE)
        if time.time() - last_status > 30:          # v148: the dashboard looked late with 60 s
            ctl.write_status(**status)
            _touch_pid()                            # v168: heartbeat for the single-instance lock
            last_status = time.time()
        if changed or getattr(ctl, "pending_change", False):
            ctl.pending_change = False
            raise NewSettings()
        LAST_ACTIVITY[0] = time.time()
        time.sleep(1)


def probe_if_asked():
    d = ctl.data or {}
    req = d.get("probe_request")
    if not req or req == getattr(ctl, "probe_done", None) or not ctl.root:
        return
    ctl.probe_done = req
    g = get_game()
    if g is None:
        log("! Probe skipped: game window not found.")
        return
    import shutil
    def save(name, path):
        shutil.copyfile(path, os.path.join(ctl.root, "outbox", name + ".jpg"))
    log("Taking probe screenshots for Claude ...")
    smart.probe_screens(g, sleep, save)



# ---------------- v144: live stream keeper (OBS virtual camera -> VDO.Ninja in a minimized Chrome) ----------------
STREAM_ID, STREAM_PW = "kbb294c813b7", "ct1q-ZeP"
OBS_EXE = r"C:\Users\Administrator\obs-studio\bin\64bit\obs64.exe"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
_STREAM_LAST = [0.0]


def _proc_running(image, title_part=None):
    import subprocess
    try:
        args = ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"] + (["/V"] if title_part else [])
        out = subprocess.run(args, capture_output=True, text=True, timeout=20, creationflags=0x08000000).stdout
        if title_part:
            return any(title_part.lower() in line.lower() for line in out.splitlines())
        return image.lower() in out.lower()
    except Exception:
        return True                                          # unknown -> do not start a second copy


def stream_keeper(force=False):
    """v192: the live stream is run by stream_bot.py (its own process). It starts and stops OBS and the
    Chrome sender by itself when the dashboard pauses, freezes or resumes the bot. Here we only make sure
    that stream_bot.py is running (checked at most once a minute)."""
    import subprocess, sys
    if not force and time.time() - _STREAM_LAST[0] < 60:
        return
    _STREAM_LAST[0] = time.time()
    try:
        pid_file = os.path.join(BASE, "stream_bot.pid")
        try:
            pid = int(open(pid_file, encoding="utf-8").read().strip())
        except Exception:
            pid = 0
        if pid:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True,
                                 text=True, timeout=15, creationflags=0x08000000).stdout
            if str(pid) in out:
                # v193: stream_bot.py was updated after this copy started -> replace it with the new code
                try:
                    if os.path.getmtime(os.path.join(BASE, "stream_bot.py")) > os.path.getmtime(pid_file) + 5:
                        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=30,
                                       creationflags=0x08000000)
                        log("  stream: stream_bot.py was updated - restarting it")
                        pid = 0
                except Exception:
                    pass
                if pid:
                    return
        exe = sys.executable
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        subprocess.Popen([w if os.path.exists(w) else exe, os.path.join(BASE, "stream_bot.py")], cwd=BASE,
                         creationflags=0x00000008 | 0x08000000)
        log("  stream: stream_bot.py started (live stream follows the dashboard)")
    except Exception as e:
        log(f"  ! stream keeper failed: {e!r}")


# ---------------- v145: keep the screen alive after Remote Desktop disconnects (tscon to console) ----------------
_KEEP_LAST = [0.0]


def _set_resolution(w, h):
    import ctypes
    from ctypes import wintypes

    class DEVMODE(ctypes.Structure):
        _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD), ("dmDriverVersion", wintypes.WORD),
                    ("dmSize", wintypes.WORD), ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                    ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG), ("dmDisplayOrientation", wintypes.DWORD),
                    ("dmDisplayFixedOutput", wintypes.DWORD), ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                    ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                    ("dmFormName", wintypes.WCHAR * 32), ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
                    ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD), ("dmDisplayFlags", wintypes.DWORD),
                    ("dmDisplayFrequency", wintypes.DWORD), ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
                    ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD), ("dmReserved1", wintypes.DWORD),
                    ("dmReserved2", wintypes.DWORD), ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    if not ctypes.windll.user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
        return False
    if (dm.dmPelsWidth, dm.dmPelsHeight) == (w, h):
        return True
    dm.dmPelsWidth, dm.dmPelsHeight = w, h
    dm.dmFields = 0x00080000 | 0x00100000
    return ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0) == 0


def no_sleep():
    """v146: the server's own screen must never sleep, blank or lock while the bot plays on it."""
    import ctypes, subprocess
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000002 | 0x00000001)   # continuous, display, system
        ctypes.windll.user32.SystemParametersInfoW(0x0011, 0, None, 3)                         # screen saver off
    except Exception:
        pass
    if not getattr(no_sleep, "done", False):
        no_sleep.done = True
        for args in (["powercfg", "/change", "monitor-timeout-ac", "0"], ["powercfg", "/change", "standby-timeout-ac", "0"],
                     ["powercfg", "/change", "monitor-timeout-dc", "0"]):
            try:
                subprocess.run(args, capture_output=True, timeout=20, creationflags=0x08000000)
            except Exception:
                pass
        log("  keep-screen: screen sleep, screen saver and standby switched off")


def keep_screen_alive():
    """When Remote Desktop disconnects, Windows switches the session's screen off and the bot is blind.
    tscon moves this session to the server's own console: the screen stays on and the bot keeps playing.
    Connecting again with Remote Desktop takes the session back as usual."""
    import ctypes, subprocess
    st = ((ctl.data or {}).get("keep_screen") or {})
    if st.get("enabled", True) is False:
        return False
    if time.time() - _KEEP_LAST[0] < 25:
        return False
    _KEEP_LAST[0] = time.time()
    no_sleep()
    try:
        sid = ctypes.c_ulong()
        ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
        exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Sysnative" if sys.maxsize <= 2**32 else "System32", "tscon.exe")
        r = subprocess.run([exe, str(sid.value), "/dest:console"], capture_output=True, text=True, timeout=30, creationflags=0x08000000)
        log(f"  keep-screen: session {sid.value} moved to the server console (rc {r.returncode}) {(r.stdout + r.stderr).strip()[:120]}")
        time.sleep(6)
        for w, h in ((1280, 800), (1280, 1024), (1280, 720), (1366, 768)):
            if _set_resolution(w, h):
                log(f"  keep-screen: screen {w}x{h}")
                break
        time.sleep(3)
        try:
            g = get_game()
            if g:
                g.focus()
        except Exception:
            pass
        return r.returncode == 0
    except Exception as e:
        log(f"  ! keep-screen failed: {e!r}")
        return False


SESSION_WATCH = [0.0]


def session_disconnected():
    """True when this Windows session has no input desktop because Remote Desktop is disconnected.

    WTSQuerySessionInformation(WTSConnectState): 0 = active, 4 = disconnected.
    """
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


def session_watch():
    """v170: the screen goes off when Remote Desktop disconnects, and then every click is lost
    (the pointer stays at 0,0). On 2026-11-22 that left the bot unable to open the game for more
    than an hour while it kept "working". Detect the disconnected session and move it back to the
    server console (keep_screen_alive) instead of waiting for a screenshot to fail."""
    if time.time() - SESSION_WATCH[0] < 60:
        return
    SESSION_WATCH[0] = time.time()
    if session_disconnected():
        log("The remote desktop session is disconnected - moving it to the server console")
        keep_screen_alive()


def action_if_asked():
    """v110: one-off actions from the dashboard: read_characters / switch_character."""
    d = ctl.data or {}
    req = d.get("action_request")
    if not isinstance(req, dict) or not req.get("id"):
        return
    if getattr(ctl, "action_done", None) is None:
        try:
            ctl.action_done = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "action_done.txt")).read().strip()
        except Exception:
            ctl.action_done = ""
    if str(req.get("id")) == str(ctl.action_done):
        return
    ctl.action_done = req["id"]
    try:
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "action_done.txt"), "w").write(str(req["id"]))
    except Exception:
        pass
    g = get_game()
    if g is None:
        return
    do = req.get("do")
    log(f"Dashboard action: {do}")
    steps = req.get("steps") if do == "multi" and isinstance(req.get("steps"), list) else [req]
    import control
    for i, step in enumerate(steps[:12]):
        try:
            control.CITY["action_progress"] = {"id": str(req["id"]), "step": i, "of": len(steps), "do": step.get("do")}
            if do == "multi":
                ctl.write_status(state="working", task=f"assistant: {step.get('do')} ({i + 1}/{len(steps)})")
                log(f"  assistant step {i + 1}/{len(steps)}: {step.get('do')}")
        except Exception:
            pass
        _do_action(g, step)
    try:                                                     # v137: tell the dashboard at once
        control.CITY["action_progress"] = {"id": str(req["id"]), "step": len(steps), "of": len(steps)}
        control.CITY["action_done"] = str(req["id"])
        ctl.write_status(state="working", task=f"dashboard: {do} done")
    except Exception:
        pass


def _do_action(g, req):
    """v142: one dashboard / assistant action."""
    do = req.get("do")
    try:
        if do == "read_resources":
            smart.read_resources(g, sleep)
        elif do == "read_marches":
            smart.read_marches(g, sleep)
        elif do == "read_characters":
            smart.read_characters(g, sleep)
        elif do == "feedback":
            kinds = {"problem": "مشكلة", "idea": "اقتراح", "complaint": "شكوى", "other": "رسالة"}
            smart.notify("info", f"{kinds.get(req.get('kind'), 'رسالة')} من لوحة التحكم: {str(req.get('text', ''))[:1500]}")
        elif do == "learn_city":
            # v150: dashboard button "learn my city" - map every building by name for this character
            ctl.write_status(state="working", task="city: learning the buildings")
            found = smart.learn_city(g, sleep)
            smart.notify("info", "تعلّم المدينة: " + (", ".join(sorted(found)) if found else "لم يتعرّف على أي مبنى"))
        elif do == "learn_element":
            # v180: turn the last failed click into a template + registry entry
            ctl.write_status(state="working", task="ui: learning the last failed element")
            name = smart.learn_element_from_failure(g, sleep)
            smart.notify("info", ("تعلّم عنصرًا جديدًا: " + name) if name else "لا يوجد فشل صالح للتعلّم منه")
        elif do == "read_profile":
            smart.read_profile(g, sleep)
        elif do == "read_commanders":
            smart.read_commanders(g, sleep)
        elif do == "switch_character":
            prev = load_json(ROT_FILE, {}).get("name") or _active_char()
            res = smart.switch_character(g, sleep, name=req.get("name", ""), kingdom=req.get("kingdom", ""))
            smart.read_characters(g, sleep)
            cur = _active_char()
            if res in ("switched", "already") and (not cur or _same(cur, req.get("name", ""))):
                mark_active_char(req.get("name", ""), prev=prev)   # v136: rotation continues from this character
                _refresh_after_switch()
    except (Stop, SystemExit, pyautogui.FailSafeException):
        raise
    except Exception as e:
        log(f"! dashboard action {do} failed: {e!r}")
    try:
        recover_screen(g)
    except Exception:
        pass


def jitter(v, amount=0.004):
    return v + random.uniform(-amount, amount)


def run_routine(g, name, steps):
    for i, s in enumerate(steps, 1):
        check_stop()
        g.refresh()
        if "click" in s:
            rx, ry = s["click"]
            g.click_rel(jitter(rx), jitter(ry))
        elif "key" in s:
            press_key(s["key"])
        elif "click_img" in s:
            hits = g.find_image(s["click_img"], s.get("threshold", 0.80), s.get("all", False))
            if not hits:
                if s.get("optional", True):
                    log(f"  - {name} step {i}: '{s['click_img']}' not visible, skipped")
                else:
                    log(f"  ! {name} step {i}: '{s['click_img']}' not found, routine stopped")
                    return False
            for rx, ry in hits:
                g.click_rel(rx, ry)
                sleep(0.6)
        sleep(s.get("wait", 0) + s.get("after", 1.5) + random.uniform(0, 0.6))
    return True


def current_settings():
    d, _ = ctl.poll()
    if d:
        return d, "dashboard"
    return load_json(TASKS_FILE, {}), "tasks.json"


def get_game():
    hwnd = find_window()
    if not hwnd:
        return None
    return Game()


TASK_STATE_FILE = os.path.join(BASE, "task_state.json")
# activities that run on their own timer: a random interval between two numbers (minutes)
DEFAULT_EVERY = {"collect_city": [30, 60], "daily_objectives": [480, 480], "alliance_tech": [120, 120], "alliance_gifts": [120, 180],
                 "tavern": [8, 10], "sunset_canyon": [120, 180],
                 "heal": [30, 45], "research": [30, 45], "build_upgrade": [30, 45], "read_mail": [20, 30], "read_profile": [60, 90], "read_characters": [720, 720], "read_marches": [15, 20], "materials": [60, 90], "read_commanders": [10080, 10080]}
DAILY_ONCE = {"vip_chests", "vip_shop", "tavern_legendary"}     # v67: once per game day (UTC); the day is stored in task_state


def task_every(t):
    """[min, max] minutes for an activity with its own timer, or None (runs every round)."""
    if t.get("routine") in DAILY_ONCE:
        return None
    ev = t.get("every") or DEFAULT_EVERY.get(t.get("routine"))
    if isinstance(ev, (list, tuple)) and len(ev) == 2 and float(ev[1]) > 0:
        lo, hi = sorted((float(ev[0]), float(ev[1])))
        return lo, hi
    return None


def soonest_due(settings):
    state = load_json(TASK_STATE_FILE, {})
    dues = [state.get(t["routine"], 0) for t in settings.get("tasks", [])
            if t.get("enabled", True) and task_every(t)]
    return min(dues) if dues else None


# ---------------- v136: character rotation with a saved preset per character ----------------
ROT_FILE = os.path.join(BASE, "rotation_state.json")
PER_CHAR_FILES = ("task_state.json", "gems_day.json")    # timers, daily-once marks and today's gems belong to one character


def _ckey(name):
    import re
    return re.sub(r"[^0-9A-Za-z_-]+", "_", str(name)).strip("_")[:30] or "char"


def _same(a, b):
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return False
    if a == b or (len(a) >= 3 and a in b) or (len(b) >= 3 and b in a):
        return True
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.75


def _swap_char_files(old, new):
    import shutil
    for f in PER_CHAR_FILES:
        p = os.path.join(BASE, f)
        stem = f[:-5]
        if old:
            try:
                if os.path.exists(p):
                    shutil.copyfile(p, os.path.join(BASE, f"{stem}__{_ckey(old)}.json"))
            except Exception as e:
                log(f"  ! could not keep {f} of {old}: {e!r}")
        q = os.path.join(BASE, f"{stem}__{_ckey(new)}.json")
        try:
            if os.path.exists(q):
                shutil.copyfile(q, p)
            elif os.path.exists(p):
                os.remove(p)                                 # a new character starts with every activity due
        except Exception as e:
            log(f"  ! could not load {f} of {new}: {e!r}")


def _active_char():
    import control
    c = next((c for c in (control.CITY.get("characters") or []) if c.get("current")), None)
    return c.get("name") if c else None


def _rot_status(slot, until, note=""):
    import control
    control.CITY["rotation"] = {"char": slot.get("name") if slot else None, "preset": (slot or {}).get("preset") or "",
                                "until": datetime.datetime.fromtimestamp(until).astimezone().isoformat(timespec="seconds") if until else None,
                                "note": note}


COLLECT_ON_SWITCH = ("collect_city", "tavern", "alliance_gifts", "alliance_help", "daily_objectives", "read_mail", "vip_shop", "events", "materials")


def _due_after_switch(rot=None):
    """v137: right after a character switch run the profile/marches readers, and (option, on by default)
    collect everything at once on the new character instead of waiting for each timer."""
    state = load_json(TASK_STATE_FILE, {})
    state["read_profile"] = 0; state["read_marches"] = 0
    if (rot or {}).get("collect_on_switch", True):
        for r in COLLECT_ON_SWITCH:
            state[r] = 0
        log("  character switch: collection activities set to run now (collect on switch)")
    save_json(TASK_STATE_FILE, state)


def _refresh_after_switch():
    """v137: read the new character's profile (name, power, KP, VIP) right after a switch and send it to the dashboard."""
    try:
        import control
        g = get_game()
        if g is None:
            return
        name = (control.CITY.get("rotation") or {}).get("char") or load_json(ROT_FILE, {}).get("name")
        pf = os.path.join(BASE, "profiles_by_char.json")
        store = load_json(pf, {})
        known = store.get(_ckey(name)) if name else None
        if known:
            control.CITY["profile"] = known                  # show this character's last card at once
        else:
            control.CITY.pop("profile", None)                # never show the previous character's card
        control.CITY["profile_char"] = name or ""
        cs = load_json(os.path.join(BASE, "commanders_by_char.json"), {}).get(_ckey(name)) if name else None
        if cs:
            control.CITY["commanders"] = cs.get("list", [])
            control.CITY["commanders_at"] = cs.get("at", "")
        else:
            control.CITY.pop("commanders", None)             # this character's commanders are read on its own
        ctl.write_status(state="working", task="reading the new character's profile")
        smart.read_profile(g, sleep)
        prof = control.CITY.get("profile")
        if name and prof:
            store[_ckey(name)] = prof
            save_json(pf, store)
        st = load_json(TASK_STATE_FILE, {})
        st["read_profile"] = time.time() + 60 * 60
        # v192: read this character's commanders (picture + level) on every switch
        ctl.write_status(state="working", task="reading the commanders of this character")
        try:
            if smart.read_commanders(g, sleep) != "retry":
                st["read_commanders"] = time.time() + 7 * 24 * 3600
        except (Stop, SystemExit, pyautogui.FailSafeException):
            raise
        except Exception as e:
            log(f"  ! commanders read after switch failed: {e!r}")
        save_json(TASK_STATE_FILE, st)
        ctl.write_status(state="working", task="profile updated after character switch")
    except (Stop, SystemExit, pyautogui.FailSafeException):
        raise
    except Exception as e:
        log(f"  ! profile refresh after switch failed: {e!r}")


def mark_active_char(name, settings=None, prev=None):
    """The game is now on <name> (manual switch from the dashboard or a rotation switch): keep the per-character files."""
    st = load_json(ROT_FILE, {})
    if _same(st.get("name"), name):
        return
    _swap_char_files(st.get("name") or prev, name)
    rot = ((settings or ctl.data or {}).get("char_rotation") or {})
    slot = next((x for x in rot.get("slots", []) if _same(x.get("name"), name)), None)
    until = time.time() + (slot or {}).get("minutes", 120) * 60
    save_json(ROT_FILE, {"name": name, "until": until, "fails": 0, "skip": 0, "since": time.time()})
    _rot_status(slot or {"name": name}, until)
    _due_after_switch(rot)


def _apply_preset(settings, slot):
    eff = dict(settings)
    pname = (slot or {}).get("preset") or ""
    p = (settings.get("presets") or {}).get(pname)
    if pname and not p:
        log(f"  ! preset '{pname}' for {slot.get('name')} no longer exists - using the main settings")
    if p and p.get("tasks"):
        eff["tasks"] = p["tasks"]
        eff["loop_minutes"] = p.get("loop_minutes") or settings.get("loop_minutes", 60)
    return eff


def _do_switch(slot):
    """Switch the game to slot['name'] and check it. True = the game is on that character now."""
    g = get_game()
    if g is None:
        return False
    g.focus()
    ctl.write_status(state="working", task="تبديل الشخصية إلى " + slot["name"])
    res = smart.switch_character(g, sleep, name=slot["name"], kingdom=slot.get("kingdom", ""))
    if res in ("notfound", "noyes"):
        return False
    try:
        smart.read_characters(g, sleep)                     # confirm and refresh the list (closes the page)
    except Exception as e:
        log(f"  ! read_characters after the switch failed: {e!r}")
    cur = _active_char()
    if cur and not _same(cur, slot["name"]):
        log(f"  ! after the switch the active character is {cur}, not {slot['name']}")
        if res == "switched":
            smart.notify("info", f"تبديل الشخصيات: اللعبة الآن على {cur} وليس {slot['name']}")
        return False
    return True


def rotation_settings(settings):
    """v136: character rotation. Every slot = character + saved preset + minutes. Returns the settings to use now."""
    rot = settings.get("char_rotation") or {}
    slots = [x for x in (rot.get("slots") or []) if x.get("name")]
    if not rot.get("enabled") or not slots:
        EFF[0] = None
        import control
        control.CITY.pop("rotation", None)
        return settings
    st = load_json(ROT_FILE, {})
    now = time.time()
    idx = next((i for i, x in enumerate(slots) if _same(x["name"], st.get("name"))), None)
    if idx is None:
        cur = _active_char() or st.get("name")
        i_cur = next((i for i, x in enumerate(slots) if _same(x["name"], cur)), None)
        if i_cur is not None:                               # start with the character that is already open
            log(f"Character rotation: starting with {slots[i_cur]['name']} (already open in the game)")
            if st.get("name") and not _same(st.get("name"), slots[i_cur]["name"]):
                _swap_char_files(st.get("name"), slots[i_cur]["name"])   # (no name yet: the files already belong to it)
            st = {"name": slots[i_cur]["name"], "until": now + slots[i_cur]["minutes"] * 60, "fails": 0, "skip": 0, "since": now}
            save_json(ROT_FILE, st)
            idx = i_cur
    target = None
    if idx is None:
        target = st.get("skip", 0) % len(slots)
    elif now >= st.get("until", 0):
        if len(slots) == 1:
            st["until"] = now + slots[0]["minutes"] * 60
            save_json(ROT_FILE, st)
        else:
            target = (idx + 1 + st.get("skip", 0)) % len(slots)
            if target == idx:                               # every other character was skipped: stay on this one a full turn
                log(f"Character rotation: staying on {slots[idx]['name']} for another {slots[idx]['minutes']} min")
                st.update(until=now + slots[idx]["minutes"] * 60, skip=0, fails=0)
                save_json(ROT_FILE, st)
                target = None
    if target is not None:
        slot = slots[target]
        log(f"Character rotation: switching to {slot['name']} (preset: {slot.get('preset') or 'main settings'}, {slot['minutes']} min)")
        ok = False
        prev = st.get("name") or _active_char()
        try:
            ok = _do_switch(slot)
        except (Stop, SystemExit, pyautogui.FailSafeException):
            raise
        except Exception as e:
            log(f"  ! character switch failed: {e!r}")
        if ok:
            _swap_char_files(prev, slot["name"])
            st = {"name": slot["name"], "until": time.time() + slot["minutes"] * 60, "fails": 0, "skip": 0, "since": time.time()}
            save_json(ROT_FILE, st)
            idx = target
            smart.notify("info", f"تبديل الشخصيات: البوت يعمل الآن على {slot['name']} بإعداد «{slot.get('preset') or 'الإعدادات الرئيسية'}» لمدة {slot['minutes']} دقيقة")
            _due_after_switch(rot)
            _refresh_after_switch()
        else:
            st["fails"] = st.get("fails", 0) + 1
            if st["fails"] >= 2:
                log(f"  ! could not switch to {slot['name']} twice - skipping it this time")
                smart.notify("info", f"تبديل الشخصيات: تعذّر التبديل إلى {slot['name']} مرتين، تخطيتها إلى الشخصية التالية")
                st["fails"] = 0
                st["skip"] = st.get("skip", 0) + 1
            st["until"] = time.time() + 5 * 60                 # try again in a few minutes
            save_json(ROT_FILE, st)
    slot = slots[idx] if idx is not None else None
    if slot is None:
        EFF[0] = None
        _rot_status(None, st.get("until"), "لم يتم التبديل بعد")
        return settings
    eff = _apply_preset(settings, slot)
    EFF[0] = eff
    _rot_status(slot, st.get("until"))
    return eff


UNKNOWN_ONCE = {}


def _unknown_routine(name):
    """v153: a task switched on in the dashboard that this bot has no activity for. Log it once a
    day instead of every round (events / merchant / conduct_watch are in this state)."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    if UNKNOWN_ONCE.get(name) == today:
        return
    UNKNOWN_ONCE[name] = today
    log(f"  ? routine '{name}' is switched on in the dashboard but not built yet - skipped")


def one_round(settings):

    routines = load_json(ROUTINES_FILE, {})
    import game_launcher
    if not game_launcher.ensure_game_running(sleep):
        if not find_window():
            log("Game window not found. Kingbot will try to open it again later.")
        return
    g = get_game()
    if g is None:
        return
    g.focus()
    recover_screen(g)
    try:
        smart.read_resources(g)
        ctl.write_status(state="working", task="reading resources")
        try:
            smart.read_queues(g, sleep)                      # v69: city queues for the dashboard
            ctl.write_status(state="working", task="reading city queues")
        except Exception as e2:
            log(f"  ! read_queues failed: {e2!r}")
    except Exception as e:
        log(f"  ! read_resources failed: {e!r}")
    tasks = list(settings.get("tasks", []))
    if not any(t.get("routine") == "rally_fort" for t in tasks):
        tasks.insert(0, {"routine": "rally_fort", "times": 1, "enabled": True})   # rally first (v39)
    if not any(t.get("routine") == "join_rally" for t in tasks):
        tasks.insert(1, {"routine": "join_rally", "times": 1, "enabled": True})   # v45
    if not any(t.get("routine") == "gather_gems" for t in tasks):
        tasks.append({"routine": "gather_gems", "times": 1, "enabled": True})   # gems first (v29)
    if not any(t.get("routine") == "gather" for t in tasks):
        tasks.append({"routine": "gather", "times": 1, "enabled": True})   # then normal resources (v25)
    for extra in ("daily_objectives", "vip_chests", "alliance_tech", "vip_shop", "tavern", "tavern_legendary", "sunset_canyon", "read_mail", "read_profile", "read_characters", "read_marches", "read_commanders"):   # v56
        if not any(t.get("routine") == extra for t in tasks):
            tasks.append({"routine": extra, "times": 1, "enabled": True})
    for t in tasks:
        if not t.get("enabled", True):
            continue
        name = t["routine"]
        try:                                                 # v137: dashboard read requests between activities
            ctl.poll()
            if (ctl.data or {}).get("action_request") or (ctl.data or {}).get("probe_request"):
                action_if_asked()
                probe_if_asked()
        except (Stop, SystemExit, pyautogui.FailSafeException):
            raise
        except Exception as e:
            log(f"! dashboard request between activities failed: {e!r}")
        try:
            recover_screen(g)
        except Exception:
            pass
        every = task_every(t)
        state = load_json(TASK_STATE_FILE, {})
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        if name in DAILY_ONCE and state.get(name + "_day") == today:
            log(f"  - {name}: already done today (game day {today})")
            continue
        if every and time.time() < state.get(name, 0):
            nxt = datetime.datetime.fromtimestamp(state[name])
            log(f"  - {name}: not due yet (next at {nxt:%H:%M})")
            continue
        if name not in routines and name not in smart.SMART:
            _unknown_routine(name)
            continue
        times = t.get("times", 1)
        t = dict(t)
        if name == "gather_gems":                            # v88: the stepper = how many armies go to gems (max 5)
            t["max_armies"] = max(1, min(5, int(times or 1)))
            times = 1
        elif name in ("gather",):                            # v88: automatic - every free army
            t["max_armies"] = 5
            times = 1
        else:
            times = 1 if name not in ("collect_city",) else max(1, int(times or 1))
            times = 1
        for n in range(times):
            log(f"> {name} ({n + 1}/{times})")
            try:
                log(f"  screen: {smart.what_screen(g)}")     # v176: what the task starts on
            except Exception:
                pass
            TASK_NOW[0], TASK_NOW[1] = time.time(), name
            ctl.write_status(state="working", task=f"{name} {n + 1}/{times}")
            try:
                if name in routines:
                    ok = run_routine(g, name, routines[name])
                else:
                    g.focus()
                    fn = smart.SMART[name]
                    import inspect
                    params = inspect.signature(fn).parameters
                    opts = {k: v for k, v in t.items() if k in params and k not in ("g", "sleep")}
                    ok = fn(g, sleep, **opts)
            finally:
                TASK_NOW[0] = 0.0        # v154: the task ended, the task watchdog is disarmed
            if name in DAILY_ONCE and ok is not False and ok != "retry":
                state = load_json(TASK_STATE_FILE, {})
                state[name + "_day"] = today
                save_json(TASK_STATE_FILE, state)
                log(f"  {name}: done for today ({today})")
            if every:
                state = load_json(TASK_STATE_FILE, {})
                wait_min = 30 if ok == "retry" else random.uniform(*every)   # v141: "retry" = try again soon
                state[name] = time.time() + wait_min * 60
                save_json(TASK_STATE_FILE, state)
                log(f"  {name}: next time in {wait_min:.0f} minutes")
            if not ok:
                break
            _, changed = ctl.poll()
            ctl.screenshot_if_asked()
            if changed and not ctl.data.get("running", True):
                log("Paused from dashboard.")
                return
        sleep(t.get("pause_after", 3))


STATE_AR = {"no_screen": "الشاشة مطفأة (لا يوجد اتصال سطح مكتب بعيد)", "error": "حدث خطأ، سيحاول مجدداً", "working": "يعمل الآن", "waiting": "ينتظر الجولة القادمة", "sleeping": "خارج ساعات العمل",
            "paused": "موقوف مؤقتاً", "stopped": "متوقف"}


def status_text():
    s = ctl.last or {}
    rec = load_json(ROUTINES_FILE, {})
    lines = [f"👑 Kingbot v{local_version()}",
             f"الحالة: {STATE_AR.get(s.get('state'), 'يبدأ')}",
             f"المهمة: {s.get('task') or '—'}",
             f"الجولة القادمة: {(s.get('next_round') or '—')[11:16] or '—'}",
             f"الأنشطة المسجّلة: {len(rec)}",
             f"لوحة التحكم: {'متصلة' if ctl.root else 'غير متصلة (Google Drive)'}"]
    return "\n".join(lines)


PID_FILE = os.path.join(BASE, "kingbot.pid")
HEARTBEAT_FILE = os.path.join(BASE, "heartbeat.txt")   # v193: written every 15 s by the watchdog thread


def _process_alive(pid):
    import ctypes
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


PID_MAX_AGE = 180        # v168: a pid file older than this is stale, even if the pid exists


def _touch_pid():
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def _single_instance():
    """v166/v168: refuse to run next to another Kingbot that is really alive.

    A pid alone is not enough: a half-dead instance kept the file and blocked every new start.
    The running bot refreshes the file; if it is older than PID_MAX_AGE it is taken over.
    """
    try:
        old = int(open(PID_FILE).read().strip())
    except Exception:
        old = 0
    if old and old != os.getpid() and _process_alive(old):
        try:
            age = time.time() - os.path.getmtime(PID_FILE)
        except Exception:
            age = PID_MAX_AGE + 1
        if age < PID_MAX_AGE:
            log(f"! another Kingbot is already running (pid {old}, heartbeat {age:.0f}s old) - exiting")
            os._exit(0)                  # hard exit: no thread is allowed to keep this process alive
        log(f"  the pid file of {old} is stale ({age:.0f}s) - this instance takes over")
    _touch_pid()


def main():
    _single_instance()
    log(f"Kingbot v{local_version()} starting.")
    try:
        import server_config
        me = server_config.me()
        log(f"Server: {me.get('id')}" + (" (main, old file paths)" if me.get("legacy") else "")
            + f" - settings {me.get('control')}, status {me.get('status')}")
    except Exception as e:
        log(f"! server config: {e!r}")
    if check_and_update(log):
        sys.exit(RESTART_CODE)
    start_ver = local_version()
    START_VER[0] = start_ver
    log("Kingbot started. Hold F12 or move the mouse to a screen corner to stop.")
    if is_admin():
        log("Running as administrator: clicks can reach the game.")
    else:
        log("! NOT running as administrator. The game runs elevated, so Windows blocks the bot's clicks. "
            "Close Kingbot and start 3_start_bot.bat with right-click > Run as administrator.")
    ctl.poll()
    watchdog()
    import telegram_link
    telegram_link.start(ctl, status_text)
    while True:
        try:
            if check_and_update(log) or local_version() != start_ver:
                sys.exit(RESTART_CODE)
            settings, source = current_settings()
            if not settings.get("running", True) and not RUN_NOW[0]:
                log("Paused (from dashboard). Waiting for new settings.")
                while True:
                    idle(3600, state="paused")
            fz = settings.get("freeze_until")
            if fz:
                try:
                    until = datetime.datetime.fromisoformat(str(fz).replace("Z", "+00:00"))
                    if datetime.datetime.now(datetime.timezone.utc) < until:
                        if time.time() - PAUSE_LOGGED[0] > 1800:
                            log(f"Frozen from the dashboard until {until:%Y-%m-%d %H:%M} UTC.")
                            PAUSE_LOGGED[0] = time.time()
                        idle(300, state="frozen")
                        continue
                except Exception as e:
                    log(f"! freeze_until not understood: {fz!r} ({e!r})")
            if in_daily_pause(settings):
                if time.time() - PAUSE_LOGGED[0] > 600:
                    log("Daily pause before the game reset (00:00 UTC). Kingbot starts again at the reset.")
                    PAUSE_LOGGED[0] = time.time()
                idle(60, state="sleeping")
                continue
            if not in_schedule(settings):
                log("Outside working hours (scheduler). Sleeping.")
                idle(300, state="sleeping")
                continue
            try:
                settings = rotation_settings(settings)
            except (Stop, NewSettings, SystemExit, pyautogui.FailSafeException):
                raise
            except Exception as e:
                import traceback
                log(f"! character rotation failed: {e!r}")
                log(traceback.format_exc()[-600:])
            if EFF[0]:
                source += f", character {load_json(ROT_FILE, {}).get('name')}"
            log(f"Round started (settings from {source}).")
            RUN_NOW[0] = False
            try:
                if find_window():
                    smart.probe_click_mode(Game(), sleep)      # v183: once per run
            except Exception as e:
                log(f"  ! click probe failed: {e!r}")
            LAST_ROUND[0] = time.time()
            no_sleep()
            session_watch()                                  # v170: bring a disconnected screen back first
            stream_keeper()
            try:
                one_round(settings)
            except (Stop, NewSettings, SystemExit, pyautogui.FailSafeException):
                raise
            except Exception as e:
                if "screen grab failed" in str(e):
                    log("! The server screen is switched off (nobody is connected by Remote Desktop).")
                    try:                                     # v170: the launch may be retried at once
                        import game_launcher
                        if os.path.exists(game_launcher.LAST_TRY_FILE):
                            os.remove(game_launcher.LAST_TRY_FILE)
                    except Exception:
                        pass
                    if keep_screen_alive():
                        log("  keep-screen: the screen is on again - continuing in 20 seconds")
                        idle(20, state="working")
                    else:
                        log("  Kingbot cannot see or click the game now. Waiting 5 minutes ...")
                        idle(300, state="no_screen")
                else:
                    import traceback
                    log(f"! Error in this round: {e!r}")
                    log(traceback.format_exc()[-600:])
                    if "window is black" in str(e):
                        # v172: a black picture only means the game is covered or the screen is
                        # off - never close it (closing it is what caused the endless reopen loop).
                        log("  the game picture is black - leaving the game alone and waiting")
                        idle(120, state="no_screen")
                    elif "Game window closed" in str(e) or "frozen" in str(e):
                        # the window is really gone: say so and put it back at once
                        try:
                            smart.notify("warn", "أُغلقت نافذة اللعبة — يحاول البوت فتحها من جديد")
                        except Exception:
                            pass
                        import game_launcher
                        game_launcher.ensure_game_running(sleep)
                    idle(60, state="error")
                continue
            if ctl.data and not ctl.data.get("running", True):
                continue
            mins = settings.get("loop_minutes", 60)
            due = soonest_due(settings)
            if due:   # wake up earlier for an activity with its own timer (e.g. collect_city)
                mins = min(mins, max(1.0, (due - time.time()) / 60 + 0.2))
            if EFF[0]:  # v136: wake up for the next character switch
                rt = load_json(ROT_FILE, {}).get("until")
                if rt:
                    mins = min(mins, max(1.0, (rt - time.time()) / 60 + 0.2))
            nxt = datetime.datetime.now().astimezone() + datetime.timedelta(minutes=mins)
            log(f"Round finished. Next round at {nxt:%H:%M}.")
            idle(mins * 60 + random.uniform(0, 30), state="waiting",
                 next_round=nxt.isoformat(timespec="seconds"),
                 last_round=datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
        except NewSettings:
            log("New settings received from dashboard.")
            continue
        except ArmyBack:
            log("An army came back to the city. Starting a round to send it out again.")
            continue


if __name__ == "__main__":
    try:
        main()
    except Stop:
        log("Stopped by F12.")
        ctl.write_status(state="stopped")
    except pyautogui.FailSafeException:
        log("Stopped: mouse moved to screen corner.")
        ctl.write_status(state="stopped")
