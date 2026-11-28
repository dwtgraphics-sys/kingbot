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
def _own_stream_id(sc):
    """v333: every server pushed to the same default VDO.Ninja ID 'kbb294c813b7' unless local_config.json named
    its own. Two servers live at once -> the second gets 'The stream ID you are publishing to is already in
    use ... You will now be disconnected' (vps-01-main 28 Nov, that Chrome box covered the screen).
    The original server keeps the old ID; every other server gets its own fixed ID made from its name.
    The dashboard reads view_url from the status, so it follows automatically."""
    import hashlib
    sid = sc.server_id()
    if sid == sc.DEFAULT_ID:
        return "kbb294c813b7"
    return "kb" + hashlib.sha1(("kingbot-stream:" + sid).encode()).hexdigest()[:10]


try:                                                    # v196: from local_config.json when set (not on GitHub)
    import server_config as _sc
    STREAM_ID = _sc.get("STREAM_ID") or _own_stream_id(_sc)
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


OBS_FIX = {"at": 0.0}


def obs_health():
    """v342: restart OBS when its newest log shows it stuck or on the wrong scenes:
    - stuck on the 'unclean shutdown - Safe Mode?' question (the log stops after that line for > 90 s);
    - it opened the empty 'Untitled' collection (log: "Loaded scenes: - scene 'Scene'") - the stream was black."""
    try:
        if time.time() - OBS_FIX["at"] < 600 or not obs_running():
            return
        logs = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(OBS_EXE))), "config", "obs-studio", "logs")
        files = sorted((os.path.join(logs, f) for f in os.listdir(logs) if f.endswith(".txt")), key=os.path.getmtime)
        if not files:
            return
        f = files[-1]
        txt = open(f, encoding="utf-8", errors="replace").read()
        age = time.time() - os.path.getmtime(f)
        why = None
        if "unclean shutdown" in txt and "Startup complete" not in txt and age > 90:
            why = "stuck on its 'Safe Mode?' question"
        elif "Loaded scenes:" in txt and "scene 'Kingbot'" not in txt:
            why = "opened the empty scene collection (black picture)"
        if why:
            OBS_FIX["at"] = time.time()
            _run(["taskkill", "/IM", "obs64.exe", "/F"])
            time.sleep(3)
            log(f"OBS {why} - restarting it with the Kingbot scene")
            if start_obs():
                for p in (sender_pids() or []):          # the sender must pick up the new camera
                    _run(["taskkill", "/PID", str(p), "/T", "/F"])
                SENDER["proc"] = None
    except Exception as e:
        log(f"! obs_health: {e!r}")


def close_obs_error_windows():
    """v308: every OBS start without the C++ runtime left an 'obs64.exe - System Error' box on top of the game;
    the bot then could not see the search panels. Close such boxes (title starts with 'obs64.exe')."""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        found = []
        Enum = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def cb(h, _):
            n = u.GetWindowTextLengthW(h)
            if n and u.IsWindowVisible(h):
                b = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(h, b, n + 1)
                t = b.value.lower()
                if t.startswith("obs64.exe") and ("error" in t or "system" in t):
                    found.append(h)
            return True

        u.EnumWindows(Enum(cb), 0)
        for h in found:
            u.PostMessageW(h, 0x0010, 0, 0)                 # WM_CLOSE
        if found:
            # v319: a system error box ignores WM_CLOSE from a normal program; it closes when obs64.exe ends.
            _run(["taskkill", "/IM", "obs64.exe", "/F"])
            log(f"closed {len(found)} OBS error window(s) that covered the game")
    except Exception:
        pass


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


