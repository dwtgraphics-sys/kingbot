"""TASK-18: Smart alerts - instant Telegram / Discord messages for critical events only.

Events (each one switchable from the dashboard, settings key "alerts"):
    on_attack                 the city is attacked or scouted (auto shield)
    on_shield_drop            the peace shield the bot put on has ended
    on_captcha                a verification window stopped the bot
    on_server_offline         the game lost its connection for a long time / the game client was restarted
    on_subscription_expiring  the Kingbot subscription ends soon (sent by the dashboard side)

Each message carries the slot (server id + character), the event and, when possible, a screenshot.
Secrets stay on the server: Telegram uses telegram.txt (telegram_link), Discord uses DISCORD_WEBHOOK
from local_config.json / .env - nothing is stored on GitHub.
"""
import json
import os
import ssl
import tempfile
import threading
import time
import urllib.request
import uuid

from common import log

EVENTS = ("on_attack", "on_shield_drop", "on_captcha", "on_server_offline", "on_subscription_expiring")
LABEL = {
    "on_attack": "🚨 هجوم / استكشاف على المدينة",
    "on_shield_drop": "🛡️ انتهى درع السلام",
    "on_captcha": "🧩 نافذة تحقق (كابتشا)",
    "on_server_offline": "📡 انقطاع اتصال اللعبة",
    "on_subscription_expiring": "⏳ الاشتراك ينتهي قريباً",
    "test": "✅ تنبيه تجريبي",
}
SETTINGS = [lambda: {}]          # bot.py sets this to read ctl.data["alerts"]
_LAST = {}                       # event -> last send time (no repeats within 5 minutes)
_SHIELD = {"until": None, "sent": None}


def enabled(event):
    if event == "test":
        return True
    try:
        cfg = SETTINGS[0]() or {}
    except Exception:
        cfg = {}
    if cfg.get("enabled") is False:
        return False
    return cfg.get(event, True) is not False       # default: every critical alert is on


def _slot():
    try:
        import server_config
        sid = server_config.server_id()
    except Exception:
        sid = "server"
    try:
        import control
        c = next((c for c in (control.CITY.get("characters") or []) if c.get("current")), None)
        ch = (c or {}).get("name") or ""
    except Exception:
        ch = ""
    return sid + (" · " + ch if ch else "")


def _discord(url, text, photo):
    ctx = ssl.create_default_context()
    if photo and os.path.isfile(photo):
        b = uuid.uuid4().hex
        body = (f'--{b}\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n'
                + json.dumps({"content": text[:1900]}) + "\r\n").encode()
        body += f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="screen.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
        body += open(photo, "rb").read() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}",
                                                                 "User-Agent": "Kingbot"})
    else:
        req = urllib.request.Request(url, data=json.dumps({"content": text[:1900]}).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "Kingbot"})
    urllib.request.urlopen(req, timeout=30, context=ctx).read()


def _send(text, photo):
    sent = []
    try:
        import telegram_link
        link = telegram_link.LINK
        if link is not None and getattr(link, "owner", None):
            if photo:
                try:
                    link.send_photo(photo, caption=text[:1000])
                    sent.append("telegram")
                except Exception:
                    link.send(text); sent.append("telegram")
            else:
                link.send(text); sent.append("telegram")
    except Exception as e:
        log(f"  ! alert: telegram failed: {e!r}")
    try:
        import server_config
        url = server_config.get("DISCORD_WEBHOOK")
        if url and str(url).startswith("https://"):
            _discord(url, text, photo)
            sent.append("discord")
    except Exception as e:
        log(f"  ! alert: discord failed: {e!r}")
    log(f"  alert sent ({', '.join(sent) or 'no channel configured'})")


def fire(event, detail="", screenshot=True, wait=False):
    """Send one critical alert now (in the background). Returns True when it was sent or queued."""
    if not enabled(event):
        return False
    now = time.time()
    if event != "test" and now - _LAST.get(event, 0) < 300:
        return False
    _LAST[event] = now
    text = f"{LABEL.get(event, event)}\n{_slot()}\n{detail}".strip() + "\n" + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    photo = None
    if screenshot:
        try:
            from control import take_screenshot
            photo = take_screenshot(os.path.join(tempfile.gettempdir(), f"kingbot_alert_{event}.jpg"))
        except Exception:
            photo = None
    if wait:
        _send(text, photo)
    else:
        threading.Thread(target=_send, args=(text, photo), daemon=True).start()
    return True


def shield_watch():
    """Called often (cheap): when the shield the bot put on has ended, alert once."""
    try:
        import control
        sh = control.CITY.get("shield") or {}
        until = sh.get("until") if sh.get("state") == "on" else None
        if not until:
            return
        if _SHIELD["sent"] == until:
            return
        end = time.mktime(time.strptime(until, "%Y-%m-%d %H:%M")) - time.timezone   # UTC string -> epoch
        if time.time() >= end:
            _SHIELD["sent"] = until
            sh["state"] = "off"
            fire("on_shield_drop", f"انتهى الدرع الساعة {until} UTC — المدينة بلا حماية الآن")
    except Exception:
        pass
