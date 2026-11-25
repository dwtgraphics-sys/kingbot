# -*- coding: utf-8 -*-
"""Shared helpers: find the game window, screenshots, clicks, image search."""
import ctypes, json, os, time, datetime, random
from ctypes import wintypes

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

def _disable_quick_edit():
    try:
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-10)
        mode = ctypes.c_ulong()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, (mode.value & ~0x0040) | 0x0080)   # no QUICK_EDIT, keep EXTENDED_FLAGS
    except Exception:
        pass


_disable_quick_edit()

import numpy as np
import cv2
import pyautogui
from PIL import ImageGrab

pyautogui.FAILSAFE = True      # move mouse to a screen corner = emergency stop
pyautogui.PAUSE = 0.05
CLICK_JITTER_PX = [0]          # TASK-08: set by bot.py from smart_schedule (0 = exact clicks)

BASE = os.path.dirname(os.path.abspath(__file__))
ROUTINES_FILE = os.path.join(BASE, "routines.json")
TASKS_FILE = os.path.join(BASE, "tasks.json")
TEMPL_DIR = os.path.join(BASE, "templates")
BUILTIN_DIR = os.path.join(BASE, "builtin_templates")   # shipped with updates (smart activities)
LOG_FILE = os.path.join(BASE, "log.txt")
os.makedirs(TEMPL_DIR, exist_ok=True)

GAME_TITLE = "Rise of Kingdoms"

