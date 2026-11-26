# -*- coding: utf-8 -*-
"""ADM-02: build a portable, versioned Kingbot bundle that can be copied to any managed server.

    python tools/make_bundle.py            -> dist/Kingbot_bundle_v<N>.zip (+ .sha256)

Contains only CODE (bot, sync, config/template modules, builtin_templates, launchers). Never secrets, never
server runtime (config/, state/, logs/, slots/, templates/, local_config.json, tokens). Install on a server:

    py -3 updater.py --install-bundle Kingbot_bundle_v<N>.zip     (backup first, runtime untouched, restart the bot)
    py -3 updater.py --rollback                                   (back to the previous version, updates held)
    py -3 updater.py --unpin                                      (release updates again)
Servers normally update themselves from GitHub; the bundle is for servers without GitHub access or offline copies.
"""
import hashlib, json, os, subprocess, sys, time, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import updater  # noqa: E402

EXCLUDE = updater.GH_SKIP_PREFIX + updater.RUNTIME_PREFIX + ("tools/", "dist/", "kingbot_dashboard_")
SECRET = set(updater.NEVER_OVERWRITE) - {"tasks.json"}


def files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    except Exception:
        out = [os.path.relpath(os.path.join(r, f), ROOT).replace("\\", "/") for r, _d, fs in os.walk(ROOT) for f in fs]
    return sorted(f for f in out if f and not f.startswith(EXCLUDE) and f not in SECRET and "__pycache__" not in f
                  and not f.endswith((".bak", ".pyc")))


def main():
    ver = updater.local_version()
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = ""
    fl = files()
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", f"Kingbot_bundle_v{ver}.zip")
    h = hashlib.sha256()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in fl:
            data = open(os.path.join(ROOT, f), "rb").read()
            if f.endswith(".py"):
                compile(data.decode("utf-8-sig"), f, "exec")
            h.update(f.encode() + data)
            z.writestr(f, data)
        z.writestr("BUNDLE.json", json.dumps({"version": ver, "sha": sha, "made": time.strftime("%Y-%m-%d %H:%M:%S"),
                                              "files": len(fl), "content_sha256": h.hexdigest()}, indent=1))
    dig = hashlib.sha256(open(out, "rb").read()).hexdigest()
    open(out + ".sha256", "w").write(f"{dig}  {os.path.basename(out)}\n")
    print(f"{out}  ({len(fl)} files, {os.path.getsize(out) // 1024} KB)  sha256 {dig[:16]}…")


if __name__ == "__main__":
    main()
