# -*- coding: utf-8 -*-
"""
Auto-update. First choice: the GitHub repository dwtgraphics-sys/kingbot (branch main) - a new version is
installed only when version.json there is higher AND the repository's checks (GitHub Actions) passed.
Fallback: the shared Google Drive folder "RisBot_updates".
Looks for files named Kingbot_vN.zip (or older RisBot_vN.zip) and installs the highest N if it is newer.
Your recordings (routines.json, templates/), tasks.json and log.txt are never overwritten.
"""
import io, os, re, json, zipfile, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
FOLDER_ID = "1CS-oG5Zi7iXeHtYO2RbKHkUgctOMJbNe"
LIST_URL = f"https://drive.google.com/embeddedfolderview?id={FOLDER_ID}"
DL_URL = "https://drive.google.com/uc?export=download&id={}"
VERSION_FILE = os.path.join(BASE, "version.json")
NEVER_OVERWRITE = {"routines.json", "tasks.json", "log.txt", "version.json", "telegram.txt", "telegram_owner.txt",
                   "3_start_bot.bat", "local_config.json", ".env", "github_token.txt", "vision_scales.json",
                   "signed_out.json", "signout_sched.json", "brain.json"}
# ADM-02: server-specific runtime folders/prefixes an update never touches (config, state, logs, slot assignments)
RUNTIME_PREFIX = ("config/", "state/", "logs/", "slots/", "templates/", "claude_out/", "migrate/", "backup_v",
                  "stream_chrome/", "roadmap/")
UPDATE_LOG = os.path.join(BASE, "update_history.json")
PIN_FILE = os.path.join(BASE, "update_pin.json")
KEEP_BACKUPS = 6   # the launcher lives on this PC; keep an update zip from replacing it
UA = {"User-Agent": "Mozilla/5.0 Kingbot"}

# ---- GitHub source (v190) ----
GH_OWNER, GH_REPO, GH_BRANCH = "dwtgraphics-sys", "kingbot", "main"
TOKEN_FILE = os.path.join(BASE, "github_token.txt")
# repository files that must never land on the bot (docs, CI, the dashboard deployer is fine to update)
GH_SKIP_PREFIX = (".github/", ".git", "README", "templates/")


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def local_version():
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return int(json.load(f).get("version", 0))
    except Exception:
        return 0


def local_folder():
    """Find RisBot_updates synced by Google Drive for desktop (e.g. G:\\My Drive\\Ris bot\\RisBot_updates)."""
    import glob, string
    for letter in string.ascii_uppercase[3:]:
        for pat in (rf"{letter}:\*\Ris bot\RisBot_updates", rf"{letter}:\*\*\Ris bot\RisBot_updates",
                    rf"{letter}:\*\RisBot_updates"):
            for p in glob.glob(pat):
                if os.path.isdir(p):
                    return p
    return None


def latest_local():
    folder = local_folder()
    best = (0, None)
    if not folder:
        return best
    for name in os.listdir(folder):
        m = re.match(r"(?:Kingbot|RisBot)_v(\d+)\.zip$", name, re.I)
        if m and int(m.group(1)) > best[0]:
            best = (int(m.group(1)), os.path.join(folder, name))
    return best


def latest_remote():
    html = _get(LIST_URL).decode("utf-8", "ignore")
    best = (0, None)
    for fid, title in re.findall(r'entry-([\w-]{20,})".*?flip-entry-title">([^<]+)<', html, re.S):
        m = re.match(r"(?:Kingbot|RisBot)_v(\d+)\.zip$", title.strip(), re.I)
        if m and int(m.group(1)) > best[0]:
            best = (int(m.group(1)), fid)
    return best


def _merge_tasks(new_tasks_bytes):
    """Add tasks that exist in the update but not in the local tasks.json (disabled)."""
    path = os.path.join(BASE, "tasks.json")
    try:
        new = json.loads(new_tasks_bytes.decode("utf-8-sig"))
    except Exception:
        return
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, indent=2)
        return
    with open(path, encoding="utf-8") as f:
        cur = json.load(f)
    have = {t.get("routine") for t in cur.get("tasks", [])}
    added = False
    for t in new.get("tasks", []):
        if t.get("routine") not in have:
            t = dict(t, enabled=False)
            cur.setdefault("tasks", []).append(t)
            added = True
    if added:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)


def _gh_token():
    try:
        return open(TOKEN_FILE, encoding="utf-8").read().strip()
    except Exception:
        return os.environ.get("KINGBOT_GH_TOKEN", "").strip()


def _gh(url, raw=False):
    h = dict(UA, Accept="application/vnd.github+json")
    tok = _gh_token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code != 401 or "Authorization" not in h:
            raise
        h.pop("Authorization")      # public repo: retry without the refused token
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
            data = r.read()
    return data if raw else json.loads(data.decode("utf-8"))


