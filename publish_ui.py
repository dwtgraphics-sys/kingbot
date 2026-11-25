# -*- coding: utf-8 -*-
import os, sys, time, json, base64, urllib.request, urllib.error

GITHUB_OWNER = "dwtgraphics-sys"
GITHUB_REPO = "kingbot-ui"
HTML_PATH = r"C:\Users\Administrator\Desktop\index.html"
TOKEN_FILE = r"C:\RisBot\github_token.txt"

def get_token():
    if os.path.isfile(TOKEN_FILE):
        return open(TOKEN_FILE, "r", encoding="utf-8").read().strip()
    return os.environ.get("KINGBOT_GH_TOKEN", "").strip()

def gh_req(path, method="GET", payload=None):
    token = get_token()
    if not token:
        raise RuntimeError("Missing GitHub token in C:\\RisBot\\github_token.txt")
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    if method == "GET":
        url += f"?t={int(time.time())}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Kingbot-UI-Deployer"
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404 and method == "GET":
            return None
        raise

MIN_BYTES = 100_000          # the dashboard is ~1.8 MB; anything this small is a half-saved or empty file


def read_complete():
    """Wait until the file stops changing, then check it is a whole page. Returns bytes or None."""
    last = None
    for _ in range(10):
        st = os.stat(HTML_PATH)
        if last == (st.st_size, st.st_mtime):
            break
        last = (st.st_size, st.st_mtime)
        time.sleep(2)
    raw = open(HTML_PATH, "rb").read()
    tail = raw[-200:].lower()
    if len(raw) < MIN_BYTES or b"</html>" not in tail:
        print(f"! Not deployed: index.html looks incomplete ({len(raw)} bytes) - waiting for a full save")
        return None
    return raw


def deploy_once():
    if not os.path.isfile(HTML_PATH):
        print("! File not found:", HTML_PATH)
        return False
    raw = read_complete()
    if raw is None:
        return False
    existing = gh_req("index.html", "GET")
    sha = existing.get("sha") if isinstance(existing, dict) else None
    body = {
        "message": f"auto-deploy: update index.html ({time.strftime('%Y-%m-%d %H:%M:%S')})",
        "content": base64.b64encode(raw).decode("ascii")
    }
    if sha:
        body["sha"] = sha
    gh_req("index.html", "PUT", body)
    print(f"[OK] Deployed index.html ({len(raw)} bytes) to {GITHUB_OWNER}/{GITHUB_REPO}")
    return True

if __name__ == "__main__":
    if "--watch" in sys.argv:
        print("Watching index.html for changes... (Ctrl+C to stop)")
        last_mtime = 0
        while True:
            try:
                mt = os.path.getmtime(HTML_PATH)
                if mt != last_mtime:
                    last_mtime = mt
                    deploy_once()
            except Exception as e:
                print("! Deploy error:", e)
            time.sleep(2)
    else:
        deploy_once()
