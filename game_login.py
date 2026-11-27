# -*- coding: utf-8 -*-
"""
v262 / LOGIN-01: first login of a new game account from the dashboard (verification-code login).

When the game has never been signed in, Rise of Kingdoms opens a small "Log In" window (owned by
limpcbrowserex.exe, title "Rise of Kingdoms"): tabs "Verification Code Login" / "Password Login",
an email box, a verification-code box with "Get Code", the "I have read and agreed ..." circle,
START and Guest Login.

The bot clicks NOTHING in that window by itself. It reports `city.game_login.stage = "need_email"`, the
dashboard opens a form, and the customer sends:
  1. action game_login_email {email}            -> the bot types the email and presses Get Code
  2. action game_login_code  {code, agree:true} -> the bot types the code, ticks the agreement circle
                                                   (only when the customer ticked it in the form) and
                                                   presses START.
Rules: everything is found by its text (Windows OCR), never by a guessed position; Guest Login,
Password Login and anything about deleting / unbinding is never pressed; the email and the code are never
written to the log, the status or a saved picture (the OCR scratch pictures are deleted at once).
"""
import os, re, time, ctypes
from ctypes import wintypes

import common
from common import log, user32, client_rect, activate, BASE

LOGIN_PROC = "limpcbrowserex.exe"
STATE = {"stage": "", "detail": "", "at": "", "email_hint": ""}
_CACHE = {"t": 0.0, "hwnd": None}
NEVER = ("guest", "password login", "delete", "unbind", "remove", "erase", "facebook", "apple", "google")


# ------------------------------------------------------------------ status
def _iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def set_stage(stage, detail=""):
    STATE.update(stage=stage, detail=str(detail or "")[:160], at=_iso())
    try:
        import control
        control.CITY["game_login"] = dict(STATE)
    except Exception:
        pass


def clear():
    STATE.update(stage="", detail="", at="", email_hint="")
    try:
        import control
        control.CITY.pop("game_login", None)
    except Exception:
        pass


def mask_email(e):
    e = str(e or "")
    if "@" not in e:
        return "***"
    u, d = e.split("@", 1)
    return (u[:1] + "***@" + d[:1] + "***") if u else "***"


# ------------------------------------------------------------------ the login window
def _exe_of(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        n = wintypes.DWORD(520)
        if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value).lower()
    finally:
        k.CloseHandle(h)
    return ""


def find_login_window(max_age=20):
    """hwnd of the visible Log In window, or None. Cached for max_age seconds (EnumWindows is cheap,
    but this runs in every idle tick)."""
    if time.time() - _CACHE["t"] < max_age and (_CACHE["hwnd"] is None or user32.IsWindow(_CACHE["hwnd"])):
        return _CACHE["hwnd"]
    found = []
    Enum = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w < 250 or h < 200:
            return True
        if _exe_of(hwnd) == LOGIN_PROC:
            found.append((w * h, hwnd))
        return True

    try:
        user32.EnumWindows(Enum(cb), 0)
    except Exception as e:
        log(f"  ! game_login: window scan failed: {e!r}")
    found.sort(reverse=True)
    _CACHE.update(t=time.time(), hwnd=found[0][1] if found else None)
    return _CACHE["hwnd"]


def _candidates():
    """Every visible window that could hold the Log In form: windows of limpcbrowserex.exe and non-Unity windows
    titled 'Rise of Kingdoms' (v265: the biggest limpcbrowserex window was a 946x532 host, not the form)."""
    out = []
    Enum = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        if r.right - r.left < 250 or r.bottom - r.top < 200:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        cls = common.window_class(hwnd)
        if _exe_of(hwnd) == LOGIN_PROC or ("rise of kingdoms" in buf.value.lower() and cls != "UnityWndClass"):
            out.append(hwnd)
        return True

    user32.EnumWindows(Enum(cb), 0)
    return out


LOGIN_WORDS = ("log in", "verification code", "enter your email", "get code", "guest login")


