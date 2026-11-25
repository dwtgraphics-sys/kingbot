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
                   "3_start_bot.bat"}   # the launcher lives on this PC; keep an update zip from replacing it
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
    # keep the running version so it can be restored by hand: backup_v<old>\
    old = local_version()
    bak = os.path.join(BASE, f"backup_v{old}")
    os.makedirs(bak, exist_ok=True)
    for rel in files:
        src = os.path.join(BASE, rel)
        if os.path.isfile(src) and rel.endswith((".py", ".bat", ".vbs", ".ps1", ".json")):
            dst = os.path.join(bak, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(src, "rb") as a, open(dst, "wb") as b2:
                b2.write(a.read())
    for rel, b in files.items():
        if rel == "tasks.json":
            _merge_tasks(b)
            continue
        if rel in NEVER_OVERWRITE:
            continue
        dest = os.path.join(BASE, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(b)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"version": ver}, f)
    log(f"Updated to v{ver} from GitHub ({sha[:7]}); previous files kept in backup_v{old}. Restarting ...")
    return True


def check_and_update(log=print):
    """Return True if a new version was installed (caller should restart)."""
    cur = local_version()
    try:                                                     # v190: GitHub first
        gver, sha = github_latest(log)
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
