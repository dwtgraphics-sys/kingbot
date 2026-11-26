# -*- coding: utf-8 -*-
"""
SEC-04: startup integrity and runtime checks for Kingbot.

startup_check(log) runs once when the bot starts and makes sure the ground is solid before the loop:
  1. Python is new enough and the third-party packages the bot needs are importable.
  2. The writable runtime folders exist (templates/, claude_out/, backups/, ...); it creates them.
  3. There is enough free disk for logs, backups and screenshots.
  4. If a protected build shipped an integrity manifest (integrity.json: sha256 of each core .py / the exe),
     the running files are checked against it and any mismatch is reported (a tampered or half-updated build).

A *fatal* problem (a core package missing, no writable folder, disk full) stops the bot with a clear
message and SystemExit(2) instead of letting it crash deep inside the game loop. Everything else is a
warning in the log and on the dashboard.

build_manifest(paths) writes integrity.json during packaging. verify_manifest() reads it at runtime.
The module imports nothing Windows-only, so it also runs (and is tested) on Linux / in CI.
"""
import os, sys, json, hashlib, shutil

import kb_paths

BASE = kb_paths.base_dir(__file__)
CODE = kb_paths.code_dir()
MANIFEST = os.path.join(CODE, "integrity.json")
MIN_PYTHON = (3, 8)
MIN_FREE_GB = 1.0

# import name -> what to tell the user to install (pip name)
REQUIRED_PACKAGES = {"numpy": "numpy", "cv2": "opencv-python", "PIL": "pillow", "pyautogui": "pyautogui"}
# core modules that must be present for the bot to work at all
CORE_MODULES = ("common", "control", "smart", "updater", "server_config", "queue_manager",
                "automation", "alerts", "game_launcher", "kb_safeio", "kb_secure", "kb_health")


class IntegrityError(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ checks
def check_python():
    if sys.version_info[:2] < MIN_PYTHON:
        return [f"Python {sys.version_info.major}.{sys.version_info.minor} is too old "
                f"(need {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+)"]
    return []


def check_packages():
    import importlib.util
    missing = [pip for mod, pip in REQUIRED_PACKAGES.items() if importlib.util.find_spec(mod) is None]
    return [f"missing Python package(s): {', '.join(missing)} - run: pip install {' '.join(missing)}"] if missing else []


def check_core_modules():
    """Every core .py is present next to the code (not that it imports - that happens as the bot runs)."""
    if kb_paths.is_frozen():
        return []                                    # bundled inside the exe; the manifest check covers it
    missing = [m for m in CORE_MODULES if not os.path.isfile(os.path.join(CODE, m + ".py"))]
    return [f"missing program file(s): {', '.join(m + '.py' for m in missing)}"] if missing else []


def check_dirs():
    failed = kb_paths.ensure_runtime_dirs(BASE)
    if not os.access(BASE, os.W_OK):
        return [f"the Kingbot folder is not writable: {BASE}"]
    return [f"could not create runtime folder(s): {', '.join(failed)}"] if failed else []


def check_disk():
    try:
        free_gb = shutil.disk_usage(BASE).free / 1024 ** 3
    except Exception:
        return []
    if free_gb < MIN_FREE_GB:
        return [f"only {free_gb:.1f} GB free on the bot's drive (need at least {MIN_FREE_GB:g} GB "
                f"for logs, backups and screenshots)"]
    return []


def verify_manifest():
    """(warnings, checked_count). Empty manifest -> nothing to check (script mode / unsigned build)."""
    if not os.path.isfile(MANIFEST):
        return [], 0
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            man = json.load(f)
        files = man.get("files", {})
    except Exception as e:
        return [f"integrity.json could not be read ({e})"], 0
    warns, n = [], 0
    for rel, want in files.items():
        p = os.path.join(CODE, rel)
        if not os.path.isfile(p):
            warns.append(f"protected file missing: {rel}")
            continue
        n += 1
        if sha256(p) != want:
            warns.append(f"protected file changed since the build: {rel}")
    return warns, n


# ------------------------------------------------------------------ entry point
def run_checks():
    """(fatal_list, warn_list). Fatal problems must stop the bot; warnings are only reported."""
    fatal = check_python() + check_packages() + check_core_modules() + check_dirs() + check_disk()
    warns, _ = verify_manifest()
    return fatal, warns


def startup_check(log=print):
    fatal, warns = run_checks()
    for w in warns:
        log(f"! integrity warning: {w}")
    if fatal:
        for fprob in fatal:
            log(f"! STARTUP CHECK FAILED: {fprob}")
        log("Kingbot cannot start safely until the problem above is fixed.")
        sys.exit(2)
    build = "packaged build" if kb_paths.is_frozen() else "script"
    extra = ""
    try:
        _, n = verify_manifest()
        if n:
            extra = f", {n} protected files verified"
    except Exception:
        pass
    log(f"Startup check passed ({build}, runtime folder {BASE}{extra}).")
    return True


# ------------------------------------------------------------------ packaging helper
def build_manifest(code_dir=None, out=None, patterns=(".py",), extra=()):
    """Write integrity.json: sha256 of every matching file under code_dir. Used by the build script."""
    code_dir = code_dir or CODE
    out = out or os.path.join(code_dir, "integrity.json")
    files = {}
    for root, _dirs, names in os.walk(code_dir):
        if any(part in (".git", "__pycache__", "tests", "backups") for part in root.split(os.sep)):
            continue
        for name in names:
            if name == "integrity.json":
                continue
            if name.endswith(patterns) or name in extra:
                p = os.path.join(root, name)
                files[os.path.relpath(p, code_dir).replace(os.sep, "/")] = sha256(p)
    man = {"version": 1, "files": files}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    return out, len(files)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "manifest":
        path, n = build_manifest(*(sys.argv[2:3] or []))
        print(f"wrote {path} ({n} files)")
    else:
        fatal, warns = run_checks()
        for w in warns:
            print("warning:", w)
        for fprob in fatal:
            print("FATAL:", fprob)
        sys.exit(2 if fatal else 0)