def no_error_boxes():
    """v319: Windows shows 'obs64.exe - System Error / MSVCP140_1.dll was not found' as a system box that a
    normal program cannot close (WM_CLOSE from v308 is refused), and it sat on top of the game. With
    SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX the loader fails quietly instead;
    OBS (started from here) inherits this mode, so the box can never appear again."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    except Exception:
        pass


def _system_dir():
    """v319: the real 64-bit System32. A 32-bit Python sees SysWOW64 under the name System32, where a 32-bit
    msvcp140_1.dll made the v302 check pass although the 64-bit runtime that obs64.exe needs was missing."""
    win = os.environ.get("WINDIR", r"C:\Windows")
    native = os.path.join(win, "Sysnative")
    return native if os.path.isdir(native) else os.path.join(win, "System32")


def vc_runtime_ok():
    d = _system_dir()
    if all(os.path.exists(os.path.join(d, f)) for f in ("msvcp140.dll", "msvcp140_1.dll", "vcruntime140_1.dll")):
        return True
    obs_bin = os.path.dirname(OBS_EXE)                   # an OBS zip that carries its own copy also works
    return os.path.exists(os.path.join(obs_bin, "msvcp140_1.dll"))


VC_TRY = [0.0]


def install_vc_runtime():
    """v319: install the Microsoft Visual C++ 2015-2022 x64 runtime silently (same download as install_obs.ps1),
    at most once every 6 hours. Returns True when the runtime is there afterwards."""
    if time.time() - VC_TRY[0] < 6 * 3600:
        return False
    VC_TRY[0] = time.time()
    log("Visual C++ runtime (MSVCP140_1.dll) missing - installing it from Microsoft (silent) ...")
    exe = os.path.join(os.environ.get("TEMP", BASE), "vc_redist.x64.exe")
    cmd = ("$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; "
           f"Invoke-WebRequest 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '{exe}' -UseBasicParsing; "
           f"$p = Start-Process '{exe}' -ArgumentList '/install','/quiet','/norestart' -PassThru -Wait; $p.ExitCode")
    out = ps(cmd, timeout=900)
    ok = vc_runtime_ok()
    log("Visual C++ runtime installed" if ok else f"! Visual C++ runtime install failed (exit {str(out).strip()[:40]})"
        " - run the install_obs action from the dashboard")
    return ok


OBS_FAIL = {"n": 0, "until": 0.0}


def pin_obs_collection():
    """v339: newer OBS keeps the chosen profile / scene collection in user.ini, not global.ini - it opened the empty
    'Untitled' collection ('Scene' with no source), so the virtual camera and the dashboard stream were black.
    Point user.ini at the Kingbot profile + collection (the window capture of the game)."""
    try:
        cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(OBS_EXE))), "config", "obs-studio")
        sent = os.path.join(cfg, ".sentinel")             # v341: OBS 30+ marks a run here; after the bot closes OBS
        if os.path.isdir(sent):                           # it asked "Safe Mode?" and sat 3 min on that dialog
            for f in os.listdir(sent):                    # (on top of the game) - --disable-shutdown-check is ignored
                try:
                    os.remove(os.path.join(sent, f))
                except Exception:
                    pass
        if not os.path.exists(os.path.join(cfg, "basic", "scenes", "Kingbot.json")):
            return
        path = os.path.join(cfg, "user.ini")
        want = {"Profile": "Kingbot", "ProfileDir": "Kingbot", "SceneCollection": "Kingbot",
                "SceneCollectionFile": "Kingbot.json"}
        lines = open(path, encoding="utf-8-sig").read().splitlines() if os.path.exists(path) else []
        out, sec, done, inb = [], None, set(), False
        for ln in lines:
            st = ln.strip()
            if st.startswith("[") and st.endswith("]"):
                if inb:
                    out += [f"{k}={v}" for k, v in want.items() if k not in done]
                sec = st[1:-1]; inb = sec == "Basic"
                out.append(ln); continue
            k = st.split("=", 1)[0] if "=" in st else None
            if inb and k in want:
                out.append(f"{k}={want[k]}"); done.add(k); continue
            out.append(ln)
        if inb:
            out += [f"{k}={v}" for k, v in want.items() if k not in done]
        if not any(l.strip() == "[Basic]" for l in out):
            out += ["", "[Basic]"] + [f"{k}={v}" for k, v in want.items()]
        new = "\n".join(out) + "\n"
        if new != "\n".join(lines) + "\n":
            open(path, "w", encoding="utf-8").write(new)
            log("  stream: OBS set to the Kingbot scene collection (user.ini)")
    except Exception as e:
        log(f"  stream: could not set the OBS scene collection: {e!r}")


def start_obs():
    if not os.path.exists(OBS_EXE):
        log("! OBS is not installed at " + OBS_EXE)
        return False
    if time.time() < OBS_FAIL["until"]:
        return False                             # v319: OBS failed to start - wait instead of retrying every minute
    if not vc_runtime_ok() and not install_vc_runtime():
        if OBS_FAIL["n"] == 0:
            log("! OBS cannot start: the Visual C++ runtime (MSVCP140_1.dll) is missing - run the install_obs action")
        OBS_FAIL["n"] += 1
        OBS_FAIL["until"] = time.time() + 1800
        return False                             # v302: otherwise every start leaves a 'System Error' window
    ensure_vcam()
    pin_obs_collection()
    subprocess.Popen([OBS_EXE, "--startvirtualcam", "--minimize-to-tray", "--disable-shutdown-check",
                      "--profile", "Kingbot", "--collection", "Kingbot", "--scene", "Kingbot"],
                     cwd=os.path.dirname(OBS_EXE), creationflags=DETACH)
    time.sleep(12)
    if not obs_running():                        # v319: it closed at once (missing DLL, broken install)
        OBS_FAIL["n"] += 1
        OBS_FAIL["until"] = time.time() + min(3600, 300 * OBS_FAIL["n"])
        log(f"! OBS closed right after starting (try {OBS_FAIL['n']}) - next try in "
            f"{int((OBS_FAIL['until'] - time.time()) / 60)} minutes; run the install_obs action if it keeps failing")
        return False
    OBS_FAIL["n"], OBS_FAIL["until"] = 0, 0.0
    log("OBS started with the virtual camera")
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
    no_error_boxes()                             # v319: OBS inherits it - no 'System Error' box on the game
    old_senders = sender_pids()
    if old_senders:                              # left by an older stream_bot: start clean
        for p in old_senders:
            _run(["taskkill", "/PID", str(p), "/T", "/F"])
        log(f"closed {len(old_senders)} old Chrome sender process(es)")
    if os.path.exists(OBS_EXE):                  # v301: register the virtual camera now; a running OBS that
        had = subprocess.run(["reg", "query", rf"HKLM\SOFTWARE\Classes\CLSID\{VCAM_CLSID}"], capture_output=True,
                             timeout=15, creationflags=NOWIN).returncode == 0
        if not had and ensure_vcam() and obs_running():   # started without it must start again
            _run(["taskkill", "/IM", "obs64.exe", "/F"])
            log("OBS restarted so it can use the new virtual camera")
    active, since, last_health, last_out = None, None, 0.0, None
    while True:
        live = load(LIVE_FILE, {})
        on, reason = wanted(live)
        now = time.time()
        close_obs_error_windows()
        try:
            if on and (active is not True or now - last_health > HEALTH):
                last_health = now
                obs_new = False
                if not obs_running():
                    obs_new = bool(start_obs())
                if obs_new and sender_running():          # v305: a sender opened before the OBS camera existed
                    for p in (sender_pids() or []):       # waits on "Share your Camera" forever - start it again
                        _run(["taskkill", "/PID", str(p), "/T", "/F"])
                    SENDER["proc"] = None
                    log("Chrome sender restarted so it finds the new OBS camera")
                if not obs_new:
                    obs_health()
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