class LoginWin:
    """The area the Log In form is drawn in. Each candidate window is read by OCR and the one that shows the
    form wins; if none does, the whole screen is used (clicks are then in screen pixels)."""
    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.full = False
        best = None
        for h in [hwnd] + [c for c in _candidates() if c != hwnd]:
            self.hwnd = h
            self.refresh()
            try:
                txt = " ".join(b[4].lower() for b in _ocr(self.shot()))
            except Exception:
                txt = ""
            hits = sum(w in txt for w in LOGIN_WORDS)
            log(f"  game login: window {self.w}x{self.h} at {self.x},{self.y} - {hits} login words")
            if hits and (best is None or hits > best[0]):
                best = (hits, h)
        if best:
            self.hwnd = best[1]
            self.refresh()
        else:
            self.full = True
            self.hwnd = hwnd
            self.refresh()
            log(f"  game login: the form was not found in a window - reading the whole screen {self.w}x{self.h}")

    def refresh(self):
        if getattr(self, "full", False):
            self.x, self.y = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
            self.w, self.h = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        else:
            self.x, self.y, self.w, self.h = client_rect(self.hwnd)

    def to_screen(self, rx, ry):
        sx = int(round(self.x + rx * self.w))
        sy = int(round(self.y + ry * self.h))
        return min(self.x + self.w - 1, max(self.x, sx)), min(self.y + self.h - 1, max(self.y, sy))

    def front(self):
        if not self.full:
            activate(self.hwnd)
        time.sleep(0.4)
        self.refresh()

    def shot(self):
        import cv2, numpy as np
        from PIL import ImageGrab
        self.refresh()
        img = ImageGrab.grab(bbox=(self.x, self.y, self.x + self.w, self.y + self.h), all_screens=True)
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def click_px(self, px, py):
        """Exact click on a pixel of the window picture (TASK-19: no random offset)."""
        self.front()
        return common.Game._click_absolute(self, px / self.w, py / self.h) is not False

    def scroll(self, clicks):
        import pyautogui
        sx, sy = self.to_screen(0.5, 0.5)
        pyautogui.moveTo(sx, sy)
        pyautogui.scroll(clicks)
        time.sleep(0.8)


PHRASES = ("verification code login", "password login", "enter your email address", "enter your verification code",
           "get code", "send code", "i have read and agreed", "user agreement", "start", "guest login", "log in")


def _ocr_words(img_bgr, scale):
    """[(x1, y1, x2, y2, line, word)] in image pixels (ocr_words.ps1)."""
    import cv2, subprocess
    big = cv2.resize(img_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    path = os.path.join(BASE, "claude_out", "login_ocr.png")
    cv2.imwrite(path, big)
    out = []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            os.path.join(BASE, "ocr_words.ps1"), path], capture_output=True, timeout=60,
                           creationflags=0x08000000)
        for ln in (r.stdout or b"").decode("utf-8", errors="replace").splitlines():
            p = ln.split("|", 5)
            if len(p) == 6 and p[0].lstrip("-").isdigit() and p[4].isdigit():
                out.append((int(p[0]) / scale, int(p[1]) / scale, int(p[2]) / scale, int(p[3]) / scale, int(p[4]), p[5].strip()))
    except Exception as e:
        log(f"    (ocr_words failed: {e!r})")
    return out


def _words_to_boxes(words):
    """Line boxes (like ocr_boxes) PLUS a box for every known phrase inside a line, made from its own words -
    so 'Get Code' gets its own box even when OCR puts it on one line with the code box's placeholder."""
    sq = lambda x: re.sub(r"[^a-z0-9@]", "", x.lower())
    lines = {}
    for w in words:
        lines.setdefault(w[4], []).append(w)
    boxes = []
    for ws in lines.values():
        ws.sort(key=lambda w: w[0])
        span = lambda a: (min(w[0] for w in a), min(w[1] for w in a), max(w[2] for w in a), max(w[3] for w in a))
        for ph in PHRASES:
            n = len(ph.split())
            for i in range(len(ws) - n + 1):
                part = ws[i:i + n]
                if sq("".join(w[5] for w in part)) == sq(ph):
                    boxes.append(span(part) + (" ".join(w[5] for w in part),))
        boxes.append(span(ws) + (" ".join(w[5] for w in ws),))
    boxes.sort(key=lambda b: (round(b[1] / 6), len(b[4])))        # same row: the exact phrase before the whole line
    return boxes


