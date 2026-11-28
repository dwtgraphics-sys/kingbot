# -*- coding: utf-8 -*-
"""
Runs your recorded routines on a schedule.

Settings come from the Kingbot dashboard (through Google Drive) when available,
otherwise from tasks.json.
Stop the bot completely: hold F12, or move the mouse into any screen corner.
"""
import os, re, sys, time, random, datetime
from common import *
from updater import check_and_update, local_version
from control import Control, in_schedule
import smart
import claude_channel
import queue_manager
import automation
import alerts
import kb_guard
import game_login
smart.SMART["queue_manager"] = queue_manager.run


def conduct_watch(g, sleep, notify_below=100, stop_below=80, **_opts):
    """URGENT-02: read the Conduct Score from Settings -> Conduct Score (closing Settings after), alert under
    notify_below and STOP the bot at stop_below or lower (default 80) - the safety stop holds until the owner
    resumes from the dashboard or a later reading is above the limit."""
    v = smart.read_conduct(g, sleep)
    try:
        lim = int(stop_below or 80)
        note = int(notify_below or 100)
    except Exception:
        lim, note = 80, 100
    if v is None:
        log("  conduct_watch: Conduct not read")
        return True
    log(f"  conduct_watch: Conduct {v}/100 (alert below {note}, safety stop at {lim} or lower)")
    if v < note:
        try:
            alerts.fire("conduct_low", f"Conduct {v}/100", screenshot=False)
        except Exception:
            pass
    if v <= lim:
        smart.conduct_stop(v, lim, "conduct_watch")
        log(f"! SAFETY STOP: Conduct score {v} is at or below {lim} - the bot stops until you resume it from the dashboard.")
        try:
            import brain
            brain.record("stuck", f"conduct safety stop: score {v} <= {lim}", task="conduct_watch", shot=True)
        except Exception:
            pass
    elif smart.conduct_stopped():
        smart.conduct_clear(f"conduct is {v}, above {lim}")
    return True


smart.SMART["conduct_watch"] = conduct_watch
START_VER = [0]
RUN_NOW = [False]        # v150: the dashboard's "run now" button starts a round even while paused
TASK_NOW = [0.0, ""]     # v154: (started at, task name) - a task that never ends is aborted
TASK_LIMIT = 900         # v154: one activity may not run longer than 15 minutes
TASK_LIMITS = {"queue_manager": 1800, "sunset_canyon": 1500}    # v244: the queue manager does several jobs (train, build, donate x20 ...) in one task

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
    if conduct_hold(d):                                      # GUIDE-13
        return
    t = t or {}
    try:
        if find_window():
            smart.join_rally(Game(), sleep, max_troops=t.get("max_troops", 600000),
                             max_armies=t.get("max_armies", 2), quiet=True,
                             min_ap_reserve=t.get("min_ap_reserve", 0),                 # TASK-03
                             max_march_time_minutes=t.get("max_march_time_minutes", 0),
                             target_types=t.get("target_types", "forts"), commander_preset=t.get("commander_preset", 0),
                             daily_cap=t.get("daily_cap", 0), only_players=t.get("only_players", ""))   # GUIDE-14
    except Exception as e:
        if "screen grab failed" not in str(e):
            log(f"! join_rally watch failed: {e!r}")


MARCH_GROUPS = {"rallies": ("rally_fort", "join_rally"), "gathering": ("gather_gems", "gather"),
                "barbarians": ("attack_barbarians",)}


def march_priority(tasks, mc):
    """TASK-06: march tasks run in the dashboard order (march_control.priority_order, e.g. ["rallies", "gathering",
    "barbarians"]); they keep the first places the march tasks had, every other task keeps its place."""
    order = [x for x in (mc.get("priority_order") or []) if x in MARCH_GROUPS]
    if not order:
        return tasks
    rank = {r: i for i, grp in enumerate(order) for r in MARCH_GROUPS[grp]}
    slots = [i for i, t in enumerate(tasks) if t.get("routine") in rank]
    moved = sorted((tasks[i] for i in slots), key=lambda t: rank[t["routine"]])
    out = list(tasks)
    for i, t in zip(slots, moved):
        out[i] = t
    return out


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


def no_screen_error(e):
    """v317: True when the failure only means the server has no screen right now (Remote Desktop
    disconnected / input desktop gone): PIL's OSError('screen grab failed'), our own
    RuntimeError('screen grab failed: ...') from a click pinned at 0,0. That is not a bug in an
    activity - the round loop (same test) moves the session back to the console."""
    return "screen grab failed" in repr(e)


def game_gone_error(e):
    """v320: the game client closed under the activity (crash, self-exit, update). Common.refresh() raises
    RuntimeError('Game window closed'); the round loop then warns the owner and reopens the game
    (game_launcher.ensure_game_running, START on the launcher). That is a game state, not a code fault."""
    return "Game window closed" in repr(e)


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


RECALL_WATCH = [0.0]


def recall_watch():
    """TASK-05: every 30 s while waiting - Auto-Return & Recall (task auto_recall switched on in the dashboard)."""
    if time.time() - RECALL_WATCH[0] < 30:
        return
    RECALL_WATCH[0] = time.time()
    d = cur_data()
    t = next((x for x in d.get("tasks", []) if x.get("routine") == "auto_recall" and x.get("enabled")), None)
    if not t:
        return
    try:
        if find_window():
            smart.auto_recall(Game(), sleep, recall_on_threat=t.get("recall_on_threat", True),
                              cooldown_minutes=t.get("cooldown_minutes", 10))
    except Exception as e:
        watch_error("auto_recall check failed", e)


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
                          react_scout=t.get("react_scout", False),
                          trigger_on_attack=t.get("trigger_on_attack", True),          # TASK-04
                          trigger_on_scout=t.get("trigger_on_scout", t.get("react_scout", False)),
                          shield_duration_hours=t.get("shield_duration_hours", 8),
                          scheduled_shield_times=t.get("scheduled_shield_times", ""))
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
alerts.SETTINGS[0] = lambda: (ctl.data or {}).get("alerts") or {}      # TASK-18


def check_stop():
    if key_down(VK["F12"]):
        raise Stop()


QUICK = [0.0, False, 0.0]   # last poll, busy, last status written from inside a task (v252)


def quick_requests():
    """v137: answer a screenshot request right away, even in the middle of a round (it does not click)."""
    if QUICK[1] or time.time() - QUICK[0] < 3:
        return
    QUICK[0], QUICK[1] = time.time(), True
    try:
        ctl.poll()
        ctl.screenshot_if_asked()
        d = ctl.data or {}                                   # v252: tell the dashboard its command was seen
        new = False
        ar = d.get("action_request")
        if isinstance(ar, dict) and ar.get("id") and str(ar["id"]) != str(getattr(ctl, "action_done", "") or ""):
            new |= kb_guard.command("action", ar["id"], ar.get("do"), "queued",
                                    f"after the current activity ({TASK_NOW[1] or 'round'})")
        pr = d.get("probe_request")
        if pr and pr != getattr(ctl, "probe_done", None):
            new |= kb_guard.command("probe", pr, "probe", "queued", "after the current activity")
        rn = d.get("run_now")
        if rn and rn != getattr(ctl, "run_now_done", None) and TASK_NOW[0]:
            new |= kb_guard.command("run_now", rn, "run_now", "queued", "a round is running - the next one starts right after it")
        if new or (TASK_NOW[0] and time.time() - QUICK[2] > 120):   # the ack (and a fresh status) reach GitHub now
            QUICK[2] = time.time()
            ctl.write_status(state="working", task=f"{TASK_NOW[1] or 'round'}")
    except Exception:
        pass
    finally:
        QUICK[1] = False


CAPTCHA_BUSY = [False]