def github_latest(log=print):
    """(version, sha) of the newest commit on main whose checks passed; (0, None) if none / not reachable."""
    api = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}"
    head = _gh(f"{api}/commits/{GH_BRANCH}")
    sha = head["sha"]
    import base64
    vj = _gh(f"{api}/contents/version.json?ref={sha}")
    ver = int(json.loads(base64.b64decode(vj["content"]).decode("utf-8")).get("version", 0))
    runs = _gh(f"{api}/commits/{sha}/check-runs").get("check_runs", [])
    if not runs:
        log(f"GitHub v{ver}: checks have not started yet - waiting")
        return 0, None
    if any(r.get("status") != "completed" for r in runs):
        log(f"GitHub v{ver}: checks still running - waiting")
        return 0, None
    bad = [r.get("name") for r in runs if r.get("conclusion") not in ("success", "skipped", "neutral")]
    if bad:
        log(f"GitHub v{ver}: checks FAILED ({', '.join(bad)}) - this version is NOT installed")
        return 0, None
    return ver, sha


def _install_github(ver, sha, log=print):
    data = _gh(f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/zipball/{sha}", raw=True)
    if not data.startswith(b"PK"):
        log("GitHub download was not a zip")
        return False
    z = zipfile.ZipFile(io.BytesIO(data))
    files = {}
    for info in z.infolist():
        if info.is_dir():
            continue
        rel = info.filename.split("/", 1)[1] if "/" in info.filename else info.filename
        if not rel or rel.startswith(GH_SKIP_PREFIX):
            continue
        files[rel] = z.read(info)
    # never install code that does not even compile
    for rel, b in files.items():
        if rel.endswith(".py"):
            try:
                compile(b.decode("utf-8-sig"), rel, "exec")
            except Exception as e:
                log(f"GitHub v{ver}: {rel} does not compile ({e}) - NOT installed")
                return False
    return install_files(ver, files, log, source=f"GitHub {sha[:7]}")


def install_files(ver, files, log=print, source="bundle"):
    """ADM-02: install a set of code files {rel: bytes}. Before: a full backup of every file that will change
    (+ a manifest of files that did not exist, so a rollback removes them). Never touches runtime files."""
    import time as _t, shutil
    files = {r: b for r, b in files.items() if r not in NEVER_OVERWRITE or r == "tasks.json"}
    files = {r: b for r, b in files.items() if not r.startswith(RUNTIME_PREFIX) and not r.startswith(GH_SKIP_PREFIX)}
    old = local_version()
    bak = os.path.join(BASE, f"backup_v{old}")
    os.makedirs(bak, exist_ok=True)
    new_files = []
    for rel in files:
        src = os.path.join(BASE, rel)
        if os.path.isfile(src):
            dst = os.path.join(bak, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        elif rel != "tasks.json":
            new_files.append(rel)
    with open(os.path.join(bak, "_backup.json"), "w", encoding="utf-8") as f:
        json.dump({"version": old, "replaced_by": ver, "at": _t.strftime("%Y-%m-%d %H:%M:%S"), "source": source,
                   "new_files": new_files}, f, indent=1)
    for rel, b in files.items():
        if rel == "tasks.json":
            _merge_tasks(b)
            continue
        dest = os.path.join(BASE, rel)
        os.makedirs(os.path.dirname(dest) or BASE, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(b)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"version": ver}, f)
    _history({"from": old, "to": ver, "source": source, "files": len(files), "kind": "update"})
    _prune_backups(log)
    log(f"Updated to v{ver} from {source}; previous files kept in backup_v{old}. Restarting ...")
    return True


def _history(item):
    import time as _t
    try:
        h = json.load(open(UPDATE_LOG, encoding="utf-8"))
    except Exception:
        h = []
    item["at"] = _t.strftime("%Y-%m-%d %H:%M:%S")
    h = (h + [item])[-30:]
    with open(UPDATE_LOG, "w", encoding="utf-8") as f:
        json.dump(h, f, indent=1)


def backups():
    out = []
    for d in os.listdir(BASE):
        m = re.match(r"backup_v(\d+)$", d)
        if m and os.path.isdir(os.path.join(BASE, d)):
            out.append(int(m.group(1)))
    return sorted(out)


def _prune_backups(log=print):
    import shutil
    b = backups()
    for v in b[:-KEEP_BACKUPS]:
        try:
            shutil.rmtree(os.path.join(BASE, f"backup_v{v}"))
        except Exception as e:
            log(f"  could not remove backup_v{v}: {e}")


def pinned():
    """{'max': N, 'since': ...} while updates are held after a rollback, else None."""
    try:
        return json.load(open(PIN_FILE, encoding="utf-8"))
    except Exception:
        return None


def unpin():
    try:
        os.remove(PIN_FILE)
    except Exception:
        pass


def rollback(target=None, log=print):
    """ADM-02: go back to backup_v<target> (default: the newest backup older than the running version).
    Restores every backed-up file, removes the files the newer version added, and holds updates at that
    version until the dashboard releases them (unpin). Returns the version restored, or None."""
    import time as _t, shutil
    cur = local_version()
    cands = [v for v in backups() if v < cur]
    if target is not None:
        cands = [v for v in cands if v == int(target)]
    if not cands:
        log("  rollback: no older backup on this server")
        return None
    v = max(cands)
    bak = os.path.join(BASE, f"backup_v{v}")
    meta = {}
    try:
        meta = json.load(open(os.path.join(bak, "_backup.json"), encoding="utf-8"))
    except Exception:
        pass
    n = 0
    for root, _d, fs in os.walk(bak):
        for fn in fs:
            if fn == "_backup.json":
                continue
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, bak)
            dst = os.path.join(BASE, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    for rel in meta.get("new_files", []):
        try:
            os.remove(os.path.join(BASE, rel))
        except Exception:
            pass
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"version": v}, f)
    with open(PIN_FILE, "w", encoding="utf-8") as f:
        json.dump({"max": v, "since": _t.strftime("%Y-%m-%d %H:%M:%S"), "from": cur}, f)
    _history({"from": cur, "to": v, "source": f"backup_v{v}", "files": n, "kind": "rollback"})
    log(f"Rolled back v{cur} -> v{v} ({n} files). Updates are held at v{v} until released from the dashboard.")
    return v


