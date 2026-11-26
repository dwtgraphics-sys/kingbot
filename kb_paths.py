# -*- coding: utf-8 -*-
"""
SEC-04: where Kingbot's files live, so a protected (packaged) build keeps code and runtime data apart.

Run as a normal script  -> base_dir() is the Kingbot folder (exactly as before; nothing changes).
Run as a PyInstaller exe -> the application code is frozen and read-only inside the bundle, while
                            settings, state, logs, templates and backups must stay WRITABLE. The
                            launcher sets KINGBOT_HOME to a writable folder next to the exe; this
                            module returns that folder, so an update/rebuild of the exe never touches
                            the user's runtime files.

Every module computes BASE through base_dir(__file__), so there is one answer for the whole app.
When not frozen and KINGBOT_HOME is unset, base_dir(f) == os.path.dirname(os.path.abspath(f)) as before.
"""
import os, sys

MUTABLE_DIRS = ("templates", "claude_out", "backups", "stream_chrome")


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def base_dir(file=None):
    """The folder that holds runtime files (settings, state, logs, templates, backups)."""
    home = os.environ.get("KINGBOT_HOME")
    if home:
        return os.path.abspath(home)
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    if file:
        return os.path.dirname(os.path.abspath(file))
    return os.path.dirname(os.path.abspath(__file__))


def code_dir():
    """Where the application code sits (inside the bundle when frozen, else the Kingbot folder)."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


def ensure_runtime_dirs(base=None):
    """Create the writable folders the bot needs. Returns the ones it could not create."""
    base = base or base_dir()
    failed = []
    for d in MUTABLE_DIRS:
        try:
            os.makedirs(os.path.join(base, d), exist_ok=True)
        except Exception:
            failed.append(d)
    return failed
