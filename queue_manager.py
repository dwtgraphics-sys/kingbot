# -*- coding: utf-8 -*-
"""
queue_manager (v197) - one place for everything the game's Queue Overview shows.

The Queue Overview is the side panel behind the three-line button at the top-left of the city:
    Unit Training (4 troop types) · Unit Healing · Building Queues 1/2 · Tech Research ·
    Alliance Donations · Material Production · (Armament Acquirement) · Scout Queues A/B/C
The bot opens it, expands folded sections, scrolls to the end and reads every row:
    name + state (idle / busy with seconds left / done) + counters (chances, capacity, producible).

scan()  -> the reading, also published as status["city"]["qm"] (timestamp + seconds left per row),
           so the dashboard can count down live.
run()   -> acts on it, by settings:
    train     idle troop row  -> tap the row (the game jumps to the building) -> train the chosen tier
    heal      wounded + idle  -> tap the row -> hospital -> HEAL with resources
    build     idle builder    -> the game's own building suggestion
    research  idle academy    -> research by focus
    donate    chances >= min  -> tap the row -> alliance technology -> donate with resources
    materials free slots      -> tap the row -> blacksmith -> queue the chosen materials
    scout     standing by     -> tap the row -> scout camp -> Explore
All of them: resources only, never gems, never INSTANT.
"""
import re, time, datetime

from common import log

SECTIONS = (                       # (key, words that start the header)
    ("train", ("unit training",)),
    ("heal", ("unit healing",)),
    ("build", ("building queues",)),
    ("research", ("tech research",)),
    ("donate", ("alliance donations", "alliance donation")),
    ("materials", ("material production",)),
    ("armament", ("armament acquirement", "armament")),
    ("scout", ("scout queues",)),
)
TROOP_UNITS = {
    "infantry": ("guard", "axeman", "swordsman", "pikeman", "spearman", "warrior", "legion", "infantry", "samurai",
                 "berserker", "huskarl", "hwarang", "jaguar", "immortal", "throwing", "hoplite", "longsword"),
    "archer": ("crossbow", "bowman", "archer", "longbow", "chu-ko", "chukonu", "yumi", "camel", "hwacha", "slinger",
               "amazon"),
    "cavalry": ("knight", "cavalry", "horse", "lancer", "mamluk", "conquistador", "cataphract", "rider", "keshik",
                "elephant", "bear", "teutonic"),
    "siege": ("catapult", "trebuchet", "ballista", "siege", "mangonel", "battering"),
}
UNIT_BUILDING = {"infantry": "barracks", "archer": "archery", "cavalry": "stable", "siege": "siege"}
DONE_WORDS = ("completed", "complete", "collect", "finished", "ready")
LAST = {"qm": None}


# ------------------------------------------------------------------ reading
def clean(t):
    """Drop what the OCR read from the round icons in front of the text ('©', 'Js)', '®)', '9)', 'A ')
    and the fold arrows behind headers."""
    toks = re.sub(r"\s+", " ", (t or "").strip()).split(" ")
    while toks and (len(toks[0]) == 1 or (len(toks[0]) <= 3 and re.search(r"[^\w]", toks[0]))
                    or not re.search(r"[A-Za-z0-9]", toks[0])):
        if len(toks) == 1:
            break
        toks.pop(0)
    out = " ".join(toks)
    return re.sub(r"\s+[^\w\s:/.]{1,3}\w{0,2}$", "", out).strip()


def norm(t):
    return re.sub(r"\s+", " ", clean(t).lower())