def captcha_watch(force=False):
    """TASK-09: a verification (captcha) window halts everything: no clicks, screenshot to the dashboard,
    status captcha_required, urgent alert; wait until the dashboard says it is solved and it is really gone."""
    if CAPTCHA_BUSY[0]:
        return
    g = CURRENT_GAME[0]
    if g is None:
        return
    try:
        seen = smart.captcha_visible(g, force=force)
    except Exception:
        return
    alerts.shield_watch()                                    # TASK-18: shield ended -> one alert
    if not seen and smart.NETDROP[0]:
        netdrop_wait(g)                                      # TASK-20: network drop / maintenance
        return
    if not seen and smart.RELOGIN[0]:
        relogin_wait(g)                                      # GUIDE-13: logged in from another device
        return
    if not seen:
        return
    CAPTCHA_BUSY[0] = True
    import control
    task_saved = list(TASK_NOW)
    TASK_NOW[0] = 0                                          # the task timer and the stuck watchdog wait too
    cid = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    CAPTCHA[0] = cid
    try:
        log("! VERIFICATION (captcha) window in the game - every click is stopped until it is solved.")
        control.CITY["captcha"] = {"id": cid, "at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "still": False}
        try:
            ctl.upload_screen("bot: captcha screenshot")
        except Exception as e:
            log(f"  captcha: screenshot upload failed {e!r}")
        try:
            smart.notify("captcha", "⚠️ نافذة تحقق (كابتشا) في اللعبة — البوت متوقف حتى تحلّها ثم اضغط «تم الحل — استئناف»")
        except Exception:
            pass
        last = 0
        while True:
            check_stop()
            LAST_ACTIVITY[0] = time.time()
            ctl.poll()
            if time.time() - last > 30:
                last = time.time()
                ctl.write_status(state="captcha_required", task="verification window - waiting for the owner")
                _touch_pid()
            if game_login.find_login_window():               # v263: it was the game's Log In window, not a captcha
                log("  captcha: it is the game's Log In window - switching to the login wait")
                break
            if str((ctl.data or {}).get("captcha_resume") or "") == cid:
                if smart.captcha_visible(g, force=True):
                    if not control.CITY["captcha"].get("still"):
                        log("  captcha: 'solved' pressed but the window is still there - still waiting")
                        control.CITY["captcha"]["still"] = True
                        try:
                            ctl.upload_screen("bot: captcha screenshot")
                        except Exception:
                            pass
                        last = 0
                else:
                    log("  captcha: solved - Kingbot continues.")
                    break
            time.sleep(5)
    finally:
        if task_saved[0]:
            TASK_NOW[0] = time.time()
        CAPTCHA[0] = None
        control.CITY.pop("captcha", None)
        CAPTCHA_BUSY[0] = False


NET_BACKOFF = (30, 120, 300, 600)                            # TASK-20: 30 s -> 2 min -> 5 min -> 10 min
NET_STATE = {"level": 0, "last": 0.0}


def _net_dialog_button(g):
    """Retry / Reconnect / Confirm / OK on the disconnect dialog -> (x, y) relative or None."""
    try:
        img = g.screenshot()
        h, w = img.shape[:2]
        y0 = int(0.45 * h)
        for x1, y1, x2, y2, t in smart._ocr_boxes(img[y0:int(0.85 * h), int(0.2 * w):int(0.8 * w)], "net_btn.png", 1.6):
            if re.search(r"^(retry|reconnect|confirm|ok|try again|re-?login)$", t.strip(), re.I):
                return ((int(0.2 * w) + (x1 + x2) / 2) / w, (y0 + (y1 + y2) / 2) / h)
    except Exception:
        pass
    return None


def netdrop_wait(g):
    """TASK-20: the game shows a disconnect / reconnecting / maintenance dialog. No rapid tapping: wait with an
    exponential backoff (30 s, 2 min, 5 min, 10 min), then press Retry/Confirm once. Drops close together raise
    the level; after the last level the game client is restarted. 30 quiet minutes reset the level."""
    CAPTCHA_BUSY[0] = True
    task_saved = list(TASK_NOW)
    TASK_NOW[0] = 0
    try:
        now = time.time()
        if now - NET_STATE["last"] > 30 * 60:
            NET_STATE["level"] = 0
        lvl = NET_STATE["level"]
        NET_STATE["last"] = now
        maint = "maintenance" in (smart.NETDROP[1] or "").lower()
        wait = NET_BACKOFF[min(lvl, len(NET_BACKOFF) - 1)] * (2 if maint else 1)
        log(f"! Network drop{' (maintenance)' if maint else ''} - waiting {wait} s before retrying (level {lvl + 1}/{len(NET_BACKOFF)})")
        if lvl == 0:
            try:
                smart.notify("info", "انقطع اتصال اللعبة" + (" (صيانة)" if maint else "") + " — البوت ينتظر ثم يعيد المحاولة تلقائياً")
            except Exception:
                pass
        CAPTCHA[0] = "network"                               # no clicks while waiting
        end = time.time() + wait
        while time.time() < end:
            check_stop()
            LAST_ACTIVITY[0] = time.time()
            ctl.poll()
            ctl.write_status(state="waiting", task=f"network drop - retry in {max(0, int(end - time.time()))} s")
            _touch_pid()
            time.sleep(min(15, max(1, end - time.time())))
        CAPTCHA[0] = None
        if lvl >= len(NET_BACKOFF) - 1:
            log("  network: still down after every backoff step - restarting the game client")
            alerts.fire("on_server_offline", "اللعبة بقيت بلا اتصال بعد كل محاولات الانتظار — البوت يعيد تشغيل اللعبة")
            import subprocess, game_launcher
            for exe in ("MASS.exe", "UnityCrashHandler64.exe"):
                subprocess.run(["taskkill", "/f", "/im", exe], capture_output=True, timeout=30)
            time.sleep(6)
            try:
                if os.path.exists(game_launcher.LAST_TRY_FILE):
                    os.remove(game_launcher.LAST_TRY_FILE)
            except Exception:
                pass
            game_launcher.ensure_game_running(sleep)
            NET_STATE["level"] = 0
            return
        p = _net_dialog_button(g)
        if p:
            g.click_rel(*p)
            log("  network: pressed the dialog's retry/confirm button once")
        time.sleep(8)
        NET_STATE["level"] = lvl + 1
    finally:
        smart.NETDROP[0] = 0
        CAPTCHA[0] = None
        if task_saved[0]:
            TASK_NOW[0] = time.time()
        CAPTCHA_BUSY[0] = False


def relogin_wait(g):
    """GUIDE-13: the game says the account was opened on another device. Wait relogin_cooldown_min minutes
    (default 10, dashboard) before reconnecting, so the owner can play on the other device without being kicked."""
    CAPTCHA_BUSY[0] = True
    task_saved = list(TASK_NOW)
    TASK_NOW[0] = 0
    try:
        mins = max(1, min(240, int((ctl.data or {}).get("relogin_cooldown_min") or 10)))
        log(f"The account was opened on another device - waiting {mins} min before logging in again.")
        try:
            smart.notify("info", f"دخل أحد للحساب من جهاز آخر — البوت ينتظر {mins} دقيقة ثم يعود")
        except Exception:
            pass
        end = time.time() + mins * 60
        CAPTCHA[0] = "relogin"                               # no clicks while waiting
        while time.time() < end:
            check_stop()
            LAST_ACTIVITY[0] = time.time()
            ctl.poll()
            ctl.write_status(state="waiting", task=f"logged in on another device - back in {max(0, int((end - time.time()) / 60))} min")
            _touch_pid()
            time.sleep(30)
        CAPTCHA[0] = None
        for name in ("btn_confirm_blue", "btn_confirm_word"):
            p = g.find_image(name, 0.8)
            if p:
                g.click_rel(*p[0]); time.sleep(8)
                break
        else:
            g.click_rel(0.5, 0.62); time.sleep(8)            # the dialog's single button
        log("  relogin: reconnected after the cooldown")
    finally:
        smart.RELOGIN[0] = 0
        CAPTCHA[0] = None
        if task_saved[0]:
            TASK_NOW[0] = time.time()
        CAPTCHA_BUSY[0] = False


WAIT_JITTER = [0.0]     # TASK-08: +/- fraction applied to every wait (smart_schedule.jitter_percent)


def sleep(sec):
    captcha_watch()                                          # TASK-09 (checks every 10 s at most)
    try:
        session_watch(every=20)                              # v252: a disconnect in the middle of a task
    except Exception:
        pass
    if WAIT_JITTER[0] > 0 and sec > 0:
        sec = sec * (1 + random.uniform(-WAIT_JITTER[0], WAIT_JITTER[0]))
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
            kb_guard.beat()
            if n % 4 == 0:
                game_hung_check()
            t0, tname = TASK_NOW[0], TASK_NOW[1]
            lim = TASK_LIMITS.get(str(tname or "").split(" ")[0], TASK_LIMIT)
            if t0 and time.time() - t0 > lim:
                log(f"! task '{tname}' has been running for over {lim // 60} minutes "
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
                try:                                   # BRAIN-01: a stuck task is an incident (with a picture)
                    import brain
                    brain.record("stuck", f"no progress for {limit // 60} minutes", task=tname or "-")
                    time.sleep(8)                      # let the screenshot upload before the restart
                    brain.upload(force=True)
                except Exception:
                    pass
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
        if smart.signed_out():                               # v258: signed out - stop answering the game
            return
        if game_login.find_login_window():                   # v262: the game waits for a login - no clicks
            return
        claude_channel.check(sleep)
        captcha_watch()                                      # TASK-09
        shield_watch()
        recall_watch()
        attack_watch()
        session_watch()
        stream_keeper()
        rn = (ctl.data or {}).get("run_now")
        if rn and rn != getattr(ctl, "run_now_done", None):
            ctl.run_now_done = rn
            RUN_NOW[0] = True
            kb_guard.command("run_now", rn, "run_now", "running", "round started")
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
    kb_guard.command("probe", req, "probe", "received")
    g = get_game()
    if g is None:
        log("! Probe skipped: game window not found.")
        kb_guard.command("probe", req, "probe", "failed", "game window not found")
        return
    import control, server_config
    sent = []
    def save(name, path):                                    # v252: ctl.root is a GitHub address, not a folder
        folder = os.path.dirname(server_config.path("screen"))
        if control._gh_put_bytes(f"{folder}/{name}.jpg", control._seal_bytes(open(path, "rb").read()), "bot: probe " + name):
            sent.append(name)
    log("Taking probe screenshots for Claude ...")
    kb_guard.command("probe", req, "probe", "running")
    kb_guard.routine("probe")
    try:
        smart.probe_screens(g, sleep, save)
        kb_guard.command("probe", req, "probe", "done" if sent else "failed", f"{len(sent)} picture(s): " + ", ".join(sent))
    except (Stop, SystemExit, pyautogui.FailSafeException):
        raise
    except Exception as e:
        kb_guard.command("probe", req, "probe", "failed", repr(e)[:150])
        kb_guard.error(f"probe: {e!r}")
    finally:
        kb_guard.routine(None)



# ---------------- v144: live stream keeper (OBS virtual camera -> VDO.Ninja in a minimized Chrome) ----------------
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


def keep_screen_alive_ok():
    """v252: after a 'screen grab failed', only call tscon when the session really is disconnected
    (a black/locked screen with an active session is not fixed by tscon and used to loop)."""
    if kb_guard.session_disconnected():
        return False
    try:
        g = get_game()
        if g:
            g.screenshot()
        return True
    except Exception:
        return keep_screen_alive()


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


SIGNOUT_STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signout_sched.json")


def signout_due():
    """v258: dashboard 'sign_out_schedule' {enabled, time_local 'HH:MM', tz_min, time_utc, days [0..6] (Mon=0 in the
    owner's own week, empty = every day)}.
    Due once per day, from that time until 60 minutes after it."""
    cfg = (ctl.data or {}).get("sign_out_schedule") or {}
    if not cfg.get("enabled") or not cfg.get("time_utc"):
        return False
    try:                                                     # the owner's own clock when tz_min is sent
        local = cfg.get("time_local") and cfg.get("tz_min") is not None
        tz = int(cfg["tz_min"]) if local else 0
        hh, mm = (int(x) for x in str(cfg["time_local"] if local else cfg["time_utc"]).split(":")[:2])
    except Exception:
        return False
    now = datetime.datetime.utcnow() + datetime.timedelta(minutes=tz)     # days / time are the owner's
    days = cfg.get("days") or []
    if days and now.weekday() not in days:
        return False
    at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if not (at <= now < at + datetime.timedelta(minutes=60)):
        return False
    st = load_json(SIGNOUT_STATE, {})
    if st.get("day") == now.strftime("%Y-%m-%d"):
        return False
    save_json(SIGNOUT_STATE, {"day": now.strftime("%Y-%m-%d")})
    log(f"Scheduled sign-out ({cfg.get('time_local') or cfg.get('time_utc')}).")
    return True


def _save_action_done(cid):
    """Before an exit: remember the action so the restarted bot does not run it again."""
    try:
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "action_done.txt"), "w").write(str(cid))
    except Exception:
        pass


