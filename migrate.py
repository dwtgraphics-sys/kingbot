# -*- coding: utf-8 -*-
"""Kingbot - move to a new server (or add a second server with another game account).

    python migrate.py export                 -> migrate\\kingbot_state_<date>.zip       (no secrets)
    python migrate.py export --secrets       -> also migrate\\kingbot_secrets_<date>.kbe (AES-256, asks a passphrase)
    python migrate.py import <state.zip> [<secrets.kbe>] [--server-id vps-04-new]
    python migrate.py check                  -> what this server has / misses

The CODE never travels this way: every server downloads it from GitHub (updater.py).
The state zip carries what only exists on this server and is not secret:
    templates/ (your recordings + meta.json), vision_scales.json, building_pos.json, persist_city.json,
    profiles_by_char.json, task_state*.json, gems_day*.json, rotation_state.json, stats_days.json,
    mat_scan_cd.json, gather_next.txt, click_mode.txt, tasks.json
Secrets (github_token.txt, telegram*.txt, local_config.json) only go into the encrypted .kbe file, and only
with --secrets. Move the .kbe by a private channel and type the passphrase by hand on the new server.

A NEW game account on a NEW server: export WITHOUT --secrets is still useful (templates + vision scales),
but use --fresh on import: the per-account state (persist_city, profiles, task_state, gems_day, rotation,
stats, building_pos) is skipped so the new account starts clean.
"""
import datetime
import getpass
import glob
import json
import os
import sys
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "migrate")
SHARED = ["templates/**", "vision_scales.json", "click_mode.txt", "tasks.json", "brain.json"]
ACCOUNT = ["building_pos.json", "persist_city.json", "profiles_by_char.json", "task_state*.json", "gems_day*.json",
           "rotation_state.json", "stats_days.json", "mat_scan_cd.json", "gather_next.txt"]
SECRETS = ["github_token.txt", "telegram.txt", "telegram_owner.txt", "local_config.json"]


def _files(patterns):
    out = []
    for p in patterns:
        for f in glob.glob(os.path.join(BASE, p), recursive=True):
            if os.path.isfile(f):
                out.append(os.path.relpath(f, BASE).replace("\\", "/"))
    return sorted(set(out))


def export(with_secrets=False):
    os.makedirs(OUT, exist_ok=True)
    day = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    zp = os.path.join(OUT, f"kingbot_state_{day}.zip")
    files = _files(SHARED) + _files(ACCOUNT)
    manifest = {"made": day, "from_server": _server_id(), "version": _version(),
                "shared": _files(SHARED), "account": _files(ACCOUNT)}
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(BASE, f), f)
        z.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"state:   {zp}  ({len(files)} files, {os.path.getsize(zp) // 1024} KB) - no secrets inside")
    if with_secrets:
        import kb_crypto
        pw = getpass.getpass("Passphrase for the secrets file (you will type it on the new server): ")
        if len(pw) < 10 or pw != getpass.getpass("Again: "):
            print("! passphrases differ or shorter than 10 characters - secrets not exported")
            return zp, None
        blob = {f: open(os.path.join(BASE, f), "rb").read().decode("utf-8", "replace") for f in _files(SECRETS)}
        kp = os.path.join(OUT, f"kingbot_secrets_{day}.kbe")
        key = kb_crypto.derive(pw)
        with open(kp, "wb") as fh:
            fh.write(kb_crypto.seal_bytes(key, json.dumps(blob).encode("utf-8")))
        print(f"secrets: {kp}  ({len(blob)} files, AES-256) - send it privately, never by GitHub or chat")
        return zp, kp
    return zp, None


def do_import(zp, kp=None, server_id=None, fresh=False):
    with zipfile.ZipFile(zp) as z:
        man = json.loads(z.read("MANIFEST.json"))
        skip = set(man.get("account", [])) if fresh else set()
        n = 0
        for f in z.namelist():
            if f == "MANIFEST.json" or f in skip:
                continue
            dest = os.path.join(BASE, f)
            if os.path.exists(dest) and f.startswith("templates/"):
                pass                                         # the zip wins: these are the owner's recordings
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(z.read(f))
            n += 1
    print(f"state imported: {n} files{' (account state skipped: --fresh)' if fresh else ''} from {man.get('from_server')}")
    if kp:
        import kb_crypto
        pw = getpass.getpass("Passphrase of the secrets file: ")
        data = json.loads(kb_crypto.open_bytes(kb_crypto.derive(pw), open(kp, "rb").read()).decode("utf-8"))
        for f, txt in data.items():
            if f == "local_config.json" and server_id:
                try:
                    cfg = json.loads(txt)
                    cfg["SERVER_ID"] = server_id
                    txt = json.dumps(cfg, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            with open(os.path.join(BASE, f), "w", encoding="utf-8") as fh:
                fh.write(txt)
        print(f"secrets restored: {', '.join(sorted(data))}")
    if server_id and not kp:
        p = os.path.join(BASE, "local_config.json")
        cfg = {}
        if os.path.exists(p):
            cfg = json.load(open(p, encoding="utf-8-sig"))
        cfg["SERVER_ID"] = server_id
        json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"local_config.json: SERVER_ID = {server_id}")
    check()


def check():
    print("\n--- this server ---")
    for f in ("github_token.txt", "local_config.json", "telegram.txt"):
        print(f"  {'OK ' if os.path.exists(os.path.join(BASE, f)) else 'MISSING'} {f}")
    print(f"  server id : {_server_id() or 'MISSING (local_config.json SERVER_ID)'}")
    print(f"  version   : {_version()}")
    print(f"  templates : {len(_files(['templates/*.png']))} recordings, vision scales: "
          f"{'yes' if os.path.exists(os.path.join(BASE, 'vision_scales.json')) else 'not learned yet'}")
    try:
        import cv2, numpy, pyautogui, PIL  # noqa
        print("  python packages: OK")
    except Exception as e:
        print(f"  python packages: MISSING ({e}) -> pip install opencv-python numpy pyautogui pillow cryptography")


def _server_id():
    for p in ("local_config.json",):
        try:
            return json.load(open(os.path.join(BASE, p), encoding="utf-8-sig")).get("SERVER_ID")
        except Exception:
            pass
    return None


def _version():
    try:
        return json.load(open(os.path.join(BASE, "version.json"))).get("version")
    except Exception:
        return None


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("export", "import", "check"):
        print(__doc__)
    elif a[0] == "export":
        export("--secrets" in a)
    elif a[0] == "check":
        check()
    else:
        rest = [x for x in a[1:] if not x.startswith("--")]
        sid = a[a.index("--server-id") + 1] if "--server-id" in a else None
        rest = [x for x in rest if x != sid]
        do_import(rest[0], rest[1] if len(rest) > 1 else None, sid, "--fresh" in a)