def _ocr(img, strong=False):
    """v270: strong=True reads light-grey placeholder text too (contrast stretch, bigger scale).
    v271: word-level OCR, phrase boxes first (see _words_to_boxes)."""
    try:
        if strong:
            import cv2
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            g = cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX)
            g = cv2.convertScaleAbs(g, alpha=1.8, beta=-160)          # light grey -> dark, white stays white
            img = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
            return _words_to_boxes(_ocr_words(img, 2.4))
        return _words_to_boxes(_ocr_words(img, 1.6))
    finally:
        try:                                               # the picture can show the email / code: never keep it
            os.remove(os.path.join(BASE, "claude_out", "login_ocr.png"))
        except Exception:
            pass


def _find(boxes, words, exact=False):
    """First box whose text matches one of words (lower case); boxes with a NEVER word are skipped."""
    sq = lambda x: re.sub(r"[\s.:]", "", x)                 # v271: OCR often glues words ("GetCode")
    for b in boxes:
        t = b[4].lower().strip()
        if any(n in t for n in NEVER):
            continue
        if any((sq(t) == sq(w)) if exact else (sq(w) in sq(t)) for w in words):
            return b
    return None


def _center(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _type(text, clear_first=True):
    import pyautogui
    if clear_first:
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(0.1)
    pyautogui.write(str(text), interval=0.04)
    time.sleep(0.3)


def _safe_texts(boxes):
    return [b[4][:30] for b in boxes if "@" not in b[4]][:25]          # never the email


def _look(win, words, exact=False, scrolls=(0, -3, 3, 3)):
    """Find text, scrolling the window if it is below / above the visible part. Each view is read normally and,
    if that misses, once more with strong contrast (placeholders are light grey)."""
    boxes = []
    for s in scrolls:
        if s:
            win.scroll(s)
        img = win.shot()
        for strong in (False, True):
            boxes = _ocr(img, strong)
            b = _find(boxes, words, exact)
            if b:
                return b, boxes
    log(f"  game login: '{words[0]}' not found; last texts: {_safe_texts(boxes)}")
    return None, boxes


ERR_WORDS = ("invalid", "incorrect", "error", "wrong", "expired", "too many", "frequent", "failed", "format",
             "try again later", "not exist")


def _errors(boxes):
    for b in boxes:
        t = b[4].lower()
        if any(w in t for w in ERR_WORDS):
            return b[4][:120]
    return ""


# ------------------------------------------------------------------ the two steps
def send_email(email):
    email = str(email or "").strip()
    if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}", email):
        set_stage("need_email", "البريد غير صحيح")
        return "failed: bad email"
    hwnd = find_login_window(0)
    if not hwnd:
        set_stage("", "")
        return "failed: no login window"
    win = LoginWin(hwnd)
    STATE["email_hint"] = mask_email(email)
    set_stage("sending_code", "جاري كتابة البريد وطلب الكود")
    log(f"  game login: typing the email ({STATE['email_hint']}) and asking for a code")
    tab, bx = _look(win, ("verification code login",), scrolls=(0, 5))
    log(f"  game login: {len(bx)} texts read, tab {'found' if tab else 'not found'}")
    if tab:
        win.click_px(*_center(tab)); time.sleep(1.5)
    box, _ = _look(win, ("enter your email", "email address", "@"))     # "@": the email is already in the box
    if not box:
        set_stage("need_email", "لم أجد خانة البريد في نافذة الدخول")
        return "failed: email box not found"
    win.click_px(*_center(box)); time.sleep(0.5)
    _type(email)
    log("  game login: email typed")
    get, boxes = _look(win, ("get code", "send code", "get verification"), scrolls=(0, -3, -3))
    if not get:
        set_stage("need_email", "لم أجد زر Get Code")
        return "failed: Get Code not found"
    log("  game login: pressing Get Code")
    win.click_px(*_center(get)); time.sleep(4)
    boxes = _ocr(win.shot())
    err = _errors(boxes)
    if err:
        set_stage("need_email", "رسالة اللعبة: " + err)
        log(f"  game login: the game says {err!r}")
        return "failed: " + err
    set_stage("code_sent", "أُرسل الكود إلى " + STATE["email_hint"])
    log("  game login: code requested - waiting for the code from the dashboard")
    return "done"


