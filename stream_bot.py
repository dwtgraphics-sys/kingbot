# -*- coding: utf-8 -*-
"""
Kingbot live stream helper (runs next to bot.py, started by it).

It follows the dashboard switches the main bot already reads from GitHub:
  running = true, not frozen, stream.enabled != false, and (on_demand off or someone watching:
  stream.watch_until in the future) -> OBS + the Chrome sender run
  paused / frozen / stream switched off / bot dead     -> both are stopped
It makes NO GitHub calls of its own: the main bot writes live_state.json (what the dashboard wants,
the current task) and copies stream_status.json (written here) into outbox/status.json -> "stream".

Video path: OBS (Window Capture of the game, virtual camera) -> minimized Chrome on VDO.Ninja (push)
            -> the dashboard plays the VDO.Ninja viewer in its Live section.
"""
import os, sys, json, time, subprocess, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
LIVE_FILE = os.path.join(BASE, "live_state.json")        # written by control.py (main bot)
OUT_FILE = os.path.join(BASE, "stream_status.json")      # read by control.py -> status.json "stream"
PID_FILE = os.path.join(BASE, "stream_bot.pid")
LOG_FILE = os.path.join(BASE, "log.txt")

OBS_EXE = r"C:\Users\Administrator\obs-studio\bin\64bit\obs64.exe"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PROFILE = os.path.join(BASE, "stream_chrome")
try:                                                    # v196: from local_config.json when set (not on GitHub)
    import server_config as _sc
    STREAM_ID = _sc.get("STREAM_ID") or "kbb294c813b7"
    STREAM_PW = _sc.get("STREAM_PASSWORD") or "ct1q-ZeP"
except Exception:
    STREAM_ID, STREAM_PW = "kbb294c813b7", "ct1q-ZeP"
VIEW_URL = f"https://vdo.ninja/?view={STREAM_ID}&password={STREAM_PW}&label=Kingbot"
PUSH_URL = (f"https://vdo.ninja/?push={STREAM_ID}&webcam&videodevice=OBS&audiodevice=0&autostart"
            f"&password={STREAM_PW}&quality=1&label=Kingbot")

TICK = 5            # seconds between checks of live_state.json
HEALTH = 60         # seconds between process health checks while streaming
STALE = 300         # bot silent this long -> treat it as stopped
NOWIN = 0x08000000  # CREATE_NO_WINDOW
DETACH = 0x00000008


def log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]   stream: {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load(path, default):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def pid_alive(pid):
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=15, creationflags=NOWIN).stdout
        return str(int(pid)) in out
    except Exception:
        return False


def ps(cmd, timeout=40):
    """stdout, or None when PowerShell failed / timed out (unknown - not "nothing found")."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           capture_output=True, text=True, timeout=timeout, creationflags=NOWIN)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def obs_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=15, creationflags=NOWIN).stdout
        return "obs64.exe" in out.lower()
    except Exception:
        return True


def sender_pids():
    """Chrome processes that use OUR profile folder (the user's own Chrome is never touched)."""
    out = ps("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
             "Where-Object { $_.CommandLine -like '*stream_chrome*' } | ForEach-Object { $_.ProcessId }")
    if out is None:
        return None                      # could not check - never treat as "not running"
    return [int(x) for x in out.split() if x.strip().isdigit()]


SENDER = {"proc": None, "at": 0.0}


def sender_running():
    p = SENDER["proc"]
    if p is not None and p.poll() is None:
        return True
    pids = sender_pids()
    if pids is None:                     # unknown: assume running if we started one in the last 10 minutes
        return time.time() - SENDER["at"] < 600
    return bool(pids)


VCAM_CLSID = "{A3FCE0F5-3493-419F-958A-ABA1250EC20B}"     # OBS Virtual Camera (DirectShow)


def ensure_vcam():
    """v301: the sender asks Chrome for the camera named 'OBS'. A portable OBS on a new server never registered its
    virtual camera, so the viewer only spun. Register it (regsvr32) when its class is missing."""
    try:
        r = subprocess.run(["reg", "query", rf"HKLM\SOFTWARE\Classes\CLSID\{VCAM_CLSID}"], capture_output=True,
                           timeout=15, creationflags=NOWIN)
        if r.returncode == 0:
            return True
        root = os.path.dirname(os.path.dirname(os.path.dirname(OBS_EXE)))           # ...\obs-studio
        dlls = []
        for d, _, files in os.walk(os.path.join(root, "data", "obs-plugins")):
            dlls += [os.path.join(d, f) for f in files if f.lower().startswith("obs-virtualcam-module") and f.lower().endswith(".dll")]
        if not dlls:
            log("! OBS virtual camera module not found - the stream has no picture")
            return False
        for dll in dlls:
            subprocess.run(["regsvr32", "/s", dll], timeout=60, creationflags=NOWIN)
        ok = subprocess.run(["reg", "query", rf"HKLM\SOFTWARE\Classes\CLSID\{VCAM_CLSID}"], capture_output=True,
                            timeout=15, creationflags=NOWIN).returncode == 0
        log("OBS virtual camera registered" if ok else "! OBS virtual camera could not be registered")
        return ok
    except Exception as e:
        log(f"! virtual camera check failed: {e!r}")
        return False


def start_obs():
    if not os.path.exists(OBS_EXE):
        log("! OBS is not installed at " + OBS_EXE)
        return False
    ensure_vcam()
    subprocess.Popen([OBS_EXE, "--startvirtualcam", "--minimize-to-tray", "--disable-shutdown-check"],
                     cwd=os.path.dirname(OBS_EXE), creationflags=DETACH)
    log("OBS started with the virtual camera")
    time.sleep(12)
    return True


def start_sender():
    if not os.path.exists(CHROME_EXE):
        log("! Chrome is not installed at " + CHROME_EXE)
        return False
    SENDER["at"] = time.time()
    SENDER["proc"] = subprocess.Popen([CHROME_EXE, f"--user-data-dir={CHROME_PROFILE}", "--use-fake-ui-for-media-stream",
                      "--autoplay-policy=no-user-gesture-required", "--disable-background-timer-throttling",
                      "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
                      "--no-first-run", "--no-default-browser-check", "--start-minimized", "--new-window", PUSH_URL],
                     creationflags=DETACH)
    log("Chrome sender started (minimized)")
    time.sleep(6)
    return True


def _run(args, timeout=45):
    try:
        subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NOWIN)
    except Exception as e:
        log(f"! {args[0]} {args[-1]}: {e.__class__.__name__}")