def logout_game(g, cid=None):
    """ADM-03: stop field work first (the current activity has already ended - actions run between
    activities; no new march is sent), then Settings > Account > Sign out with its confirmation."""
    kb_guard.routine("logout_game")
    kb_guard.command("action", cid, "logout_game", "running", "جاري تسجيل الخروج من اللعبة")
    ctl.write_status(state="working", task="جاري تسجيل الخروج من اللعبة")
    res = smart.sign_out(g, sleep, "dashboard")
    kb_guard.routine(None)
    if res == "done":
        kb_guard.command("action", cid, "logout_game", "done", "تم تسجيل الخروج من اللعبة")
        ctl.write_status(state="paused", task="تم تسجيل الخروج من اللعبة")
    return res


def conduct_stop_wait():
    """URGENT-02: the Conduct safety stop - no game actions; answer the dashboard; re-read the score every 3 hours."""
    import json as _j
    info = load_json(smart.CONDUCT_STOP_FILE, {}) or {}
    log(f"Conduct safety stop: score {info.get('score')} <= {info.get('limit')} - the bot does nothing in the game until you resume it.")
    last = time.time()
    while smart.conduct_stopped():
        check_stop()
        LAST_ACTIVITY[0] = time.time()                       # v303: a deliberate wait is not "stuck"
        try:
            ctl.poll()
            ctl.screenshot_if_asked()
            action_if_asked()
        except (Stop, SystemExit):
            raise
        except Exception:
            pass
        ctl.write_status(state="paused", task=f"Conduct safety stop ({info.get('score')}/100 <= {info.get('limit')})")
        if time.time() - last > 3 * 3600:
            last = time.time()
            try:
                g = get_game()
                if g:
                    conduct_watch(g, sleep, stop_below=info.get("limit") or 80)
            except Exception:
                pass
        time.sleep(30)


def signed_out_wait():
    """The account is signed out: click nothing. Answer the dashboard and look at the screen every 2 minutes -
    when the city or the map shows again, someone logged in and the bot works again."""
    log("The game account is signed out - the bot waits (no clicks) until someone logs in again.")
    last_look = 0
    while smart.signed_out():
        check_stop()
        LAST_ACTIVITY[0] = time.time()                       # v303: a deliberate wait is not "stuck"
        try:
            ctl.poll()
            ctl.screenshot_if_asked()
            action_if_asked()
        except (Stop, SystemExit):
            raise
        except Exception:
            pass
        if time.time() - last_look > 120:
            last_look = time.time()
            try:
                g = get_game()
                if g and smart.what_screen(g) in ("city", "map"):
                    smart.clear_signed_out("the game is logged in again")
                    break
            except Exception:
                pass
            ctl.write_status(state="paused", task="signed out of the game - waiting for a new login")
        time.sleep(15)