VK = {
    "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F12": 0x7B,
    "ESC": 0x1B,
}
# keys the recorder can capture after F9
KEY_NAMES = {0x20: "space", 0x1B: "esc", 0x0D: "enter", 0x09: "tab", 0x08: "backspace",
             0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down"}
for c in range(0x30, 0x3A):
    KEY_NAMES[c] = chr(c)
for c in range(0x41, 0x5B):
    KEY_NAMES[c] = chr(c).lower()


LOG_HOOKS = []   # functions called with each log message (e.g. Telegram notifications)
LAST_ACTIVITY = [time.time()]   # updated on every log line and wait; read by the watchdog


def log_raw(msg):
    """v170: write a line without touching the progress clock (used by the watchdog itself)."""
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    for hook in LOG_HOOKS:
        try:
            hook(msg)
        except Exception:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def log(msg):
    LAST_ACTIVITY[0] = time.time()
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    for hook in LOG_HOOKS:
        try:
            hook(msg)
        except Exception:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class _MI(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", _MI)]


def _mouse(flags, dx=0, dy=0):
    """Send one mouse event with SendInput (what real mice use)."""
    inp = _INPUT(0, _MI(dx, dy, 0, flags, 0, None))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


CLICK_MODE_FILE = os.path.join(BASE, "click_mode.txt")
_click_mode = None


def click_mode():
    """'absolute' (default), 'message' or 'cursor'; the bot switches and remembers when one has no effect."""
    global _click_mode
    if _click_mode is None:
        try:
            _click_mode = open(CLICK_MODE_FILE).read().strip() or ""
        except Exception:
            _click_mode = ""
        if not _click_mode or (_click_mode != "interception" and interception_lib() is not None
                               and not os.path.exists(CLICK_MODE_FILE + ".checked")):
            # first run with the driver installed: start with Interception
            _click_mode = "interception" if interception_lib() is not None else "absolute"
            try:
                open(CLICK_MODE_FILE + ".checked", "w").write("1")
            except Exception:
                pass
    return _click_mode


CLICK_MODES = ["interception", "absolute", "message", "cursor"]
_ic = [None, False]   # module, tried

# v154: consecutive clicks that missed. After 3 the click method is switched and remembered;
# after 15 the round is aborted instead of spinning on a pointer that cannot reach the game.
CLICK_FAILS = [0]
CLICK_STUCK_AFTER = 15


def _click_missed(mode):
    CLICK_FAILS[0] += 1
    n = CLICK_FAILS[0]
    if n == 3:
        # v183: 'message' proved to work when the pointer cannot reach the game (RDP), so it is
        # tried before the cursor mode.
        if mode == "absolute":
            log("! 3 clicks in a row missed the target - switching to 'message' clicks (remembered)")
            set_click_mode("message")
        elif mode == "message":
            log("! message clicks missed too - switching to 'cursor' clicks (remembered)")
            set_click_mode("cursor")
    if n >= CLICK_STUCK_AFTER:
        CLICK_FAILS[0] = 0
        raise RuntimeError(f"{CLICK_STUCK_AFTER} clicks in a row failed - the game is not taking the mouse")


def interception_lib():
    """The Interception driver library, ready to use, or None if the driver is not installed."""
    if not _ic[1]:
        _ic[1] = True
        try:
            import interception
            interception.auto_capture_devices(keyboard=True, mouse=True)
            _ic[0] = interception
            log("Interception driver ready (real mouse/keyboard input).")
        except Exception as e:
            log(f"Interception driver not available: {str(e)[:120]}")
    return _ic[0]


CURRENT_GAME = [None]


def close_gem_dialogs(g=None):
    """SAFETY: if a window asking to spend gems is open, press NO. Returns True if such a window was seen."""
    g = g or CURRENT_GAME[0]
    if g is None:
        return False
    seen = False
    for _ in range(3):
        try:
            img = g.screenshot()
        except Exception:
            return seen
        notice = g.find_image("notice_title", 0.8, img=img)
        if not notice and not (g.find_image("btn_confirm_word", 0.85, img=img) and g.find_image("btn_no", 0.8, img=img)):
            return seen
        no = g.find_image("btn_no", 0.8, img=img)
        if not no and not g.find_image("btn_confirm_word", 0.85, img=img):
            # v141: a NOTICE title with no NO / CONFIRM is the Notice Board (events news), not a gem window
            log("  ! the Notice Board was open - closing it")
            g._click_absolute(0.766, 0.268); time.sleep(2)
            return seen
        seen = True
        if not no:
            # v148: the NO template can miss on some dialogs (this happened 608 times), which used to
            # leave a 'spend gems' window open in front of every later click. Close it properly now.
            log("! SAFETY: a 'spend gems' window is open but the NO button was not found - closing it")
            closed_by = ""
            for tpl in ("btn_x", "btn_x2"):
                xb = g.find_image(tpl, 0.85, img=img)
                if xb:
                    g._click_absolute(*xb[0])
                    closed_by = tpl
                    break
            if not closed_by:
                pyautogui.press("esc")           # ESC cancels a dialog; press_key() would recurse here
                closed_by = "ESC"
            time.sleep(1.5)
            try:
                img3 = g.screenshot()
                still = bool(g.find_image("notice_title", 0.8, img=img3) and g.find_image("btn_confirm_word", 0.85, img=img3))
            except Exception:
                still = False
            if still:
                log("  ! the 'spend gems' window is STILL open after " + closed_by + " - no click may follow")
            else:
                log("  the 'spend gems' window was closed with " + closed_by + " (nothing was spent)")
            continue
        g._click_absolute(*no[0])
        log("! SAFETY: a 'spend gems' window was open - pressed NO (nothing was spent)")
        time.sleep(1.5)
    return seen


def screen_is_clear(g=None):
    """True when the plain city or map view is showing (no panel or dialog on top).

    v173: an open panel can cover the icons checked below (the governor profile covers them all),
    and then ESC was refused as "nothing is open". A visible close button means something is open.
    """
    g = g or CURRENT_GAME[0]
    if g is None:
        return True
    img = g.screenshot()
    if g.find_image("btn_x", 0.85, img=img) or g.find_image("btn_x2", 0.85, img=img):
        return False
    return any(g.find_image(n, t, img=img) for n, t in (("space_on_map", 0.75), ("space_on_city", 0.75),
                                                          ("city_build_icon", 0.8), ("map_search_icon", 0.8)))


def recover_screen(g=None, tries=4):
    """Bring the game back to the plain city/map view: press NO on gem windows, use the BACK arrow,
    else ESC once. Returns True when the screen is clear."""
    g = g or CURRENT_GAME[0]
    if g is None:
        return True
    for i in range(tries):
        close_gem_dialogs(g)
        img = g.screenshot()
        chat = g.find_image("chat_close", 0.85, img=img)
        if chat:
            log("  ! the chat panel was open - closing it")
            g._click_absolute(*chat[0]); time.sleep(2)
            continue
        if any(g.find_image(n, t, img=img) for n, t in (("space_on_map", 0.75), ("space_on_city", 0.75),
                                                          ("city_build_icon", 0.8), ("map_search_icon", 0.8))):
            if i:
                log("  screen recovered")
            return True
        cok = g.find_image("canyon_ok", 0.85, img=img)
        if cok:                                              # Sunset Canyon battle setup: leaving asks a question
            log("  ! Sunset Canyon battle setup was open - pressing OK (free attempt)")
            g._click_absolute(*cok[0]); time.sleep(10)
            g._click_absolute(0.5, 0.88); time.sleep(3)
            continue
        cf = g.find_image("btn_confirm_cmd", 0.8, img=img)
        if cf:
            log("  ! a reward card was open - pressing CONFIRM")
            g._click_absolute(*cf[0]); time.sleep(2.5)
            continue
        cts = g.find_image("click_to_start", 0.8, img=img)
        xb = g.find_image("btn_x", 0.85, img=img) or g.find_image("btn_x2", 0.85, img=img)
        back = g.find_image("btn_back", 0.8, img=img)
        if cts:
            log("  game start screen - pressing 'Click to Start'")
            g._click_absolute(*cts[0])
            time.sleep(25)
            continue
        if xb:
            log("  ! a window was left open - pressing X")
            g._click_absolute(*xb[0])
        elif back:
            log("  ! a window was left open - pressing BACK")
            g._click_absolute(*back[0])
        else:
            # v171: a click on the start banner (and then the middle) also continues the title screen
            if i == 0:
                try:
                    g.click_rel(0.5, 0.885); time.sleep(2)
                    g.click_rel(0.5, 0.5); time.sleep(4)
                except Exception:
                    pass
            # v148: neither X nor BACK matched. The icons checked above prove this is not the plain
            # view, so ESC closes a window here instead of asking to quit.
            if i == 0:
                log("  ! screen not recognised (no X / BACK found) - trying ESC once")
                pyautogui.press("esc")
                time.sleep(2)
                continue
            log("  ! screen not recognised (no X / BACK found) - leaving it as it is")
            return False
        time.sleep(2)
    return False


def press_key(key):
    """Press a key through Interception if available (games accept it), otherwise normally.
    SAFETY: never press a key while a 'spend gems' window is open; Space only on the plain city/map view."""
    if close_gem_dialogs():
        return
    if key in ("esc", "escape") and CURRENT_GAME[0] is not None and screen_is_clear():
        log("! SAFETY: nothing is open, ESC was not pressed (ESC would ask to quit the game)")
        return
    if key == "space" and CURRENT_GAME[0] is not None and not screen_is_clear():
        log("! SAFETY: a panel is open, Space was not pressed")
        return
    ic = interception_lib()
    if ic is not None:
        try:
            ic.press(key)
            return
        except Exception:
            pass
    pyautogui.press(key)


def set_click_mode(mode):
    global _click_mode
    _click_mode = mode
    try:
        open(CLICK_MODE_FILE, "w").write(mode)
    except Exception:
        pass
    log(f"Click method set to: {mode}")


def is_admin():
    """True when Kingbot runs as administrator (needed: the game runs elevated, and Windows
    blocks input from normal programs to elevated windows)."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def wait_key_release(vk):
    while key_down(vk):
        time.sleep(0.02)


# ---------------- window ----------------
def window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def find_window():
    """Return hwnd of the game window: a visible window whose title contains GAME_TITLE.
    Prefers the game itself (Unity window) over launchers; ignores File Explorer folders."""
    found = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if GAME_TITLE.lower() in buf.value.lower():
            cls = window_class(hwnd)
            if cls in ("CabinetWClass", "ExploreWClass", "ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"):
                return True
            if buf.value.startswith("RISE OF KINGDOMS") and cls != "UnityWndClass":
                return True      # the launcher, not the game
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            found.append((cls == "UnityWndClass", area, hwnd))
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    if not found:
        return None
    found.sort(reverse=True)
    return found[0][2]


def activate(hwnd):
    """v158: put the game window in front, even when another app (the dashboard, the DSH window)
    has the focus. AttachThreadInput + the ALT tap are what make SetForegroundWindow work from a
    background process; without them every click landed in the other window."""
    if user32.IsIconic(hwnd):
        user32.ShowWindowAsync(hwnd, 9)  # SW_RESTORE (async: never waits for a busy window)
        time.sleep(1.0)
    if user32.GetForegroundWindow() == hwnd:
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        fg = user32.GetForegroundWindow()
        tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        tid_me = kernel32.GetCurrentThreadId()
        if tid_fg:
            user32.AttachThreadInput(tid_me, tid_fg, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if tid_fg:
            user32.AttachThreadInput(tid_me, tid_fg, False)
    except Exception:
        pass
    user32.keybd_event(0x12, 0, 0, 0)   # ALT down/up releases the foreground lock
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)
    return user32.GetForegroundWindow() == hwnd


def client_rect(hwnd):
    """Screen x, y, width, height of the game's drawing area (no title bar)."""
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    p = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(p))
    return p.x, p.y, r.right, r.bottom


def game_frozen():
    """True when the client crashed: Unity keeps UnityCrashHandler64.exe up and the window shows
    one frozen frame while ignoring every click (that is what happened at 13:20 today)."""
    try:
        import subprocess
        out = subprocess.run(["tasklist", "/fi", "IMAGENAME eq UnityCrashHandler64.exe", "/fo", "csv", "/nh"],
                             capture_output=True, encoding="utf-8", errors="replace", timeout=15).stdout
        return "UnityCrashHandler64" in out
    except Exception:
        return False


def close_window(hwnd):
    """v156: ask a black/dead game window to close, then kill its process if it is still there."""
    try:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)      # WM_CLOSE
    except Exception:
        pass
    time.sleep(2)
    try:
        if user32.IsWindow(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            log(f"  the game window did not close - killing process {pid.value}")
            os.system(f"taskkill /f /pid {pid.value} >nul 2>&1")
            time.sleep(3)
    except Exception as e:
        log(f"  ! could not close the game window: {e!r}")


def keep_on_screen(hwnd):
    """Keep the game window fully on screen. If it is bigger than the screen
    (e.g. after the screen size changed), maximize it so the whole game is visible."""
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w > sw + 16 or h > sh + 16:
        user32.ShowWindowAsync(hwnd, 3)     # SW_MAXIMIZE (async)
        time.sleep(1.5)
    elif r.left < -8 or r.top < -8 or r.right > sw + 8 or r.bottom > sh + 8:
        user32.SetWindowPos(hwnd, 0, 0, 0, min(w, sw), min(h, sh), 0x4000 | 0x0004)  # ASYNC | NOZORDER
        time.sleep(1.0)


DESIGN_W, DESIGN_H = 946, 710          # v201: the window size every picture and position was made for
_SIZE_TRY = [0.0]


def ensure_game_size(hwnd):
    """v201: put the game window back to 946x710 (drawing area). Remote Desktop at another resolution left it at
    941x529, where the windows inside the game sit elsewhere and the pictures no longer match. At most one try
    every 10 minutes, and only when the screen is big enough."""
    try:
        x, y, w, h = client_rect(hwnd)
        if abs(w - DESIGN_W) <= 8:            # the game keeps its own 16:9 shape - only the WIDTH matters:
            return False                      # the game's windows are laid out by width (measured 25-11)
        if time.time() - _SIZE_TRY[0] < 600 or user32.IsIconic(hwnd):
            return False
        _SIZE_TRY[0] = time.time()
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        fw, fh = (r.right - r.left) - w, (r.bottom - r.top) - h       # frame + title bar
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        ww, wh = DESIGN_W + fw, int(round(DESIGN_W * h / max(1, w))) + fh
        if ww > sw or wh > sh:
            log(f"  game size: the window is {w}x{h}, the screen ({sw}x{sh}) is too small to change it")
            return False
        user32.ShowWindow(hwnd, 9)                                    # SW_RESTORE (not maximized)
        time.sleep(0.8)
        user32.SetWindowPos(hwnd, 0, max(0, (sw - ww) // 2), 0, ww, wh, 0x0004)   # NOZORDER
        time.sleep(2.0)
        x2, y2, w2, h2 = client_rect(hwnd)
        log(f"  game size: {w}x{h} -> {w2}x{h2} (the bot was made for a game {DESIGN_W} wide)")
        return True
    except Exception as e:
        log(f"  ! game size: {e!r}")
        return False


class Game:
    def __init__(self):
        self.hwnd = find_window()
        if not self.hwnd:
            raise SystemExit("Game window not found. Open Rise of Kingdoms first.")
        self.refresh()
        CURRENT_GAME[0] = self

    def refresh(self):
        if not user32.IsWindow(self.hwnd):
            self.hwnd = find_window()
            if not self.hwnd:
                raise RuntimeError("Game window closed")
        keep_on_screen(self.hwnd)
        ensure_game_size(self.hwnd)
        self.x, self.y, self.w, self.h = client_rect(self.hwnd)

    def focus(self):
        activate(self.hwnd)
        self.refresh()
        if user32.GetForegroundWindow() != self.hwnd:
            log("  ! game window is not in front; clicks may not reach it")

    def describe(self):
        return (f"screen {user32.GetSystemMetrics(0)}x{user32.GetSystemMetrics(1)}, "
                f"game area at {self.x},{self.y} size {self.w}x{self.h}")

    # relative (0..1) <-> screen pixels
    def to_screen(self, rx, ry):
        return int(self.x + rx * self.w), int(self.y + ry * self.h)

    def to_rel(self, sx, sy):
        return (sx - self.x) / self.w, (sy - self.y) / self.h

    def click_rel(self, rx, ry):
        """Click at a relative point of the game area, using the method that works on this PC."""
        if close_gem_dialogs(self):
            return False          # a 'spend gems' window was open: closed it, skip this click
        if user32.GetForegroundWindow() != self.hwnd:
            # v158: the user works in another window on this desktop; without this the click
            # would land in that window instead of the game.
            activate(self.hwnd)
            time.sleep(0.1)
        if CLICK_JITTER_PX[0] > 0 and self.w and self.h:      # TASK-08: human-like +/- px click jitter
            j = CLICK_JITTER_PX[0]
            rx = min(0.999, max(0.001, rx + random.uniform(-j, j) / self.w))
            ry = min(0.999, max(0.001, ry + random.uniform(-j, j) / self.h))
        mode = click_mode()
        if mode == "interception":
            r = self._click_interception(rx, ry)
        elif mode == "cursor":
            r = self._click_cursor(rx, ry)
        elif mode == "message":
            r = self._click_message(rx, ry)
        else:
            r = self._click_absolute(rx, ry)
        if r is False:
            _click_missed(mode)
            return False          # False = the click was skipped
        CLICK_FAILS[0] = 0
        return True

    def _click_interception(self, rx, ry):
        """Click through the Interception driver: the game sees a real mouse."""
        ic = interception_lib()
        if ic is None:
            return self._click_absolute(rx, ry)
        sx, sy = self.to_screen(rx, ry)
        ic.move_to(sx, sy)
        time.sleep(0.12)
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        if abs(pt.x - sx) > 4 or abs(pt.y - sy) > 4:
            log(f"  ! interception move ended at {pt.x},{pt.y} instead of {sx},{sy}; click skipped")
            return False
        ic.mouse_down("left")
        time.sleep(0.09)
        ic.mouse_up("left")
        time.sleep(0.05)

    def _click_absolute(self, rx, ry, tries=4):
        """Move and click with absolute screen coordinates in one input stream (like touch / remote tools).
        If something else moves the pointer (e.g. the RDP / iPad mouse), retry the move a few times."""
        sx, sy = self.to_screen(rx, ry)
        vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        vw, vh = max(user32.GetSystemMetrics(78), 2), max(user32.GetSystemMetrics(79), 2)
        ax = int((sx - vx) * 65535 / (vw - 1))
        ay = int((sy - vy) * 65535 / (vh - 1))
        base = 0x8000 | 0x4000          # ABSOLUTE | VIRTUALDESK
        pt = wintypes.POINT()
        for attempt in range(tries):
            _mouse(base | 0x0001, ax, ay)   # move
            time.sleep(0.15 + 0.15 * attempt)
            user32.GetCursorPos(ctypes.byref(pt))
            if abs(pt.x - sx) <= 4 and abs(pt.y - sy) <= 4:
                _mouse(base | 0x0001 | 0x0002, ax, ay)   # down at the same point
                time.sleep(0.09)
                _mouse(base | 0x0001 | 0x0004, ax, ay)   # up
                time.sleep(0.05)
                if attempt:
                    log(f"  absolute click landed on try {attempt + 1}")
                return True
            # nudge: a tiny relative move wakes the input stream after RDP took the pointer
            _mouse(0x0001, 1, 1)
            time.sleep(0.25)
        log(f"  ! absolute move ended at {pt.x},{pt.y} instead of {sx},{sy} after {tries} tries; click skipped")
        if (pt.x, pt.y) == (0, 0) and (sx, sy) != (0, 0):
            # v170: the pointer is pinned at 0,0 because the session has no input desktop
            # (Remote Desktop disconnected, screen switched off). No click can land; say so in
            # the words the round loop already understands, so it can move the session back.
            raise RuntimeError("screen grab failed: the input desktop is gone (the remote session is disconnected)")
        return False

    def _click_message(self, rx, ry):
        """Send the click straight to the game window (does not need the mouse pointer)."""
        cx, cy = int(rx * self.w), int(ry * self.h)
        target = self.hwnd
        # the game may draw inside a child window: find it and convert the point
        pt = wintypes.POINT(cx, cy)
        child = user32.ChildWindowFromPointEx(self.hwnd, pt, 0x0001 | 0x0002)   # skip invisible/disabled
        if child and child != self.hwnd:
            p2 = wintypes.POINT(cx, cy)
            user32.MapWindowPoints(self.hwnd, child, ctypes.byref(p2), 1)
            target, cx, cy = child, p2.x, p2.y
        lp = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
        user32.PostMessageW(target, 0x0200, 0, lp)          # WM_MOUSEMOVE
        time.sleep(0.06)
        user32.PostMessageW(target, 0x0201, 0x0001, lp)     # WM_LBUTTONDOWN
        time.sleep(0.09)
        user32.PostMessageW(target, 0x0202, 0, lp)          # WM_LBUTTONUP
        time.sleep(0.05)

    def _click_cursor(self, rx, ry):
        """Human-like click with the real mouse pointer."""
        sx, sy = self.to_screen(rx, ry)
        user32.SetCursorPos(sx, sy)
        time.sleep(0.12)
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        if abs(pt.x - sx) > 3 or abs(pt.y - sy) > 3:
            log(f"  ! mouse landed at {pt.x},{pt.y} instead of {sx},{sy}; click skipped")
            if (pt.x, pt.y) == (0, 0) and (sx, sy) != (0, 0):
                raise RuntimeError("screen grab failed: the input desktop is gone (the remote session is disconnected)")
            return False
        _mouse(0x0001, 1, 1)
        _mouse(0x0001, -1, -1)
        time.sleep(0.05)
        _mouse(0x0002)
        time.sleep(0.09)
        _mouse(0x0004)
        time.sleep(0.05)

    def screenshot(self):
        # NOTE: UnityCrashHandler64.exe runs from game start (it is dormant, not a sign of a
        # crash), so it cannot be used as a frozen-client test. A black frame is the reliable one.
        img = ImageGrab.grab(bbox=(self.x, self.y, self.x + self.w, self.y + self.h), all_screens=True)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        # v156: a crashed or off-screen game window grabs a pure black picture. The bot used to
        # keep clicking on it for minutes ("screen not recognised", failed scans). Put the window
        # back on screen and try once; if it stays black, say so instead of guessing.
        if float(frame.mean()) < 8:
            keep_on_screen(self.hwnd)
            activate(self.hwnd)
            time.sleep(0.6)
            img = ImageGrab.grab(bbox=(self.x, self.y, self.x + self.w, self.y + self.h), all_screens=True)
            frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            if float(frame.mean()) < 8:
                log("  ! the game window shows a black picture - it is off-screen or has crashed")
                raise RuntimeError("game window is black (off-screen or crashed)")
            log("  the game window was off-screen - moved it back and continued")
        return frame

    # ---------- templates ----------
    def save_template_around(self, name, rx, ry, size=0.045):
        """Cut a square around a relative point and save it as a template."""
        img = self.screenshot()
        half = int(size * self.w / 2)
        cx, cy = int(rx * self.w), int(ry * self.h)
        x1, y1 = max(cx - half, 0), max(cy - half, 0)
        x2, y2 = min(cx + half, self.w), min(cy + half, self.h)
        cv2.imwrite(os.path.join(TEMPL_DIR, name + ".png"), img[y1:y2, x1:x2])
        meta = load_json(os.path.join(TEMPL_DIR, "meta.json"), {})
        meta[name] = {"width": self.w}
        save_json(os.path.join(TEMPL_DIR, "meta.json"), meta)

    def find_image(self, name, threshold=0.80, find_all=False, img=None):
        """Return list of (rx, ry) centres where the template matches.
        Looks in templates/ (your recordings) then builtin_templates/ (smart activities).
        Tries a few sizes around the expected scale, so small window-size changes still match."""
        folder = TEMPL_DIR if os.path.exists(os.path.join(TEMPL_DIR, name + ".png")) else BUILTIN_DIR
        path = os.path.join(folder, name + ".png")
        if not os.path.exists(path):
            log(f"  ! template missing: {name}")
            return []
        tpl0 = cv2.imread(path)
        meta = load_json(os.path.join(folder, "meta.json"), {})
        base = self.w / meta.get(name, {}).get("width", self.w)
        img = self.screenshot() if img is None else img
        best = None
        for f in (1.0, 0.92, 1.08, 0.85, 1.17):
            sc = base * f
            tpl = tpl0 if abs(sc - 1) < 0.02 else cv2.resize(tpl0, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_LINEAR)
            if tpl.shape[0] < 8 or tpl.shape[0] > img.shape[0] or tpl.shape[1] > img.shape[1]:
                continue
            res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
            mx = float(res.max())
            if best is None or mx > best[0]:
                best = (mx, res, tpl.shape[:2])
            if mx >= 0.9:
                break
        if best is None or best[0] < threshold:
            return []
        _, res, (th, tw) = best
        hits = []
        if not find_all:
            _, _, _, loc = cv2.minMaxLoc(res)
            hits.append(loc)
        else:
            ys, xs = np.where(res >= threshold)
            for x, y in sorted(zip(xs, ys), key=lambda p: -res[p[1], p[0]]):
                if all(abs(x - hx) > tw // 2 or abs(y - hy) > th // 2 for hx, hy in hits):
                    hits.append((x, y))
        return [((x + tw / 2) / self.w, (y + th / 2) / self.h) for x, y in hits]


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    """Write JSON atomically, with retries.

    v148: Google Drive / antivirus on this VPS sometimes hold a file for a moment; the plain
    open(...,"w") then raised PermissionError and killed the character rotation. Writing to a
    temporary file and replacing it means a reader never sees half a file, and a retry rides
    over the short lock.
    """
    text = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = path + ".tmp"
    last = None
    for attempt in range(5):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, path)
            return True
        except OSError as e:                     # PermissionError / sharing violation
            last = e
            time.sleep(0.4 * (attempt + 1))
            try:
                os.remove(tmp)
            except Exception:
                pass
    log(f"  ! could not save {os.path.basename(path)}: {last!r}")
    return False