def secs(t):
    m = re.search(r"(?:(\d+)\s*d\D{0,3})?(\d{1,2})\s*[:.]\s*(\d{2})\s*[:.]\s*(\d{2})", t or "")
    if not m:
        m2 = re.search(r"\b(\d{1,2})\s*[:.]\s*(\d{2})\b", t or "")
        return int(m2.group(1)) * 60 + int(m2.group(2)) if m2 else None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def fraction(t, word):
    m = re.search(word + r"\D{0,4}([\d,.\s]+?)\s*/\s*([\d,.\s]+)", norm(t))
    if not m:                                   # the label itself was misread: take the first "a/b" of the card
        m = re.search(r"(\d[\d,.]*)\s*/\s*(\d[\d,.]*)", norm(t))
    if not m and word in ("producible", "chances"):  # small counters: "5,'5" / "20120" are "5/5" / "20/20"
        m = re.search(word + r"\D{0,4}(\d{1,2})\s*[,'’|]{1,3}\s*(\d{1,2})\b", norm(t))
    if not m:
        return None
    a, b = (int(re.sub(r"\D", "", x) or 0) for x in m.groups())
    return a, b


def section_of(text):
    t = norm(text)
    t = re.sub(r"(unit|building|tech|alliance|material|armament|scout)(?=[a-z])", r"\1 ", t)
    for key, words in SECTIONS:
        if any(t.startswith(w) for w in words):
            return key
    for key, words in SECTIONS:
        if any(w in t for w in words) and len(t) < 40 and not re.search(r"\d", t):
            return key
    return None


STATUS_RE = re.compile(r"\b(idle|[il1]?d[lti1]e|standing by|standing|training|healing|upgrading|researching|producing|exploring|returning|"
                       r"next chance|donate|completed?|ready|collect|travels with|remaining|chances|capacity|"
                       r"producible)\b|\d{1,2}\s*[:.]\s*\d{2}\s*[:.]\s*\d{2}")


def is_status(text):
    return bool(STATUS_RE.search(norm(text)))


def is_junk(text):
    t = clean(text)
    return not re.search(r"[A-Za-z]{3,}|\d{1,2}\s*[:.]\s*\d{2}|\d+\s*/\s*\d+", t)


def row_name(section, text):
    """The row title in a stable spelling, or None when this line is not a row title of that section."""
    t = clean(text)
    low = t.lower()
    if section == "build":
        m = re.search(r"bu?i?l?ding\s*queue\s*(\d)", low)
        if m:
            return f"Building Queue {m.group(1)}"
        if re.search(r"bu?i?l?ding\s*queue", low):
            return "Building Queue ?"                   # the number was not read - named by its place below
        return None
    if section == "scout":
        m = re.search(r"scout\s*([abc8])(?:\b|$)", low)
        if m:
            return f"Scout {'B' if m.group(1) == '8' else m.group(1).upper()}"
        return "Scout ?" if re.fullmatch(r"scout\W*", low) else None
    if section == "train":
        if not unit_of(t):
            return None
        m = re.search(r"[A-Z][A-Za-z'\-]+(?:\s+[A-Za-z'\-]+)*", t)
        return m.group(0) if m else t
    if section in ("research", "armament"):
        return t if re.search(r"[A-Za-z]{3,}", t) else None
    return None


def unit_of(name):
    t = norm(name)
    for unit, words in TROOP_UNITS.items():
        if any(w in t for w in words):
            return unit
    return None


def state_of(status):
    t = norm(status)
    m = STATUS_RE.search(t)
    if m:
        t = t[m.start():]
    s = secs(t)
    if any(w in t for w in DONE_WORDS):
        return "done", None
    if s is not None:
        return "busy", s
    if re.match(r"([il1]?d[lti1]e|standing)\b", t):
        return "idle", None
    if t.startswith("donate"):
        return "ready", None
    return "unknown", None


