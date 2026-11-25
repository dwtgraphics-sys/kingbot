# -*- coding: utf-8 -*-
"""
Telegram link for Kingbot.

Put your bot token (from @BotFather) alone in telegram.txt next to this file.
The first Telegram account that sends /start becomes the owner (saved in telegram_owner.txt);
everyone else is ignored. Delete telegram_owner.txt to choose a new owner.

Commands: /status /shot /log /pause /resume /now /help
"""
import os, ssl, json, time, threading, uuid, urllib.request, urllib.parse

from common import BASE, LOG_HOOKS, log, load_json, ROUTINES_FILE
from updater import local_version

TOKEN_FILE = os.path.join(BASE, "telegram.txt")
OWNER_FILE = os.path.join(BASE, "telegram_owner.txt")

HELP = ("أوامر Kingbot:\n"
        "/status حالة البوت\n"
        "/shot صورة من الشاشة الآن\n"
        "/log آخر سطور السجل\n"
        "/pause إيقاف مؤقت\n"
        "/resume تشغيل\n"
        "/now ابدأ جولة الآن\n"
        "/help هذه القائمة")


class Telegram:
    def __init__(self, token, ctl, status_fn):
        self.api = f"https://api.telegram.org/bot{token}/"
        self.ctl = ctl
        self.status_fn = status_fn
        self.owner = None
        try:
            self.owner = int(open(OWNER_FILE).read().strip())
        except Exception:
            pass
        self.offset = 0
        self.queue = []
        self.lock = threading.Lock()
        self.ctx = None
        self.last_err = None

    def _pick_context(self):
        """Find a certificate store that trusts api.telegram.org (Python default, Windows store, certifi)."""
        options = [("python default", lambda: ssl.create_default_context())]
        try:
            import truststore
            options.append(("windows store", lambda: truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)))
        except Exception:
            pass
        try:
            import certifi
            options.append(("certifi", lambda: ssl.create_default_context(cafile=certifi.where())))
        except Exception:
            pass
        errors = []
        for name, make in options:
            try:
                ctx = make()
                urllib.request.urlopen(self.api + "getMe", context=ctx, timeout=20).read()
                log(f"Telegram connection OK ({name}).")
                return ctx
            except Exception as e:
                errors.append(f"{name}: {str(e)[:90]}")
        log("! Telegram connection failed: " + " | ".join(errors))
        return None

    # ---------- HTTP ----------
    def _call(self, method, params=None, timeout=40):
        data = urllib.parse.urlencode(params or {}).encode()
        with urllib.request.urlopen(self.api + method, data=data, timeout=timeout, context=self.ctx) as r:
            return json.loads(r.read().decode("utf-8"))

    def send(self, text):
        if not self.owner:
            return
        try:
            self._call("sendMessage", {"chat_id": self.owner, "text": text[:4000]}, timeout=20)
        except Exception as e:
            print("telegram send failed:", e)

    def send_photo(self, path, caption=""):
        boundary = uuid.uuid4().hex
        with open(path, "rb") as f:
            img = f.read()
        parts = []
        for k, v in (("chat_id", str(self.owner)), ("caption", caption)):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="screen.jpg"\r\n'
                     f'Content-Type: image/jpeg\r\n\r\n'.encode() + img + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        req = urllib.request.Request(self.api + "sendPhoto", data=b"".join(parts),
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        urllib.request.urlopen(req, timeout=60, context=self.ctx).read()

    # ---------- notifications from the log ----------
    def on_log(self, msg):
        m = msg.strip()
        important = (m.startswith("!") or "failed" in m.lower() or m.startswith("Round started")
                     or m.startswith("Round finished") or m.startswith("Stopped") or m.startswith("Updated to")
                     or m.startswith("Paused") or "Outside working hours" in m or "Game window not found" in m)
        if important:
            with self.lock:
                self.queue.append(m)

    def _flush(self):
        with self.lock:
            items, self.queue = self.queue, []
        if items:
            self.send("👑 Kingbot\n" + "\n".join(items[-15:]))

    # ---------- commands ----------
    def _handle(self, msg):
        chat = msg.get("chat", {}).get("id")
        text = (msg.get("text") or "").strip().split("@")[0].lower()
        if self.owner is None and text == "/start":
            self.owner = chat
            with open(OWNER_FILE, "w") as f:
                f.write(str(chat))
            log("Telegram owner registered.")
            self.send("✅ تم ربط Kingbot بحسابك.\n\n" + HELP)
            return
        if chat != self.owner:
            return
        if text in ("/start", "/help"):
            self.send(HELP)
        elif text == "/status":
            self.send(self.status_fn())
        elif text == "/log":
            try:
                with open(os.path.join(BASE, "log.txt"), encoding="utf-8", errors="replace") as f:
                    self.send("".join(f.readlines()[-20:]) or "السجل فارغ")
            except Exception:
                self.send("لا يوجد سجل بعد")
        elif text == "/shot":
            from control import take_screenshot
            import tempfile
            p = take_screenshot(os.path.join(tempfile.gettempdir(), "kingbot_tg.jpg"))
            if p:
                try:
                    self.send_photo(p, "شاشة السيرفر الآن")
                except Exception as e:
                    self.send(f"تعذر إرسال الصورة: {e}")
            else:
                self.send("تعذر التقاط الصورة. تأكد أن جلسة سطح المكتب على السيرفر ليست مقفلة.")
        elif text == "/pause":
            ok = self.ctl.send_settings({"running": False})
            self.send("⏸ تم الإيقاف المؤقت" if ok else "تعذر الإيقاف: مجلد Google Drive غير متاح")
        elif text in ("/resume", "/run"):
            ok = self.ctl.send_settings({"running": True})
            self.send("▶️ تم التشغيل" if ok else "تعذر التشغيل: مجلد Google Drive غير متاح")
        elif text == "/now":
            ok = self.ctl.send_settings({"running": True, "run_now": str(time.time())})
            self.send("🚀 تبدأ جولة جديدة الآن" if ok else "تعذر: مجلد Google Drive غير متاح")
        else:
            self.send("أمر غير معروف.\n\n" + HELP)

    def loop(self):
        while self.ctx is None:
            self.ctx = self._pick_context()
            if self.ctx is None:
                time.sleep(600)   # try again in 10 minutes
        log("Telegram link started." + ("" if self.owner else " Send /start to your bot to become its owner."))
        last_flush = 0
        while True:
            try:
                res = self._call("getUpdates", {"offset": self.offset, "timeout": 25}, timeout=35)
                for u in res.get("result", []):
                    self.offset = u["update_id"] + 1
                    if "message" in u:
                        try:
                            self._handle(u["message"])
                        except Exception as e:
                            print("telegram command failed:", e)
            except Exception as e:
                if str(e) != self.last_err:
                    print("telegram poll failed:", e)
                    self.last_err = str(e)
                time.sleep(15)
            if time.time() - last_flush > 20:
                self._flush()
                last_flush = time.time()


LINK = None


def notify(text):
    """v105: push a bot notification (attack, mail, day summary ...) to the owner's Telegram chat."""
    if LINK is not None:
        threading.Thread(target=LINK.send, args=(text,), daemon=True).start()


def start(ctl, status_fn):
    """Start the Telegram link in the background if telegram.txt exists. Returns the link or None."""
    try:
        token = open(TOKEN_FILE, encoding="utf-8-sig").read().strip()
    except Exception:
        return None
    if ":" not in token:
        log("! telegram.txt does not look like a bot token.")
        return None
    global LINK
    tg = Telegram(token, ctl, status_fn)
    LINK = tg
    LOG_HOOKS.append(tg.on_log)
    threading.Thread(target=tg.loop, daemon=True).start()
    return tg
