# -*- coding: utf-8 -*-
"""
SEC-03: secrets, log sanitisation, file permissions and path safety for Kingbot.

Why: the status the bot publishes (kingbot-syn, a PUBLIC repository) carries the last log lines, the
stream link and error texts. Without KB_PASSPHRASE it is plain text for anyone on the internet.
A single log line holding a token, a webhook or a password would give that secret away.

  redact(text) / redact_obj(obj)
      hide GitHub tokens, Telegram bot tokens, Discord webhooks, "password=" / "Bearer" values and the
      exact values of every secret in local_config.json / .env (KB_PASSPHRASE, STREAM_PASSWORD, ...).
      common.log() runs every line through it, so log.txt, Telegram and the dashboard never see them.
  harden_secret_files()
      github_token.txt, telegram*.txt, local_config.json, .env: readable only by this Windows user,
      Administrators and SYSTEM (icacls); chmod 600 elsewhere. Once a day; off with HARDEN_PERMS=false.
  safe_join(base, *parts) / safe_name(name)
      a path built from outside input (an update zip, a command file) must stay inside its folder:
      "..", absolute paths, drive letters and device names are refused.

No Windows-only imports at load time: the module also runs (and is tested) on Linux.
"""
import os, re, sys, time, json, subprocess

import kb_paths
BASE = kb_paths.base_dir(__file__)   # SEC-04
MASK = "[hidden]"

# ------------------------------------------------------------------ redaction
# Built from pieces so this file never contains anything that looks like a real token.
_PATTERNS = [
    (re.compile(r"\b(gh[pousr]_)[A-Za-z0-9]{20,}"), r"\1" + MASK),                  # GitHub classic tokens
    (re.compile(r"\b(github_pat_)[A-Za-z0-9_]{20,}"), r"\1" + MASK),               # GitHub fine-grained
    (re.compile(r"\b(\d{6,12}):[A-Za-z0-9_-]{30,}"), r"\1:" + MASK),                # Telegram bot token
    (re.compile(r"(https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/)[A-Za-z0-9_.-]+",
                re.I), r"\1" + MASK),                                                # Discord webhook
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{12,}"), r"\1" + MASK),        # Authorization header
    (re.compile(r"(?i)([?&](?:password|pass|pw|pwd|token|key|secret|access_token)=)[^&\s\"'#]+"),
     r"\1" + MASK),                                                                  # secrets in URLs
    (re.compile(r"(?i)(\"[A-Za-z_]*(?:passphrase|password|secret|token|webhook|api[_-]?key)[A-Za-z_]*\"\s*:\s*\")"
                r"(?!\[hidden\])[^\"]+(\")"), r"\1" + MASK + r"\2"),                 # "KEY": "value with spaces"
    (re.compile(r"(?i)(\"?(?:kb_passphrase|stream_password|password|passphrase|api[_-]?key|secret|token)\"?"
                r"\s*[:=]\s*\"?)(?!\[hidden\])[^\s\",}]{4,}"), r"\1" + MASK),        # key=value / "key": "value"
]
SECRET_KEY_RX = re.compile(r"(?i)(pass|secret|token|webhook|api[_-]?key|private)")
MIN_SECRET_LEN = 6
_vals = {"at": 0.0, "list": []}


def _secret_values():
    """Exact values of secrets on this server (local_config.json / .env / token files), cached 60 s."""
    if time.time() - _vals["at"] < 60:
        return _vals["list"]
    vals = set()
    try:
        import server_config
        for k, v in (server_config.local() or {}).items():
            if SECRET_KEY_RX.search(str(k)) and isinstance(v, str) and len(v) >= MIN_SECRET_LEN:
                vals.add(v)
    except Exception:
        pass
    for name in ("github_token.txt", "telegram.txt"):
        try:
            with open(os.path.join(BASE, name), encoding="utf-8-sig") as f:
                v = f.read().strip()
            if len(v) >= MIN_SECRET_LEN and "\n" not in v:
                vals.add(v)
        except Exception:
            pass
    _vals.update(at=time.time(), list=sorted(vals, key=len, reverse=True))
    return _vals["list"]


def add_secret(value):
    """Register a secret that is not in a config file (e.g. one generated at runtime)."""
    if isinstance(value, str) and len(value) >= MIN_SECRET_LEN:
        lst = set(_vals["list"]) | {value}
        _vals["list"] = sorted(lst, key=len, reverse=True)