def login_wait():
    """v262 LOGIN-01: the game shows its Log In window (new account, never signed in). Click nothing in the game;
    the dashboard shows a form, the customer sends the email and then the code (actions game_login_email /
    game_login_code, done by game_login.py). Ends when the Log In window is gone."""
    log("The game is waiting for a login (Log In window) - the bot waits for the email + code from the dashboard.")
    if game_login.STATE.get("stage") in ("", "logged_in"):
        game_login.set_stage("need_email", "اللعبة تنتظر تسجيل الدخول - أدخل البريد من لوحة التحكم")
        try:
            smart.notify("info", "الحساب على هذا السيرفر يحتاج تسجيل دخول في اللعبة - افتح لوحة التحكم وأدخل البريد ثم الكود.")
        except Exception:
            pass
    last = 0
    while game_login.find_login_window(15):
        check_stop()
        LAST_ACTIVITY[0] = time.time()                       # v303: waiting for the customer's email/code is not "stuck"
        try:
            session_watch()                                  # v269: keep the screen alive (Remote Desktop closed)
            ctl.poll()
            ctl.screenshot_if_asked()
            action_if_asked()
        except (Stop, SystemExit):
            raise
        except Exception:
            pass
        if time.time() - last > 60:
            last = time.time()
            ctl.write_status(state="paused", task="بانتظار تسجيل الدخول في اللعبة من لوحة التحكم")
            try:                                             # v266: a fix for the login itself can arrive meanwhile
                if local_version() != START_VER[0] or (int(time.time() // 60) % 5 == 0 and check_and_update(log)):
                    sys.exit(RESTART_CODE)
            except SystemExit:
                raise
            except Exception:
                pass
        time.sleep(5)
    if game_login.STATE.get("stage") not in ("", "logged_in"):
        game_login.set_stage("logged_in", "نافذة الدخول أُغلقت")
    log("The Log In window is gone - the bot works again.")
    ctl.write_status(state="working", task="تم تسجيل الدخول - يبدأ العمل")
    time.sleep(10)


def _after_console():
    """Screen size + game focus once the session is on the console again."""
    for w, h in ((1280, 800), (1280, 1024), (1280, 720), (1366, 768)):
        if _set_resolution(w, h):
            log(f"  keep-screen: screen {w}x{h}")
            break
    time.sleep(2)
    g = get_game()
    if g:
        g.focus()


def session_watch(every=60):
    """v170: the screen goes off when Remote Desktop disconnects, and then every click is lost
    (the pointer stays at 0,0). v252: kb_guard.session_guard - tscon with a 20 s timeout, the result is
    checked, and failures back off 1 / 2 / 5 / 10 minutes instead of hanging or looping every minute."""
    if time.time() - SESSION_WATCH[0] < every:
        return kb_guard.HEALTH.get("session") != "disconnected"
    SESSION_WATCH[0] = time.time()
    if ((ctl.data or {}).get("keep_screen") or {}).get("enabled", True) is False:
        return True
    no_sleep()
    return kb_guard.session_guard(log, after_ok=_after_console)


RUN_TASK_OK = ("rally_fort", "attack_barbarians", "gather", "tavern", "merchant", "alliance_help", "collect_city",
               "vip_chests", "train_troops", "sunset_canyon", "materials")
NO_GAME_ACTIONS = ("conduct_resume", "purge_characters", "install_obs", "update_now")


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
    do = req.get("do")
    kb_guard.command("action", req["id"], do, "received")
    if do in ("game_login_email", "game_login_code"):        # v262 LOGIN-01: no game window needed, never log the data
        log(f"Dashboard action: {do}")
        kb_guard.command("action", req["id"], do, "running", "")
        try:                                                 # v269: a disconnected Remote Desktop leaves no screen to read
            session_watch(0)
        except Exception:
            pass
        res = game_login.handle(req)
        kb_guard.command("action", req["id"], do, "done" if res == "done" else "failed",
                         "" if res == "done" else res)
        try:
            import control
            control.CITY["action_done"] = str(req["id"])
            ctl.write_status(state="paused", task="تسجيل الدخول في اللعبة: " + (game_login.STATE.get("detail") or do))
        except Exception:
            pass
        return
    if do in NO_GAME_ACTIONS:                                # URGENT-02/03, v303: no game window needed
        log(f"Dashboard action: {do}")
        res = _do_action(None, req)
        _save_action_done(req.get("id"))
        kb_guard.command("action", req["id"], do, "failed" if str(res or "").startswith("failed") else "done",
                         str(res or "") if str(res or "").startswith("failed") else "")
        try:
            import control
            control.CITY["action_done"] = str(req["id"])
            ctl.write_status(state="working", task=f"dashboard: {do} done")
        except Exception:
            pass
        return
    steps_in = req.get("steps") if do == "multi" and isinstance(req.get("steps"), list) else [req]
    try:
        login_up = bool(game_login.find_login_window(5))
    except Exception:
        login_up = False
    if login_up:                                             # v307: the game waits for a login - never click into it
        ok_steps = [st for st in steps_in if st.get("do") in NO_GAME_ACTIONS]
        log(f"Dashboard action: {do} - the game is waiting for a login, only "
            + (", ".join(st.get("do") for st in ok_steps) or "nothing") + " can run now")
        for st in ok_steps:
            try:
                _do_action(None, st)
            except Exception as e:
                log(f"  ! {st.get('do')}: {e!r}")
        _save_action_done(req.get("id"))
        skipped = [st.get("do") for st in steps_in if st not in ok_steps]
        kb_guard.command("action", req["id"], do, "failed" if skipped else "done",
                         ("اللعبة تنتظر تسجيل الدخول - أعد المحاولة بعد الدخول: " + ", ".join(skipped)) if skipped else "")
        return
    g = get_game()
    if g is None:
        kb_guard.command("action", req["id"], do, "failed", "game window not found")
        return
    log(f"Dashboard action: {do}")
    steps = steps_in
    import control
    results = []
    for i, step in enumerate(steps[:12]):
        try:
            control.CITY["action_progress"] = {"id": str(req["id"]), "step": i, "of": len(steps), "do": step.get("do")}
            if do == "multi":
                ctl.write_status(state="working", task=f"assistant: {step.get('do')} ({i + 1}/{len(steps)})")
                log(f"  assistant step {i + 1}/{len(steps)}: {step.get('do')}")
        except Exception:
            pass
        kb_guard.command("action", req["id"], do, "running",
                         f"step {i + 1}/{len(steps)}: {step.get('do')}" if do == "multi" else "")
        kb_guard.routine("action:" + str(step.get("do")))
        try:
            res = _do_action(g, step)
        finally:
            kb_guard.routine(None)
        if res and res != "done":
            results.append(f"{step.get('do')}: {res}")
    final = "done" if not results else ("failed" if len(results) == len(steps[:12]) else "partial")
    kb_guard.command("action", req["id"], do, final, "; ".join(results)[:200])
    try:                                                     # v137: tell the dashboard at once
        control.CITY["action_progress"] = {"id": str(req["id"]), "step": len(steps), "of": len(steps)}
        control.CITY["action_done"] = str(req["id"])
        ctl.write_status(state="working", task=f"dashboard: {do} {final}")
    except Exception:
        pass


# TASK-17: the dashboard may only press these. There is no free (X, Y) tap: a free tap could hit
# gems / INSTANT / purchase buttons or the Settings page, which the owner's rules forbid.
SAFE_TAPS = ("back", "close_popups", "gem_no", "city_map")


def safe_tap(g, target):
    from common import close_gem_dialogs, recover_screen, press_key
    if target not in SAFE_TAPS:
        log(f"  ! safe_tap: '{target}' is not on the safe list - nothing pressed")
        return False
    g.focus()
    if target == "gem_no":
        close_gem_dialogs(g)                 # presses NO only
    elif target == "back":
        press_key("esc")                     # refused by press_key when nothing is open (ESC = quit dialog)
    elif target == "close_popups":
        recover_screen(g)                    # NO on gem windows, BACK arrow, ESC - back to the plain view
    elif target == "city_map":
        press_key("space")                   # refused by press_key when a panel is open
    sleep(1)
    close_gem_dialogs(g)
    return True


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
        elif do == "read_queues":                                # v197: Queue Overview read, for the live monitor
            ctl.write_status(state="working", task="reading the Queue Overview")
            queue_manager.scan(g, sleep)
        elif do == "queue_manager":                              # v197: run the queue task now (dashboard / test)
            t = next((x for x in queue_tasks(list((ctl.data or {}).get("tasks") or []))
                      if x.get("routine") == "queue_manager"), {})
            if isinstance(req.get("opts"), dict):                 # a one-off test with other switches
                t = dict(t, **req["opts"])
            import inspect
            params = inspect.signature(queue_manager.run).parameters
            ctl.write_status(state="working", task="queue manager")
            queue_manager.run(g, sleep, **{k: v for k, v in t.items() if k in params and k not in ("g", "sleep")})
        elif do in ("capture_screen", "safe_tap"):               # TASK-17: live screenshot + safe button list only
            ok = safe_tap(g, req.get("target")) if do == "safe_tap" else True
            sleep(2)
            up = ctl.upload_screen("bot: screenshot (" + do + ")")
            log(f"  {do}{' ' + str(req.get('target')) if do == 'safe_tap' else ''}: "
                + ("done" if ok else "refused") + (", picture uploaded" if up else ", picture upload failed"))
        elif do == "purge_characters":                             # URGENT-03: clear this server's cached characters
            smart.purge_characters("dashboard")
        elif do == "conduct_resume":                               # URGENT-02: the owner resumes after a Conduct safety stop
            smart.conduct_clear("resumed from the dashboard")
        elif do == "read_conduct":                                 # URGENT-02: read the Conduct Score now
            v = smart.read_conduct(g, sleep) if g else None
            if v is None:
                return "conduct not read"
        elif do in ("sign_out", "logout_game"):                   # v258 / ADM-03: dashboard button
            return logout_game(g, req.get("id"))
        elif do == "rollback":                                   # ADM-02: back to the previous version
            import updater, control
            v = updater.rollback(req.get("version"), log)
            if not v:
                return "failed: no older backup on this server"
            control.CITY["action_done"] = str(req.get("id", ""))
            kb_guard.command("action", req.get("id"), "rollback", "done", f"back to v{v} - updates held")
            _save_action_done(req.get("id"))
            _status_then_exit(state="restarting", task=f"rolled back to v{v}")
        elif do == "release_updates":                            # ADM-02: undo the rollback hold
            import updater
            updater.unpin()
            log("  updates released - the next check installs the newest version")
        elif do == "update_now":                                 # ADM-02: check GitHub now
            import updater, control                              # v267: 'control' is local in this function
            if updater.check_and_update(log):
                control.CITY["action_done"] = str(req.get("id", ""))
                kb_guard.command("action", req.get("id"), "update_now", "done", "new version installed - restarting")
                _save_action_done(req.get("id"))
                _status_then_exit(state="restarting", task="installing an update")
        elif do == "install_obs":                                # v289: OBS for the live stream on a new server
            import subprocess
            ps1 = os.path.join(BASE, "tools", "install_obs.ps1")
            log("Installing OBS Studio for the live stream (tools/install_obs.ps1) ...")
            try:
                r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
                                   capture_output=True, timeout=1200, creationflags=0x08000000)
                out = (r.stdout or b"").decode("utf-8", "replace").strip().splitlines()[-6:]
                err = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-3:]
                for ln in out + err:
                    log("  obs install: " + ln[:160])
                if r.returncode != 0:
                    return "failed: install_obs exit " + str(r.returncode)
            except Exception as e:
                log(f"  ! obs install failed: {e!r}")
                return "failed: " + repr(e)[:100]
        elif do == "signed_in":                                  # the owner logged in again
            smart.clear_signed_out("dashboard")
        elif do == "vision_scan":                                # v254: learn every picture visible on this screen
            import common, glob
            names = sorted({os.path.splitext(os.path.basename(f))[0] for d in (common.TEMPL_DIR, common.BUILTIN_DIR)
                            for f in glob.glob(os.path.join(d, "*.png"))})
            img = g.screenshot()
            before = len(common._scale_table().get(f"{g.w}x{g.h}", {}))
            for n in names:
                common._WIDE_TRIED.pop((f"{g.w}x{g.h}", n), None)
                g.find_image(n, 0.82, img=img)
            after = len(common._scale_table().get(f"{g.w}x{g.h}", {}))
            log(f"  vision_scan: {len(names)} pictures checked, {max(0, after - before)} learned on this screen")
        elif do == "test_alert":                                 # TASK-18: dashboard "Send test alert"
            ok = alerts.fire("test", "رسالة تجريبية من لوحة التحكم — التنبيهات تعمل", screenshot=True, wait=True)
            log("  test alert " + ("sent" if ok else "not sent"))
        elif do == "restart_game":                               # MOD-03: assistant quick server control
            ctl.write_status(state="working", task="restarting the game (from the dashboard)")
            log("  restarting the game client (dashboard request)")
            import subprocess, game_launcher
            for exe in ("MASS.exe", "UnityCrashHandler64.exe"):
                subprocess.run(["taskkill", "/f", "/im", exe], capture_output=True)
            sleep(6)
            try:
                if os.path.exists(game_launcher.LAST_TRY_FILE):
                    os.remove(game_launcher.LAST_TRY_FILE)       # start again at once, not after the 90 s guard
            except Exception:
                pass
            game_launcher.ensure_game_running(sleep)
            smart.notify("info", "أُعيد تشغيل اللعبة بطلب من لوحة التحكم")
            return
        elif do == "restart_bot":                                # MOD-03: assistant quick server control
            import control
            log("Restarting Kingbot (dashboard request) ...")
            try:
                control.CITY["action_done"] = str(req.get("id", ""))
                kb_guard.command("action", req.get("id"), "restart_bot", "done", "the bot restarts now")
                _save_action_done(req.get("id"))                # do not restart again after the restart
                ctl.write_status(state="working", task="restarting the bot (from the dashboard)")
            except Exception:
                pass
            sys.exit(RESTART_CODE)
        elif do == "read_profile":
            smart.read_profile(g, sleep)
        elif do == "read_commanders":
            smart.read_commanders(g, sleep)
        elif do == "run_task":                                   # v316: dashboard "test now" - one task, once
            routine = str(req.get("routine") or "")
            fn = smart.SMART.get(routine)
            if routine not in RUN_TASK_OK or not fn:
                log(f"  ! run_task: '{routine}' cannot be started from the dashboard")
                return "failed: not allowed"
            import inspect
            params = req.get("params") if isinstance(req.get("params"), dict) else {}
            ok_args = set(inspect.signature(fn).parameters)
            kw = {k: v for k, v in params.items() if k in ok_args}
            log(f"  run_task: {routine} once now {kw}")
            fn(g, sleep, **kw)
        elif do == "switch_character":
            prev = load_json(ROT_FILE, {}).get("name") or _active_char()
            res = smart.switch_character(g, sleep, name=req.get("name", ""), kingdom=req.get("kingdom", ""))
            smart.read_characters(g, sleep)
            cur = _active_char()
            if res in ("switched", "already") and (not cur or _same(cur, req.get("name", ""))):
                mark_active_char(req.get("name", ""), prev=prev)   # v136: rotation continues from this character
                _refresh_after_switch()
        else:                                                    # v252: never mark an unknown action as done
            log(f"  ? dashboard action '{do}' is not built in this bot - nothing done")
            return "unknown"
    except (Stop, SystemExit, pyautogui.FailSafeException):
        raise
    except Exception as e:
        log(f"! dashboard action {do} failed: {e!r}")
        if no_screen_error(e):                               # v317: no screen is not a bug report
            return "failed: the server screen is not available"
        if game_gone_error(e):                               # v320: nor is a game that closed
            return "failed: the game window closed"
        kb_guard.error(f"action {do}: {e!r}")
        try:
            import brain
            brain.record("error", repr(e), task="action:" + str(do))
        except Exception:
            pass
        return "failed: " + repr(e)[:120]
    try:
        recover_screen(g)
    except Exception:
        pass
    return "done"


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
                 "tavern": [8, 10], "sunset_canyon": [120, 180], "hunt_guardians": [60, 90], "merchant": [30, 45],
                 "heal": [30, 45], "research": [30, 45], "build_upgrade": [30, 45], "read_mail": [20, 30], "read_profile": [60, 90], "read_characters": [720, 720], "read_marches": [15, 20], "materials": [60, 90], "read_commanders": [10080, 10080], "events": [120, 150]}
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
    since = load_json(ROT_FILE, {}).get("since")
    control.CITY["rotation"] = {"char": slot.get("name") if slot else None, "preset": (slot or {}).get("preset") or "",
                                "until": datetime.datetime.fromtimestamp(until).astimezone().isoformat(timespec="seconds") if until else None,
                                "since": datetime.datetime.fromtimestamp(since).astimezone().isoformat(timespec="seconds") if since else None,
                                "note": note}