def stop_all(reason):
    pids = sender_pids() or []
    if SENDER["proc"] is not None and SENDER["proc"].poll() is None:
        pids.append(SENDER["proc"].pid)
    SENDER["proc"] = None
    for p in set(pids):
        _run(["taskkill", "/PID", str(p), "/T", "/F"])
    had_obs = obs_running()
    if had_obs:   # graceful first (no "unclean shutdown" next time), then force
        _run(["taskkill", "/IM", "obs64.exe"])
        for _ in range(10):
            time.sleep(1)
            if not obs_running():
                break
        else:
            _run(["taskkill", "/IM", "obs64.exe", "/F"])
    if pids or had_obs:
        log(f"stopped ({reason})")


def wanted(live):
    """(on?, reason) from what the dashboard asks for."""
    if not live:
        return False, "no data from the bot yet"
    try:
        age = time.time() - float(live.get("ts", 0))
    except Exception:
        age = 1e9
    if age > STALE:
        return False, "the bot is not running"
    if (live.get("stream") or {}).get("enabled") is False:
        return False, "switched off in the dashboard"
    if not live.get("running", True):
        return False, "the bot is paused"
    st = live.get("stream") or {}
    if st.get("on_demand") is not False:                 # v247: stream only while someone watches the dashboard
        try:
            wu = float(st.get("watch_until") or 0)
        except Exception:
            wu = 0
        if wu < time.time():
            return False, "no one is watching"
    fz = live.get("freeze_until")
    if fz:
        try:
            if datetime.datetime.fromisoformat(str(fz).replace("Z", "+00:00")).timestamp() > time.time():
                return False, "the bot is frozen"
        except Exception:
            pass
    return True, "the bot is working"


def main():
    old = load(PID_FILE, None)
    if old and int(old) != os.getpid() and pid_alive(old):
        return                                    # one copy only
    save(PID_FILE, os.getpid())
    log(f"stream_bot started (pid {os.getpid()})")
    old_senders = sender_pids()
    if old_senders:                              # left by an older stream_bot: start clean
        for p in old_senders:
            _run(["taskkill", "/PID", str(p), "/T", "/F"])
        log(f"closed {len(old_senders)} old Chrome sender process(es)")
    active, since, last_health, last_out = None, None, 0.0, None
    while True:
        live = load(LIVE_FILE, {})
        on, reason = wanted(live)
        now = time.time()
        try:
            if on and (active is not True or now - last_health > HEALTH):
                last_health = now
                if not obs_running():
                    start_obs()
                if not sender_running():
                    start_sender()
                if active is not True:
                    since = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
                    log("live stream ON (" + reason + ")")
                active = True
            elif not on and active is not False:
                stop_all(reason)
                active, since = False, datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        except Exception as e:
            log(f"! {e!r}")
        out = {"active": bool(active), "reason": reason, "since": since, "view_url": VIEW_URL,
               "task": live.get("task"), "state": live.get("state")}
        if out != last_out:                       # the file only changes when something changed
            out["updated"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            try:
                save(OUT_FILE, out)
            except Exception:
                pass
            last_out = {k: v for k, v in out.items() if k != "updated"}
        time.sleep(TICK)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