def redact(text):
    if not isinstance(text, str) or not text:
        return text
    out = text
    for v in _secret_values():
        if v in out:
            out = out.replace(v, MASK)
    for rx, rep in _PATTERNS:
        out = rx.sub(rep, out)
    return out


SENSITIVE_FIELDS = re.compile(r"(?i)^(.*(password|passphrase|secret|token|webhook|api[_-]?key|authorization).*)$")


def redact_obj(obj, _depth=0):
    """Copy of a dict/list with secret-named fields masked and every string redacted."""
    if _depth > 12:
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and SENSITIVE_FIELDS.match(k) and isinstance(v, (str, int, float)) and v not in ("", None):
                out[k] = MASK
            else:
                out[k] = redact_obj(v, _depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v, _depth + 1) for v in obj]
    if isinstance(obj, str):
        return redact(obj)
    return obj


# ------------------------------------------------------------------ path safety
_WIN_DEVICES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


class UnsafePath(ValueError):
    pass


def safe_name(name, maxlen=80):
    """A single file-name part made safe (letters, digits, - _ . and Arabic), never '..' or a device."""
    s = re.sub(r"[^\w\-. ؀-ۿ]", "_", str(name or ""))[:maxlen].strip(" .")
    if not s or s in (".", "..") or s.split(".")[0].lower() in _WIN_DEVICES:
        s = "_" + s.strip(".") if s.strip(".") else "_"
    return s


def safe_join(base, *parts):
    """Join under `base`; raise UnsafePath if the result would leave it (.., absolute, drive, UNC)."""
    root = os.path.realpath(os.path.abspath(base))
    for p in parts:
        p = str(p).replace("\\", "/")
        if p.startswith("/") or re.match(r"^[A-Za-z]:", p) or p.startswith("//") or "\0" in p:
            raise UnsafePath(f"absolute path not allowed: {p!r}")
        if any(seg == ".." for seg in p.split("/")):
            raise UnsafePath(f"'..' not allowed: {p!r}")
    full = os.path.realpath(os.path.join(root, *[str(p).replace("\\", "/") for p in parts]))
    if os.path.normcase(full) != os.path.normcase(root) and \
            not os.path.normcase(full).startswith(os.path.normcase(root) + os.sep):
        raise UnsafePath(f"path leaves {root}: {full}")
    return full


# ------------------------------------------------------------------ file permissions
SECRET_FILES = ("github_token.txt", "telegram.txt", "telegram_owner.txt", "local_config.json", ".env")
_HARDEN_MARK = os.path.join(BASE, "perm_state.json")       # git-ignored (*_state*.json)


def _cfg_on(key, default=True):
    try:
        import server_config
        v = server_config.get(key, default)
    except Exception:
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("0", "false", "no", "off")
    return bool(v)


def harden_file(path):
    """Owner-only access. Windows: icacls (this user + Administrators + SYSTEM). Returns True when done."""
    if not os.path.isfile(path):
        return False
    try:
        if os.name == "nt":
            user = os.environ.get("USERNAME") or ""
            grants = ["*S-1-5-18:F", "*S-1-5-32-544:F"]        # SYSTEM, Administrators (any Windows language)
            if user:
                grants.insert(0, f"{user}:F")
            cmd = ["icacls", path, "/inheritance:r"]
            for g in grants:
                cmd += ["/grant:r", g]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, creationflags=0x08000000)
            return r.returncode == 0
        os.chmod(path, 0o600)
        return True
    except Exception:
        return False


def harden_secret_files(log=None, force=False):
    """Restrict the secret files once a day (and at once with force=True). Never raises."""
    if not _cfg_on("HARDEN_PERMS", True):
        return []
    try:
        with open(_HARDEN_MARK, encoding="utf-8") as f:
            last = json.load(f).get("at", 0)
    except Exception:
        last = 0
    if not force and time.time() - last < 86400:
        return []
    done = []
    for name in SECRET_FILES:
        p = os.path.join(BASE, name)
        if os.path.isfile(p) and harden_file(p):
            done.append(name)
    try:
        from kb_safeio import atomic_write_json
        atomic_write_json(_HARDEN_MARK, {"at": time.time(), "files": done}, make_backup=False)
    except Exception:
        pass
    if log and done:
        log(f"Security: access to {', '.join(done)} limited to this Windows user, Administrators and SYSTEM.")
    return done


def encryption_on():
    try:
        import server_config
        return bool(server_config.get("KB_PASSPHRASE"))
    except Exception:
        return False