SWITCH_GAP_MIN = 10          # GUIDE-16: at least 10 minutes between two character switches


def _turn_minutes(slot):
    """GUIDE-16: a turn lasts 'minutes', or a random time between 'minutes' and 'minutes_max' when that is set."""
    lo = float(slot.get("minutes") or 120)
    hi = float(slot.get("minutes_max") or 0)
    return random.uniform(lo, hi) if hi > lo else lo


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


SCHED_PROF = [""]


def _hm(t):
    try:
        h, m = str(t).strip().split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def schedule_profile(settings, now=None):
    """GUIDE-17: settings['schedule_profiles'] = [{from: 'HH:MM', to: 'HH:MM', profile: name, on: bool}] in UTC.
    Inside a window the bot plays that saved profile (tasks + loop); when the window ends it goes back to the user's
    own settings by itself (nothing is overwritten). Character rotation keeps working - only the activities change."""
    import control
    rows = [r for r in (settings.get("schedule_profiles") or []) if isinstance(r, dict) and r.get("on", True) is not False]
    presets = settings.get("presets") or {}
    t = now if now is not None else datetime.datetime.utcnow()
    cur = t.hour * 60 + t.minute
    hit = None
    for r in rows:
        a, b = _hm(r.get("from")), _hm(r.get("to"))
        if a is None or b is None or a == b or not r.get("profile"):
            continue
        if (a < b and a <= cur < b) or (a > b and (cur >= a or cur < b)):
            hit = r
            break
    name = (hit or {}).get("profile") or ""
    p = presets.get(name) if name else None
    if name and not p:
        name = ""
    if name != SCHED_PROF[0]:
        log(f"Scheduled profile: {'now using ' + repr(name) if name else 'window ended - back to your own settings'}")
        SCHED_PROF[0] = name
    if not name:
        control.CITY.pop("sched_profile", None)
        return settings
    control.CITY["sched_profile"] = {"profile": name, "from": hit.get("from"), "to": hit.get("to")}
    eff = dict(settings)
    eff["tasks"] = p.get("tasks") or settings.get("tasks", [])
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
    slots = [x for x in (rot.get("slots") or []) if x.get("name") and x.get("on", True) is not False]   # GUIDE-16: in the rotation or not
    if rot.get("star_only"):                                   # GUIDE-16: switch only between the starred characters
        stars = [x for x in slots if x.get("star")]
        slots = stars or slots
    if not rot.get("enabled") or not slots:
        EFF[0] = None
        import control
        control.CITY.pop("rotation", None)
        return settings
    st = load_json(ROT_FILE, {})
    now = time.time()
    sn = str(rot.get("switch_now") or "")                       # GUIDE-16: "Switch now" from the dashboard
    if sn and sn != st.get("switch_now_done"):
        st["switch_now_done"] = sn
        if now - float(st.get("since") or 0) >= SWITCH_GAP_MIN * 60:
            st["until"] = 0
            log("Character rotation: 'Switch now' from the dashboard")
        else:
            log(f"Character rotation: 'Switch now' ignored - less than {SWITCH_GAP_MIN} min since the last switch")
        save_json(ROT_FILE, st)
    idx = next((i for i, x in enumerate(slots) if _same(x["name"], st.get("name"))), None)
    if idx is None:
        cur = _active_char() or st.get("name")
        i_cur = next((i for i, x in enumerate(slots) if _same(x["name"], cur)), None)
        if i_cur is not None:                               # start with the character that is already open
            log(f"Character rotation: starting with {slots[i_cur]['name']} (already open in the game)")
            if st.get("name") and not _same(st.get("name"), slots[i_cur]["name"]):
                _swap_char_files(st.get("name"), slots[i_cur]["name"])   # (no name yet: the files already belong to it)
            st = {"name": slots[i_cur]["name"], "until": now + _turn_minutes(slots[i_cur]) * 60, "fails": 0, "skip": 0, "since": now,
                  "switch_now_done": st.get("switch_now_done")}
            save_json(ROT_FILE, st)
            idx = i_cur
    target = None
    if idx is None:
        target = st.get("skip", 0) % len(slots)
    elif now >= st.get("until", 0):
        if len(slots) == 1:
            st["until"] = now + _turn_minutes(slots[0]) * 60
            save_json(ROT_FILE, st)
        else:
            target = (idx + 1 + st.get("skip", 0)) % len(slots)
            if target == idx:                               # every other character was skipped: stay on this one a full turn
                log(f"Character rotation: staying on {slots[idx]['name']} for another {slots[idx]['minutes']} min")
                st.update(until=now + _turn_minutes(slots[idx]) * 60, skip=0, fails=0)
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
            try:                                            # v309: the 60% OCR guard must not compare two characters
                import control
                control.RESOURCES.clear()
            except Exception:
                pass
            mins = _turn_minutes(slot)
            st = {"name": slot["name"], "until": time.time() + mins * 60, "fails": 0, "skip": 0, "since": time.time(),
                  "switch_now_done": st.get("switch_now_done")}
            save_json(ROT_FILE, st)
            idx = target
            smart.notify("info", f"تبديل الشخصيات: البوت يعمل الآن على {slot['name']} بإعداد «{slot.get('preset') or 'الإعدادات الرئيسية'}» لمدة {round(mins)} دقيقة")
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


