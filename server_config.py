# -*- coding: utf-8 -*-
"""
Which server is this bot? (v193, multi-server)

The answer lives in a LOCAL file that is never uploaded to GitHub:
    C:\\RisBot\\local_config.json   {"SERVER_ID": "vps-02-pilot"}
or  C:\\RisBot\\.env               SERVER_ID=vps-02-pilot
Without either, the bot is the main server "vps-01-main" (as before).

kingbot-syn/servers/index.json says where each server's files are:
    control  -> settings from the dashboard
    status   -> bot status for the dashboard
    screen   -> screenshot
The main server is marked "legacy": it keeps control/control.json and outbox/ until it is moved.
"""
import os, json, time, base64, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
LOCAL_JSON = os.path.join(BASE, "local_config.json")
LOCAL_ENV = os.path.join(BASE, ".env")
CACHE = os.path.join(BASE, "servers_index_cache.json")
OWNER, REPO = "dwtgraphics-sys", "kingbot-syn"
DEFAULT_ID = "vps-01-main"
REFRESH = 120            # seconds between reads of servers/index.json (raw CDN, no API limit)

# used when GitHub cannot be reached and nothing is cached yet
BUILTIN = {
    "vps-01-main": {"id": "vps-01-main", "legacy": True, "control": "control/control.json",
                    "status": "outbox/status.json", "screen": "outbox/screen.jpg"},
}

_local = {"data": None, "mtime": None}
_index = {"data": None, "at": 0.0}


def _read_env(path):
    out = {}
    try:
        for line in open(path, encoding="utf-8-sig"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def local():
    """local_config.json merged over .env (both optional, both git-ignored). Re-read when changed."""
    stamp = tuple(os.path.getmtime(p) if os.path.isfile(p) else 0 for p in (LOCAL_JSON, LOCAL_ENV))
    if _local["data"] is not None and _local["mtime"] == stamp:
        return _local["data"]
    d = _read_env(LOCAL_ENV)
    try:
        j = json.load(open(LOCAL_JSON, encoding="utf-8-sig"))
        if isinstance(j, dict):
            d.update({k: v for k, v in j.items() if v not in (None, "")})
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"! local_config.json is not valid JSON: {e}")
    _local.update(data=d, mtime=stamp)
    return d


def get(key, default=None):
    return local().get(key, os.environ.get(key, default))


def server_id():
    sid = str(get("SERVER_ID", DEFAULT_ID) or DEFAULT_ID).strip()
    return sid if sid.replace("-", "").replace("_", "").isalnum() else DEFAULT_ID


def _fetch_index():
    url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/servers/index.json?t={int(time.time())}"
    req = urllib.request.Request(url, headers={"User-Agent": "Kingbot-VPS", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=12) as r:
        d = json.loads(r.read().decode("utf-8-sig"))
    if not isinstance(d, dict) or not isinstance(d.get("servers"), list):
        raise ValueError("servers/index.json has no server list")
    return d


def index():
    if _index["data"] is not None and time.time() - _index["at"] < REFRESH:
        return _index["data"]
    try:
        d = _fetch_index()
        try:
            json.dump(d, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception:
            pass
    except Exception:
        d = _index["data"]
        if d is None:
            try:
                d = json.load(open(CACHE, encoding="utf-8"))
            except Exception:
                d = {"servers": list(BUILTIN.values())}
    _index.update(data=d, at=time.time())
    return d


def me():
    """This server's entry: id, legacy, control/status/screen paths in kingbot-syn."""
    sid = server_id()
    s = next((x for x in index().get("servers", []) if x.get("id") == sid), None)
    if s is None:
        s = BUILTIN.get(sid) or {"id": sid, "legacy": False, "control": f"servers/{sid}/control.json",
                                 "status": f"servers/{sid}/outbox/status.json",
                                 "screen": f"servers/{sid}/outbox/screen.jpg"}
    return dict(s)


def path(kind):
    """kind = control | status | screen"""
    return me().get(kind) or BUILTIN[DEFAULT_ID][kind]