def parse_lines(lines, start_section=None):
    """lines = [(y, x, text)] of ONE panel picture. -> (rows, last section, headers)
    rows = [{section, name, status, y}]; lines before the first header inherit start_section
    (the panel was scrolled). Each status line belongs to the nearest row title above it."""
    rows, section, headers, single = [], start_section, [], {}
    for y, x, text in sorted(lines):
        if is_junk(text) or "queue overview" in norm(text):
            continue
        sec = section_of(text)
        if sec == "research" and section == "research" and headers and headers[-1][0] == "research":
            sec = None                                   # the row under the header is also called "Tech Research"
        if sec:
            section = sec
            headers.append((sec, y))
            continue
        if section is None:
            continue
        t = clean(text)
        if section in ("heal", "donate", "materials"):          # one card: collect every fact in it
            r = single.get(section)
            if r is None:
                r = single[section] = {"section": section, "name": section, "status": "", "y": y}
                rows.append(r)
            r["status"] = (r["status"] + " | " + t).strip(" |")
            continue
        name = row_name(section, t) if not (is_status(t) and section != "research") else None
        if section == "research" and is_status(t) and not re.search(r"tech research", t.lower()):
            name = None
        if name:
            rows.append({"section": section, "name": name, "status": "", "y": y})
            continue
        if is_status(t):
            owner = next((r for r in reversed(rows) if r["section"] == section and r["name"] not in
                          ("heal", "donate", "materials") and not r["status"]), None)
            if owner is not None:
                owner["status"] = t
    return rows, section, headers


def build(rows):
    """Merged rows -> the structured reading published to the dashboard."""
    now = time.time()
    qm = {"at": round(now), "read": datetime.datetime.now().strftime("%H:%M"),
          "train": [], "heal": None, "build": [], "research": [], "donate": None, "materials": None, "scout": []}
    seen = set()
    for sec, fmt_, letters in (("build", "Building Queue {}", "12"), ("scout", "Scout {}", "ABC")):
        known = [r["name"] for r in rows if r["section"] == sec]
        for r in rows:
            if r["section"] == sec and r["name"].endswith("?"):
                i = rows.index(r)
                prev = next((x["name"] for x in reversed(rows[:i]) if x["section"] == sec and not x["name"].endswith("?")), None)
                nxt = next((x["name"] for x in rows[i + 1:] if x["section"] == sec and not x["name"].endswith("?")), None)
                guess = None
                if prev and prev[-1] in letters and letters.index(prev[-1]) + 1 < len(letters):
                    guess = letters[letters.index(prev[-1]) + 1]
                elif nxt and nxt[-1] in letters and letters.index(nxt[-1]) > 0:
                    guess = letters[letters.index(nxt[-1]) - 1]
                elif not prev and not nxt:
                    guess = letters[0]
                if guess and fmt_.format(guess) not in known:
                    r["name"] = fmt_.format(guess)
                    known.append(r["name"])
    rows = [r for r in rows if not r["name"].endswith("?")]
    for r in rows:
        key = (r["section"], norm(r["name"]))
        if key in seen:
            continue
        seen.add(key)
        sec, status = r["section"], r["status"]
        if sec in ("heal", "materials"):
            parts = [p_ for p_ in status.split("|") if state_of(p_)[0] != "unknown"]
            st, left = state_of(parts[-1]) if parts else ("unknown", None)
        else:
            st, left = state_of(status)
        if sec == "train":
            qm["train"].append({"name": r["name"], "unit": unit_of(r["name"]), "state": st, "left": left})
        elif sec in ("build", "research", "scout"):
            qm[sec].append({"name": r["name"], "state": st, "left": left})
        elif sec == "heal":
            cap = fraction(status, "capacity")
            qm["heal"] = {"wounded": cap[0] if cap else None, "capacity": cap[1] if cap else None,
                          "state": st, "left": left}
        elif sec == "donate":
            ch = fraction(status, "chances")
            nxt = re.search(r"next chance in\s*(.+)", norm(status))
            qm["donate"] = {"chances": ch[0] if ch else None, "max": ch[1] if ch else None,
                            "next_in": secs(nxt.group(1)) if nxt else None,
                            "state": "ready" if "donate" in norm(status) else ("busy" if nxt else "unknown")}
        elif sec == "materials":
            pr = fraction(status, "producible")
            qm["materials"] = {"producible": pr[0] if pr else None, "max": pr[1] if pr else None,
                               "state": st, "left": left}
    return qm