def _circle_ticked(img, px, py):
    """The agreement circle is filled with the red accent once it is ticked."""
    h, w = img.shape[:2]
    r = 7
    crop = img[max(0, int(py) - r):min(h, int(py) + r), max(0, int(px) - r):min(w, int(px) + r)]
    if crop.size == 0:
        return False
    b, g, rr = [float(crop[..., i].mean()) for i in range(3)]
    return rr > 140 and rr - max(b, g) > 50


def send_code(code, agree=False):
    code = re.sub(r"\s", "", str(code or ""))
    if not re.fullmatch(r"[0-9A-Za-z]{4,8}", code):
        set_stage("code_sent", "الكود غير صحيح")
        return "failed: bad code"
    if not agree:
        set_stage("code_sent", "يجب الموافقة على اتفاقية المستخدم")
        return "failed: agreement not accepted"
    hwnd = find_login_window(0)
    if not hwnd:
        set_stage("", "")
        return "failed: no login window"
    win = LoginWin(hwnd)
    set_stage("logging_in", "جاري كتابة الكود وتسجيل الدخول")
    log("  game login: typing the code")
    box = None
    for s in (0, -3, -3, 3):                                 # the box, never the "Verification Code Login" tab
        if s:
            win.scroll(s)
        box = next((b for b in _ocr(win.shot()) if ("enter your verification" in b[4].lower() or
                    ("verification code" in b[4].lower() and "login" not in b[4].lower()))), None)
        if box:
            break
    if not box:
        set_stage("code_sent", "لم أجد خانة الكود")
        return "failed: code box not found"
    cx, cy = _center(box)
    win.click_px(min(cx, box[0] + 40), cy); time.sleep(0.5)     # left part of the box, away from Get Code
    _type(code)
    agr, _ = _look(win, ("have read and agreed", "user agreement"), scrolls=(0, -3))
    if agr:
        img = win.shot()
        boxes = _ocr(img)
        agr = _find(boxes, ("have read and agreed", "user agreement")) or agr
        px, py = agr[0] - 1.4 * (agr[3] - agr[1]), _center(agr)[1]           # the circle sits left of the sentence
        if not _circle_ticked(img, px, py):
            win.click_px(px, py); time.sleep(0.8)
            if not _circle_ticked(win.shot(), px, py):
                log("  game login: the agreement circle does not look ticked - START may refuse")
    start, _ = _look(win, ("start",), exact=True, scrolls=(0, -3))
    if not start:
        set_stage("code_sent", "لم أجد زر START")
        return "failed: START not found"
    win.click_px(*_center(start))
    for _ in range(20):                                      # up to 60 s
        time.sleep(3)
        _CACHE["t"] = 0
        if not find_login_window(0):
            set_stage("logged_in", "تم تسجيل الدخول في اللعبة")
            log("  game login: the login window closed - signed in")
            return "done"
        try:
            err = _errors(_ocr(win.shot()))
        except Exception:
            err = ""
        if err:
            set_stage("code_sent", "رسالة اللعبة: " + err)
            log(f"  game login: the game says {err!r}")
            return "failed: " + err
    set_stage("code_sent", "نافذة الدخول ما زالت مفتوحة - تأكد من الكود")
    return "failed: still on the login window"


def handle(req):
    """Dashboard action game_login_email / game_login_code. Never logs the email or the code."""
    do = req.get("do")
    try:
        if do == "game_login_email":
            return send_email(req.get("email"))
        if do == "game_login_code":
            return send_code(req.get("code"), bool(req.get("agree")))
    except Exception as e:
        set_stage(STATE.get("stage") or "need_email", "خطأ: " + repr(e)[:100])
        return "failed: " + repr(e)[:120]
    return "unknown"
