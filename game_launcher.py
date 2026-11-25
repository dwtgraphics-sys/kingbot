# -*- coding: utf-8 -*-
"""
Opens Rise of Kingdoms when it is not running.

Finds the game's shortcut in the Start menu / desktop (or uses the path in game_path.txt),
starts it, and waits for the game window. Tries at most once every 20 minutes.
"""
import os, glob, time, subprocess
from common import BASE, log, find_window

GAME_PATH_FILE = os.path.join(BASE, "game_path.txt")
LAST_TRY_FILE = os.path.join(BASE, "launch_last_try.txt")


def _last_try():
    try:
        return float(open(LAST_TRY_FILE).read().strip())
    except Exception:
        return 0.0


def _set_last_try(t):
    try:
        open(LAST_TRY_FILE, "w").write(str(t))
    except Exception:
        pass


def _is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False
KEYWORDS = ("rise of kingdoms", "riseofkingdoms", "rok")


def find_game_shortcut():
    try:
        p = open(GAME_PATH_FILE, encoding="utf-8-sig").read().strip().strip('"')
        if p and os.path.exists(p):
            return p
    except Exception:
        pass
    roots = [
        os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        r"C:\Users\Public\Desktop",
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
    ]
    found = []
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "*.lnk"), recursive=True):
            name = os.path.basename(path).lower()
            if any(k in name for k in KEYWORDS) and "uninstall" not in name:
                found.append(path)
    # prefer a shortcut whose name is exactly the game, not a launcher/updater helper
    found.sort(key=lambda p: (("launcher" in p.lower()), len(os.path.basename(p))))
    return found[0] if found else None


def _exe_of(hwnd):
    import ctypes
    from ctypes import wintypes
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)   # QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(520)
    n = wintypes.DWORD(520)
    ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    ctypes.windll.kernel32.CloseHandle(h)
    return buf.value.lower()


def list_windows():
    """(hwnd, title, class, exe, rect) of visible top-level windows."""
    import ctypes
    from ctypes import wintypes
    from common import window_class
    user32 = ctypes.windll.user32
    out = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 50 and r.bottom - r.top > 50:
                out.append((hwnd, buf.value, window_class(hwnd), _exe_of(hwnd),
                            (r.left, r.top, r.right, r.bottom)))
        return True
    user32.EnumWindows(EnumProc(cb), 0)
    return out


def find_launcher():
    """The RoK launcher window (process launcher.exe in the Rise of Kingdoms folder)."""
    best = None
    for hwnd, title, cls, exe, r in list_windows():
        if exe.endswith("\\launcher.exe") and "rise of kingdoms" in exe:
            area = (r[2] - r[0]) * (r[3] - r[1])
            if best is None or area > best[0]:
                best = (area, hwnd)
    return best[1] if best else None


def click_to_start(sleep, game=None, tries=3):
    """v171: continue past the game's start screen.

    Clicks the 'Click to Start' banner band, then the middle of the screen, then checks whether
    the game left the title screen (the picture changes). Returns True when it seems to continue.
    """
    from common import Game, find_window
    g = game
    if g is None:
        hwnd = find_window()
        if not hwnd:
            return False
        g = Game()
    try:
        before = g.screenshot()
    except Exception:
        return False
    for attempt in range(tries):
        try:
            if g.find_image("click_to_start", 0.75):
                g.click_rel(0.5, 0.885)          # the banner itself
            else:
                g.click_rel(0.5, 0.885)          # banner band, by position
                sleep(2)
                g.click_rel(0.5, 0.5)            # middle of the screen (the user's suggestion)
        except Exception:
            pass
        sleep(6)
        try:
            after = g.screenshot()
            if float(abs(after.astype(int) - before.astype(int)).mean()) > 3:
                log("  start screen: continued")
                return True
        except Exception:
            pass
        before = after if 'after' in dir() else before
    log("  start screen: the picture did not change")
    return False


def press_launcher_start():
    """Click the yellow START button of the launcher. Returns True if the launcher was found."""
    import ctypes
    from ctypes import wintypes
    from common import activate, Game
    hwnd = find_launcher()
    if not hwnd:
        return False
    activate(hwnd)
    r = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    g = Game.__new__(Game)
    g.hwnd, g.x, g.y, g.w, g.h = hwnd, r.left, r.top, r.right - r.left, r.bottom - r.top
    ok = g._click_absolute(0.905, 0.835)
    log(f"Launcher START pressed: {ok}")
    return True


def ensure_game_running(sleep):
    """Return True if the game window exists (starting the game if needed)."""
    if find_window():
        return True
    # v150: the game closes on its own now and then; waiting 20 minutes left the bot doing
    # nothing at all. Retry after 90 s, but still never more often than that.
    if time.time() - _last_try() < 90:
        return False
    _set_last_try(time.time())     # saved to a file, so a restart does not try again right away
    path = find_game_shortcut()
    if not path:
        log("! Game is closed and no game shortcut was found. "
            "Put the full path of the game's shortcut or .exe in game_path.txt")
        return False
    log(f"Game is closed. Starting it: {os.path.basename(path)}")
    try:
        # start it from a separate process so a stuck prompt can never freeze Kingbot
        # RunAsInvoker: start the game WITHOUT administrator rights, so Windows lets
        # Kingbot (and Claude) click in it even when they are not administrator.
        env = dict(os.environ, __COMPAT_LAYER="RunAsInvoker")
        subprocess.Popen(["cmd", "/c", "start", "", path], close_fds=True, env=env,
                         cwd=os.path.dirname(path) or None,
                         creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    except Exception as e:
        log(f"! Could not start the game: {e}")
        return False
    for i in range(36):                     # up to 3 minutes for the window to appear
        sleep(5)
        if i in (4, 12, 20) and not find_window():
            press_launcher_start()          # launcher open but game not started: press START
        if find_window():
            log("Game window opened. Waiting for the game to load ...")
            sleep(20)
            click_to_start(sleep)           # v171: banner band, then the middle of the screen
            sleep(55)                       # loading screens
            return True
    if not _is_admin():
        log("! The game did not open within 3 minutes. It probably asked for administrator approval. "
            "Start Kingbot as administrator (right-click 3_start_bot.bat > Run as administrator).")
    else:
        log("! The game did not open within 3 minutes (a launcher may need a click).")
    return False