# ------------------------------------------------------------------ the game
def panel_visible(img):
    """The open panel is a light-blue column at the left edge (independent of OCR and window size)."""
    import numpy as np
    h, w = img.shape[:2]
    def frac(x0, x1):
        reg = img[int(.15 * h):int(.85 * h), int(x0 * w):int(x1 * w)].astype(np.int16)
        b, g, r = reg[..., 0], reg[..., 1], reg[..., 2]
        return float(((b > 205) & (g > 200) & (r > 175) & (b >= r + 5)).mean())
    return frac(.012, .16) > 0.45 and frac(.21, .30) < 0.30


def ocr_panel(img):
    """OCR of the panel column only, enlarged so small windows read well -> [(y, x, text)] in pixels."""
    import smart
    h, w = img.shape[:2]
    x1 = int(0.19 * w)
    crop = img[:, :x1]
    scale = max(2.0, min(4.0, 560.0 / max(1, x1)))
    boxes = smart._ocr_boxes(crop, "qm_ocr.png", scale)
    return [((by1 + by2) / 2.0, bx1, t) for bx1, by1, bx2, by2, t in boxes]


def open_panel(g, sleep):
    """Open the Queue Overview. Returns the screenshot or None."""
    import smart
    img = g.screenshot()
    if panel_visible(img):
        return img
    boxes, img = smart.queue_panel(g, sleep)
    if img is not None:
        return img
    img = g.screenshot()                      # the title OCR can miss on a small window - trust the colour
    return img if panel_visible(img) else None


def close_panel(g, sleep):
    import smart
    img = g.screenshot()
    if panel_visible(img):
        h, w = img.shape[:2]
        g.click_rel(0.188, 0.500); sleep(1.2)    # the arrow on the panel's right edge
        if panel_visible(g.screenshot()):
            smart.press_key("esc"); sleep(1.0)


def _scroll(g, sleep, up=False):
    import smart
    a, b = (0.35, 0.75) if up else (0.75, 0.45)
    smart._drag(g, 0.085, a, 0.085, b)
    sleep(1.3)