TASK_RESULT = {}          # v252: routine -> {at, ok, result} of its last run (status.json city.task_results)
UNUSED_LOGGED = {}
TASK_META_KEYS = {"routine", "times", "enabled", "every", "pause_after", "on", "max_armies"}


def _unknown_routine(name):
    """v153: a task switched on in the dashboard that this bot has no activity for. Log it once a
    day instead of every round (events / merchant / conduct_watch are in this state)."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    if UNKNOWN_ONCE.get(name) == today:
        return
    UNKNOWN_ONCE[name] = today
    log(f"  ? routine '{name}' is switched on in the dashboard but not built yet - skipped")
    try:                                                     # v252: the dashboard shows "not built yet"
        import control as _c
        _c.CITY.setdefault("task_support", {})[name] = {"missing": True}
    except Exception:
        pass


FIELD_TASKS = {"gather", "gather_gems", "rally_fort", "join_rally", "attack_barbarians", "hunt_guardians", "scout"}
CONDUCT_LOGGED = [0.0]


def conduct_hold(settings):
    """GUIDE-13: while the governor's Conduct score (read from the profile) is below conduct_min (default 61),
    field activities (marches, gathering, scouting) wait; city tasks go on. Resumes by itself at 61+."""
    import control
    try:
        v = int(str((control.CITY.get("profile") or {}).get("conduct") or "").replace(",", "") or 0)
    except Exception:
        v = 0
    lim = int((settings or {}).get("conduct_min") or 61)
    if not v or v >= lim:
        return False
    if time.time() - CONDUCT_LOGGED[0] > 1800:
        CONDUCT_LOGGED[0] = time.time()
        log(f"Conduct score {v} is below {lim}: marches / gathering / scouting wait, city tasks go on.")
    return True


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
    if not any(t.get("routine") == "events" for t in tasks):   # TASK-12: Event Milestone Claimer (off until enabled)
        tasks.append({"routine": "events", "times": 1, "enabled": False})
    mt = settings.get("merchant_tavern") or {}              # TASK-11: Mysterious Merchant & Tavern chests
    if isinstance(mt, dict) and mt:
        for t in tasks:
            if t.get("routine") == "tavern" and "tavern_free_chests" in mt:
                t["enabled"] = bool(mt.get("tavern_free_chests"))
            if t.get("routine") == "merchant":
                t["free_refresh"] = bool(mt.get("merchant_free_refresh"))   # resources only - always, not a choice
    eh = settings.get("events_hunter") or {}                 # TASK-10: Sunset Canyon & Guardians hunter
    if isinstance(eh, dict) and eh:
        for t in tasks:
            if t.get("routine") == "sunset_canyon" and "sunset_canyon_enabled" in eh:
                t["enabled"] = bool(eh.get("sunset_canyon_enabled"))
        if eh.get("guardians_enabled") and not any(t.get("routine") == "hunt_guardians" for t in tasks):
            tasks.append({"routine": "hunt_guardians", "times": 1, "enabled": True,
                          "max_attacks": int(eh.get("guardians_max_attacks") or 2)})
    tasks = queue_tasks(tasks)                               # v197: one Queue Overview task
    tasks = march_priority(tasks, settings.get("march_control") or {})   # TASK-06
    smart.MARCH_CONTROL.clear(); smart.MARCH_CONTROL.update(settings.get("march_control") or {})
    smart.COMMANDER_PRESETS.clear(); smart.COMMANDER_PRESETS.update(settings.get("commander_presets") or {})   # TASK-07
    qm_on = any(t.get("routine") == "queue_manager" and t.get("enabled", True) for t in tasks)
    for t in tasks:
        if not t.get("enabled", True):
            continue
        name = t["routine"]
        if qm_on and name in QM_REPLACED:
            continue
        if name in FIELD_TASKS and conduct_hold(settings):     # GUIDE-13: conduct score below 61
            continue
        try:                                                 # v137: dashboard read requests between activities
            ctl.poll()
            if (ctl.data or {}).get("action_request") or (ctl.data or {}).get("probe_request"):
                action_if_asked()
                probe_if_asked()
        except (Stop, SystemExit, pyautogui.FailSafeException):
            raise
        except Exception as e:
            log(f"! dashboard request between activities failed: {e!r}")
        if smart.signed_out():                               # v258: signed out from the dashboard - end the round
            log("Signed out of the game - the rest of this round is skipped.")
            return
        try:
            recover_screen(g)
        except Exception as e:
            if no_screen_error(e) or game_gone_error(e):     # v317/v320: no screen / no game - stop the round now,
                raise                                        # do not start the next activity blind
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
        try:                                                 # PLAN-01..04: the slot's subscription tier
            import plans
            ok, why = plans.allowed(name, ctl.data or {})
        except Exception:
            ok, why = True, ""
        if not ok:
            log(f"  - plan: {why}")
            try:
                import control
                control.CITY.setdefault("plan_skipped", {})[name] = why
            except Exception:
                pass
            continue
        if name.startswith("leader_") and name not in routines and name not in smart.SMART:
            log(f"  - {name}: أمر القائد قيد التطوير (قريباً) - تم تخطيه")
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
            scr0 = None
            try:
                scr0 = smart.what_screen(g)
                log(f"  screen: {scr0}")     # v176: what the task starts on
            except Exception:
                pass
            try:
                import brain                                  # BRAIN-01: the bot's memory of its failures
                brain.task_start(name, scr0)
            except Exception:
                brain = None
            TASK_NOW[0], TASK_NOW[1] = time.time(), name
            kb_guard.routine(name)
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
                    unused = sorted(k for k in t if k not in params and k not in TASK_META_KEYS)
                    if unused and UNUSED_LOGGED.get(name) != tuple(unused):    # v252: options the activity ignores
                        UNUSED_LOGGED[name] = tuple(unused)
                        log(f"  ({name}: dashboard options not used by this activity: {', '.join(unused[:8])})")
                        import control as _c
                        _c.CITY.setdefault("task_support", {})[name] = {"ignored_options": unused[:12]}
                    ok = fn(g, sleep, **opts)
                TASK_RESULT[name] = {"at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                     "ok": ok is not False, "result": ok if isinstance(ok, str) else None}
                if ok is False and brain:
                    try:
                        brain.record("fail", brain.last_warning() or f"{name} returned False", task=name)
                    except Exception:
                        pass
            except (Stop, NewSettings, SystemExit, pyautogui.FailSafeException):
                raise
            except Exception as e:
                if no_screen_error(e) or game_gone_error(e):    # v317/v320: not a code fault - the round
                    why = "no screen" if no_screen_error(e) else "game closed"   # loop reconnects / reopens
                    log(f"  {name}: stopped - " + ("the server screen is not available" if why == "no screen"
                                                   else "the game window closed (it will be reopened)"))
                    TASK_RESULT[name] = {"at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                         "ok": False, "result": why}
                    raise
                kb_guard.error(f"{name}: {e!r}")
                if brain:
                    try:
                        brain.record("error", repr(e), task=name)
                    except Exception:
                        pass
                TASK_RESULT[name] = {"at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "ok": False,
                                     "result": repr(e)[:120]}
                raise
            finally:
                if brain:
                    try:
                        brain.task_end()
                    except Exception:
                        pass
                TASK_NOW[0] = 0.0        # v154: the task ended, the task watchdog is disarmed
                kb_guard.routine(None)
                try:
                    import control as _c
                    _c.CITY["task_results"] = dict(TASK_RESULT)
                except Exception:
                    pass
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


QM_REPLACED = {"train", "train_troops", "heal", "build_upgrade", "research", "alliance_tech", "materials", "scout",
               "read_queues"}


def queue_tasks(tasks):
    """v197: the old separate tasks (train, heal, build_upgrade, research, alliance_tech, materials, scout) are one
    task now: queue_manager, driven by the game's Queue Overview. Settings made before keep working: when the
    dashboard has not sent a queue_manager task yet, it is built from the old ones (on/off and their options)."""
    if any(t.get("routine") == "queue_manager" for t in tasks):
        return tasks
    old = {t.get("routine"): t for t in tasks}
    def on(name, default=False):
        t = old.get(name)
        return bool(t.get("enabled", True)) if t else default
    tr = old.get("train") or old.get("train_troops") or {}
    qm = {"routine": "queue_manager", "enabled": True,
          "train": on("train") or on("train_troops"), "heal": on("heal"), "build": on("build_upgrade"),
          "research": on("research"), "donate": on("alliance_tech", True), "materials": on("materials"),
          "scout": on("scout"), "donate_min": 10,
          "inf_tier": tr.get("inf_tier", "4"), "arch_tier": tr.get("arch_tier", "4"),
          "cav_tier": tr.get("cav_tier", "4"), "siege_tier": tr.get("siege_tier", "4"),
          "fast": tr.get("fast", False), "use_bag": tr.get("use_bag", False),
          "heal_speedups": (old.get("heal") or {}).get("speedups", False),
          "build_mode": (old.get("build_upgrade") or {}).get("mode", "smart"),
          "build_speedups": (old.get("build_upgrade") or {}).get("speedups", False),
          "focus": (old.get("research") or {}).get("focus", "balanced"),
          "research_speedups": (old.get("research") or {}).get("speedups", False),
          "mat_kinds": (old.get("materials") or {}).get("kinds", ["leather", "ore", "ebony", "bone"])}
    out = [t for t in tasks if t.get("routine") not in QM_REPLACED]
    i = next((k + 1 for k, t in enumerate(out) if t.get("routine") == "collect_city"), 0)
    out.insert(i, qm)
    return out


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


# ---------------- TASK-08: smart interval scheduling (human-like sessions and breaks, daily hour cap) ----------------
import control
SS_FILE = os.path.join(BASE, "smart_schedule_state.json")


def _ss_cfg(settings):
    c = (settings or {}).get("smart_schedule") or {}
    def num(k, d, lo, hi):
        try:
            return max(lo, min(hi, float(c.get(k, d))))
        except Exception:
            return d
    return {"enabled": bool(c.get("enabled")), "limit_h": num("daily_active_hours_limit", 14, 1, 24),
            "work_min": num("work_session_minutes", 90, 10, 600), "break_min": num("break_duration_minutes", 20, 1, 240),
            "jitter": num("jitter_percent", 15, 0, 50) / 100.0}


def _ss_state():
    st = load_json(SS_FILE, {}) or {}
    day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    if st.get("day") != day:                          # a new game day (00:00 UTC): counters start again
        st = {"day": day, "active_sec": 0.0, "session_start": None, "session_len": 0, "break_until": 0}
    return st


def _ss_publish(cfg, st, state):
    try:
        control.CITY["smart_schedule"] = {"enabled": cfg["enabled"], "state": state, "active_h": round(st.get("active_sec", 0) / 3600, 2),
                                          "limit_h": cfg["limit_h"], "break_until": st.get("break_until") or 0, "day": st.get("day"),
                                          "at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"}
    except Exception:
        pass


def smart_schedule_gate(settings):
    """TASK-08: (state, seconds to rest) - state 'active' (go on), 'break' or 'done' (daily cap reached)."""
    cfg = _ss_cfg(settings)
    WAIT_JITTER[0] = cfg["jitter"] if cfg["enabled"] else 0.0
    CLICK_JITTER_PX[0] = 0                                  # TASK-19: exact clicks (owner's choice), no pixel jitter
    if not cfg["enabled"]:
        control.CITY.pop("smart_schedule", None)
        return "active", 0
    st, now = _ss_state(), time.time()
    if st.get("active_sec", 0) >= cfg["limit_h"] * 3600:
        save_json(SS_FILE, st); _ss_publish(cfg, st, "done")
        return "done", 300
    if now < (st.get("break_until") or 0):
        _ss_publish(cfg, st, "break")
        return "break", min(120, st["break_until"] - now)
    if not st.get("session_start"):
        j = cfg["jitter"]
        st["session_start"] = now
        st["session_len"] = cfg["work_min"] * 60 * (1 + random.uniform(-j, j))
        st["break_until"] = 0
        log(f"Smart schedule: new work session of about {st['session_len'] / 60:.0f} min "
            f"({st.get('active_sec', 0) / 3600:.1f} / {cfg['limit_h']:g} h today).")
    elif now - st["session_start"] >= st.get("session_len", cfg["work_min"] * 60):
        j = cfg["jitter"]
        rest = cfg["break_min"] * 60 * (1 + random.uniform(-j, j))
        st["session_start"], st["break_until"] = None, now + rest
        log(f"Smart schedule: taking a break of about {rest / 60:.0f} min.")
        save_json(SS_FILE, st); _ss_publish(cfg, st, "break")
        return "break", min(120, rest)
    save_json(SS_FILE, st); _ss_publish(cfg, st, "active")
    return "active", 0


def smart_schedule_add(settings, seconds):
    """TASK-08: add the time of one round to today's active runtime."""
    if seconds > 0:
        try:
            smart.stat("active_min", round(seconds / 60.0, 1))      # EARN-03: farming efficiency per active hour
        except Exception:
            pass
    cfg = _ss_cfg(settings)
    if not cfg["enabled"] or seconds <= 0:
        return
    st = _ss_state()
    st["active_sec"] = st.get("active_sec", 0) + seconds
    if st["active_sec"] >= cfg["limit_h"] * 3600:
        log(f"Smart schedule: {cfg['limit_h']:g} active hours reached today - resting until the game reset (00:00 UTC).")
    save_json(SS_FILE, st); _ss_publish(cfg, st, "done" if st["active_sec"] >= cfg["limit_h"] * 3600 else "active")