def update_info():
    """Shown in status.json -> 'update'."""
    try:
        h = json.load(open(UPDATE_LOG, encoding="utf-8"))
    except Exception:
        h = []
    return {"version": local_version(), "pinned": pinned(), "backups": backups()[-KEEP_BACKUPS:], "history": h[-5:]}


def install_bundle(path, log=print):
    """ADM-02: install a portable bundle made by tools/make_bundle.py (Kingbot_bundle_vN.zip)."""
    z = zipfile.ZipFile(path)
    meta = json.loads(z.read("BUNDLE.json"))
    files = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir() and i.filename != "BUNDLE.json"}
    for rel, b in files.items():
        if rel.endswith(".py"):
            compile(b.decode("utf-8-sig"), rel, "exec")
    return install_files(int(meta["version"]), files, log, source=f"bundle {os.path.basename(path)}")


def check_and_update(log=print):
    """Return True if a new version was installed (caller should restart)."""
    cur = local_version()
    try:                                                     # v190: GitHub first
        gver, sha = github_latest(log)
        pin = pinned()
        if sha and pin and gver > int(pin.get("max", cur)):
            log(f"Updates held at v{pin.get('max')} after a rollback (GitHub v{gver}) - release them from the dashboard.")
            return False
        if sha and gver > cur:
            log(f"Installing update v{gver} from GitHub ...")
            return _install_github(gver, sha, log)
        if sha:
            log(f"Bot is up to date (v{cur}, GitHub v{gver}).")
            return False
    except Exception as e:
        log(f"GitHub update check failed ({e}) - trying Google Drive")
    ver, src, where = 0, None, ""
    try:
        ver, src = latest_local()
        where = "Google Drive folder on this PC"
    except Exception as e:
        log(f"Local update folder error: {e}")
    if not src:
        try:
            ver, src = latest_remote()
            where = "Google Drive link"
        except Exception as e:
            log(f"Update check failed: {e}")
            return False
    if not src or ver <= cur:
        log(f"Bot is up to date (v{cur}).")
        return False
    log(f"Installing update v{ver} from {where} ...")
    try:
        if os.path.isfile(str(src)):
            with open(src, "rb") as f:
                data = f.read()
        else:
            data = _get(DL_URL.format(src))
        if not data.startswith(b"PK"):
            log("Update download was not a zip (is the Drive folder shared 'Anyone with the link'?)")
            return False
        z = zipfile.ZipFile(io.BytesIO(data))
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = info.filename.split("/", 1)
            rel = parts[1] if len(parts) == 2 and parts[0] in ("Kingbot", "RisBot") else info.filename
            if not rel or rel.startswith("templates/"):
                continue
            if rel == "tasks.json":
                _merge_tasks(z.read(info))
                continue
            if rel in NEVER_OVERWRITE:
                continue
            dest = os.path.join(BASE, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(z.read(info))
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"version": ver}, f)
        log(f"Updated to v{ver}. Restarting ...")
        return True
    except Exception as e:
        log(f"Update failed: {e}")
        return False


if __name__ == "__main__":
    print("Updated" if check_and_update() else "No update")


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    if a[:1] == ["--install-bundle"] and len(a) > 1:
        install_bundle(a[1])
    elif a[:1] == ["--rollback"]:
        rollback(a[1] if len(a) > 1 else None)
    elif a[:1] == ["--unpin"]:
        unpin(); print("updates released")
    else:
        print(json.dumps(update_info(), indent=1))