def scan(g, sleep, publish=True):
    """Read the whole panel (expanding folded sections, scrolling to the end). -> qm dict or None."""
    img = open_panel(g, sleep)
    if img is None:
        log("  ! queue_manager: the Queue Overview did not open")
        return None
    h = img.shape[0]
    rows, section, expanded, prev_sig = [], None, set(), None
    dump = []
    for page in range(10):
        lines = ocr_panel(img)
        dump.append(f"--- page {page}: " + " || ".join(t for _y, _x, t in sorted(lines)))
        page_rows, end_section, headers = parse_lines(lines, section)
        # a folded section: its header is followed directly by the next header -> tap it open once
        folded = None
        for i, (sec, y) in enumerate(headers):
            nxt = headers[i + 1][1] if i + 1 < len(headers) else None
            has_rows = any(r["section"] == sec for r in page_rows)
            if sec in ("train", "heal", "build", "research", "donate", "materials", "scout") \
                    and sec not in expanded and not has_rows and nxt is not None and (nxt - y) < 0.075 * h:
                folded = (sec, y)
                break
        if folded:
            expanded.add(folded[0])
            g.click_rel(0.08, folded[1] / h); sleep(1.3)
            log(f"    queue_manager: opened the folded section '{folded[0]}'")
            img = g.screenshot()
            continue
        rows += page_rows
        section = end_section
        sig = "|".join(t for _y, _x, t in sorted(lines))
        if sig == prev_sig or any(r["section"] == "scout" and norm(r["name"]).endswith(" c") for r in page_rows):
            break
        prev_sig = sig
        _scroll(g, sleep)
        img = g.screenshot()
        if not panel_visible(img):
            break
    for _ in range(3):
        _scroll(g, sleep, up=True)            # leave the panel at the top for the next reader
    try:
        import os
        from common import BASE
        with open(os.path.join(BASE, "claude_out", "qm_lines.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(dump))
    except Exception:
        pass
    qm = build(rows)
    LAST["qm"] = qm
    n = len(qm["train"]) + len(qm["build"]) + len(qm["research"]) + len(qm["scout"]) + \
        sum(1 for k in ("heal", "donate", "materials") if qm[k])
    log(f"  queue_manager: {n} queue(s) read - " + summary(qm))
    if publish:
        try:
            import control
            control.CITY["qm"] = qm
            control.CITY["queues"] = legacy_list(qm)          # the old list some tasks still read
            control.CITY["queues_at"] = qm["read"]
            if qm["heal"] and qm["heal"].get("capacity"):
                control.CITY["hospital"] = f"{qm['heal']['wounded']:,}/{qm['heal']['capacity']:,}"
            if qm["donate"] and qm["donate"].get("max"):
                control.CITY["donations"] = f"{qm['donate']['chances']}/{qm['donate']['max']}"
        except Exception:
            pass
    return qm


def legacy_list(qm):
    out = []
    for k, rows in (("train", qm["train"]), ("build", qm["build"]), ("res", qm["research"])):
        for r in rows:
            if r["state"] == "busy":
                item = {"kind": k, "title": r["name"], "left": _fmt(r["left"]), "pct": 0}
            elif r["state"] == "done":
                item = {"kind": k, "title": r["name"], "done": True, "pct": 100}
            else:
                continue
            out.append(item)
    return out


def _fmt(s):
    if s is None:
        return ""
    h, r = divmod(int(s), 3600)
    return f"{h} h {r // 60} min" if h else f"{r // 60} min"


def summary(qm):
    parts = []
    idle_t = [r["unit"] or r["name"] for r in qm["train"] if r["state"] in ("idle", "done")]
    if qm["train"]:
        parts.append(f"training idle: {', '.join(idle_t) or 'none'}")
    if qm["heal"]:
        parts.append(f"hospital {qm['heal'].get('wounded')}/{qm['heal'].get('capacity')} {qm['heal']['state']}")
    if qm["build"]:
        parts.append("builders " + "/".join(r["state"] for r in qm["build"]))
    if qm["research"]:
        parts.append("research " + qm["research"][0]["state"])
    if qm["donate"]:
        parts.append(f"donations {qm['donate'].get('chances')}/{qm['donate'].get('max')}")
    if qm["materials"]:
        parts.append(f"materials {qm['materials'].get('producible')}/{qm['materials'].get('max')}")
    if qm["scout"]:
        parts.append("scouts " + "/".join(r["state"] for r in qm["scout"]))
    return ", ".join(parts) or "nothing readable"


def tap_row(g, sleep, section, words=None, match=None, prefer_idle=False):
    """Open the panel and tap the first row of `section` whose name contains one of `words`
    (scrolling when needed). The game then jumps to that building. True when tapped."""
    img = open_panel(g, sleep)
    if img is None:
        return False
    h = img.shape[0]
    cur = None
    for page in range(6):
        lines = ocr_panel(img)
        rows, cur, headers = parse_lines(lines, cur)
        for r in rows:
            if r["section"] != section:
                continue
            if words and not any(w in norm(r["name"]) for w in words):
                continue
            if match and not match(r):
                continue
            if prefer_idle and state_of(r["status"])[0] == "busy":
                continue
            g.click_rel(0.08, r["y"] / h); sleep(3)
            log(f"    queue_manager: tapped '{r['name']}' ({section})")
            if panel_visible(g.screenshot()):          # some rows leave the panel open
                close_panel(g, sleep)
            return True
        _scroll(g, sleep)
        img = g.screenshot()
        if not panel_visible(img):
            break
    close_panel(g, sleep)
    return False


# ------------------------------------------------------------------ acting
def run(g, sleep, train=True, heal=True, build=True, research=True, donate=True, materials=True, scout=False,
        donate_min=10, mat_kinds=("leather", "ore", "ebony", "bone"),
        inf_tier="4", arch_tier="4", cav_tier="4", siege_tier="4", fast=False, use_bag=False,
        heal_speedups=False, build_mode="smart", build_speedups=False, focus="balanced", research_speedups=False,
        **_ignored):
    """The single Queue Overview task. Reads the panel, then does only what is needed."""
    import smart
    qm = LAST["qm"]
    if not qm or time.time() - qm.get("at", 0) > 120:      # the round start just read it - no second scan
        qm = scan(g, sleep)
    if qm is None:
        return "retry"
    did = []
    if train:
        need = [r for r in qm["train"] if r["state"] in ("idle", "done") and r["unit"]]
        if not qm["train"]:
            log("  - queue_manager: no Unit Training rows were read - training is checked next time")
        if need:
            buildings = [UNIT_BUILDING[r["unit"]] for r in need]
            smart.train_troops(g, sleep, fast=fast, use_bag=use_bag, buildings=buildings,
                               inf_tier=inf_tier, arch_tier=arch_tier, cav_tier=cav_tier, siege_tier=siege_tier)
            did.append("train " + ",".join(buildings))
        elif fast and any(r["state"] == "busy" for r in qm["train"]):
            pass
    h = qm["heal"]
    if heal and h and (h.get("wounded") is None or h["wounded"] > 0) and h["state"] in ("idle", "done", "unknown"):
        smart.heal(g, sleep, speedups=heal_speedups)
        did.append("heal")
    if build and qm["build"] and any(r["state"] in ("idle", "done") for r in qm["build"]):
        smart.build_upgrade(g, sleep, mode=build_mode, speedups=build_speedups)
        did.append("build")
    if research and qm["research"] and qm["research"][0]["state"] in ("idle", "done"):
        smart.research(g, sleep, focus=focus, speedups=research_speedups)
        did.append("research")
    d = qm["donate"]
    if donate and d and d.get("chances") is not None and d["chances"] >= int(donate_min or 1):
        smart.alliance_tech(g, sleep, max_donations=d["chances"])
        did.append(f"donate ({d['chances']})")
    m = qm["materials"]
    if materials and m and (m.get("producible") or 0) > 0 and m["state"] in ("idle", "done", "busy", "unknown"):
        smart.materials(g, sleep, kinds=tuple(mat_kinds or ()))
        did.append("materials")
    if scout:
        idle = [r for r in qm["scout"] if r["state"] in ("idle", "done")]
        for r in idle[:3]:
            if not send_scout(g, sleep, r["name"]):
                break
            did.append("scout " + r["name"][-1:])
    log("  queue_manager: " + (", ".join(did) if did else "nothing to do - every queue is busy or switched off"))
    if did:
        try:
            scan(g, sleep)                       # fresh timers for the dashboard
        except Exception:
            pass
    smart.recover_screen(g)
    return True


def send_scout(g, sleep, name):
    """Scout row -> the game selects the scout camp -> Explore -> Explore (send). False when not possible."""
    import smart
    if not tap_row(g, sleep, "scout", [norm(name)]):
        return False
    for _ in range(2):
        img = g.screenshot()
        hit = None
        for x1, y1, x2, y2, t in smart._ocr_boxes(img, "qm_scout.png", 1.6):
            if norm(t) in ("explore", "send", "scout"):
                h, w = img.shape[:2]
                hit = ((x1 + x2) / 2 / w, (y1 + y2) / 2 / h)
                break
        if not hit:
            break
        g.click_rel(*hit); sleep(2.5)
    smart._save_failure(g, "scout_after", note="after the scout Explore buttons")
    from common import close_gem_dialogs
    close_gem_dialogs(g)
    smart.recover_screen(g)
    return True