def main():
    _single_instance()
    log(f"Kingbot v{local_version()} starting.")
    try:
        smart.stat("restarts")                                 # TASK-16: restarts per day
    except Exception:
        pass
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
            try:                                                       # GUIDE-18: run ranges (UTC), offset, <15 min rule
                rg_run, rg_wait, rg_prof, rg_why = automation.sched_gate(settings)
            except Exception as e:
                rg_run, rg_wait, rg_prof, rg_why = True, 0, "", ""
                log(f"! smart scheduler ranges failed: {e!r}")
            if not rg_run and not RUN_NOW[0]:
                if time.time() - PAUSE_LOGGED[0] > 1800:
                    log(f"Smart scheduler: {rg_why}.")
                    PAUSE_LOGGED[0] = time.time()
                idle(rg_wait, state="sleeping", task="smart scheduler: " + rg_why)
                continue
            if rg_prof:
                settings = automation.apply_range_profile(settings, rg_prof)
            ss_state, ss_wait = smart_schedule_gate(settings)          # TASK-08
            if ss_state != "active" and not RUN_NOW[0]:
                idle(ss_wait, state="sleeping", task="smart schedule: " + ("on a break" if ss_state == "break" else "daily hours used up"))
                continue
            try:
                settings = rotation_settings(settings)
            except (Stop, NewSettings, SystemExit, pyautogui.FailSafeException):
                raise
            except Exception as e:
                import traceback
                log(f"! character rotation failed: {e!r}")
                log(traceback.format_exc()[-600:])
            try:
                settings = schedule_profile(settings)                 # GUIDE-17: profile for a time window
            except Exception as e:
                log(f"! scheduled profile failed: {e!r}")
            try:                                                       # TASK-15: if-this-then-that rules
                settings, rule_skip = automation.apply_rules(settings)
            except Exception as e:
                rule_skip = False
                log(f"! automation rules failed: {e!r}")
            try:
                automation.publish_daily_stats()                       # TASK-16
            except Exception:
                pass
            if rule_skip and not RUN_NOW[0]:
                log("A rule says: skip this round.")
                idle(min(900, int(settings.get("loop_minutes", 60)) * 60), state="sleeping", task="rule: skip this round")
                continue
            if EFF[0]:
                source += f", character {load_json(ROT_FILE, {}).get('name')}"
            if SCHED_PROF[0]:
                source += f", scheduled profile '{SCHED_PROF[0]}'"
            if signout_due():                                 # v258: the owner's scheduled sign-out
                g_ = get_game()
                if g_:
                    res = smart.sign_out(g_, sleep, "schedule")
                    kb_guard.command("action", "sched-" + time.strftime("%Y%m%d"), "sign_out", "done" if res == "done" else "failed", res)
            if game_login.find_login_window(0):             # v262 LOGIN-01: never signed in - ask the dashboard
                login_wait()
                continue
            if smart.signed_out():
                signed_out_wait()
                continue
            if smart.conduct_stopped():                      # URGENT-02: Conduct at or below the safety limit
                conduct_stop_wait()
                continue
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
            t_round = time.time()
            try:
                try:
                    one_round(settings)
                finally:
                    try:
                        smart_schedule_add(settings, time.time() - t_round)   # TASK-08
                    except Exception:
                        pass
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
                    SESSION_WATCH[0] = 0.0
                    if kb_guard.HEALTH.get("session") != "disconnected":    # v304: minimised RDP window
                        kb_guard.force_console(log, after_ok=_after_console)
                    if session_watch() and keep_screen_alive_ok():
                        log("  keep-screen: the screen is on again - continuing in 20 seconds")
                        idle(20, state="working")
                    else:
                        log("  Kingbot cannot see or click the game now. Waiting 5 minutes ...")
                        idle(300, state="no_screen")
                else:
                    import traceback
                    kb_guard.error(f"round: {e!r}")
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
