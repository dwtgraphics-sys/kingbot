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
                "elephant", "bear", "teutonic", "knig", "kmg", "kngt", "kight"),
    "siege": ("catapult", "trebuchet", "ballista", "siege", "mangonel", "battering"),
}
UNIT_BUILDING = {"infantry": "barracks", "archer": "archery", "cavalry": "stable", "siege": "siege"}
DONE_WORDS = ("completed", "complete", "collect", "finished", "ready", "healed")
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


STATUS_RE = re.compile(r"\b(idle|troop healed|healed|[il1]?d[lti1]e|standing by|standing|training|healing|upgrading|researching|producing|exploring|returning|"
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
    for _ in range(3):                        # always read from the top (a scrolled panel hides Unit Training)
        _scroll(g, sleep, up=True)
    img = g.screenshot()
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
            fold = header_folded(img, y)
            if sec in ("train", "heal", "build", "research", "donate", "materials", "scout") \
                    and sec not in expanded and not has_rows and fold is not False \
                    and (fold is True or (nxt is not None and (nxt - y) < 0.075 * h)):
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


def header_folded(img, y):
    """v237: a section header's chevron: '^' = open, 'v' = folded (measured on the live panel 26-11).
    Returns True (folded), False (open) or None (not readable)."""
    import cv2
    import numpy as np
    h, w = img.shape[:2]
    k = w / 946.0
    y = int(y)
    c = img[max(0, y - int(8 * k)):y + int(8 * k), int(0.146 * w):int(0.171 * w)]
    if c.size == 0:
        return None
    gr = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(int)
    ys, xs = np.nonzero(gr < gr.mean() - 25)
    if len(ys) < 8:
        return None
    top = xs[ys <= ys.min() + 2]
    bot = xs[ys >= ys.max() - 2]
    t, b = top.max() - top.min(), bot.max() - bot.min()
    if abs(t - b) < 3:
        return None
    return bool(t > b)


def tap_row(g, sleep, section, words=None, match=None, prefer_idle=False):
    """Open the panel and tap the first row of `section` whose name contains one of `words`
    (scrolling when needed). The game then jumps to that building. True when tapped."""
    img = open_panel(g, sleep)
    if img is None:
        return False
    for _ in range(3):
        _scroll(g, sleep, up=True)
    img = g.screenshot()
    h = img.shape[0]
    cur = None
    opened = False
    for page in range(6):
        lines = ocr_panel(img)
        start = cur
        rows, cur, headers = parse_lines(lines, cur)
        if not opened and not any(r["section"] == section for r in rows):   # v236: the section is folded - open it
            for i, (sec, y) in enumerate(headers):
                nxt = headers[i + 1][1] if i + 1 < len(headers) else None
                fold = header_folded(img, y)
                if sec == section and fold is not False and \
                        (fold is True or (nxt is not None and (nxt - y) < 0.075 * h)):
                    opened = True
                    g.click_rel(0.08, y / h); sleep(1.3)
                    log(f"    queue_manager: opened the folded section '{section}' to tap its row")
                    img = g.screenshot()
                    rows, cur, headers = parse_lines(ocr_panel(img), start)
                    break
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
            # the panel stays open; the selected building and its buttons are in the middle of the picture
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
        tiers = {"infantry": inf_tier, "archer": arch_tier, "cavalry": cav_tier, "siege": siege_tier}
        for r in need:
            if train_unit(g, sleep, r["unit"], tiers.get(r["unit"], 4)):
                did.append("train " + r["unit"])
    h = qm["heal"]
    if heal and h and h["state"] == "done":               # "Troop Healed - Completed": tapping it collects them
        if tap_row(g, sleep, "heal"):
            did.append("healed troops collected")
            smart.recover_screen(g)
    elif heal and h and (h.get("wounded") is None or h["wounded"] > 0) and h["state"] in ("idle", "unknown"):
        if heal_now(g, sleep):
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
    if materials and m and (m.get("producible") or 0) > 0:
        n = produce_materials(g, sleep, kinds=tuple(mat_kinds or ()), slots=m.get("producible") or 1)
        if n:
            did.append(f"materials {n}")
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


def hex_buttons(g, img=None):
    """v206: the light-blue hexagon buttons under a selected building (left to right) -> [(x, y)] relative.
    Measured on the owner's screenshot of the Scout Camp (26-11): Info on the left, Explore (telescope) on the right."""
    import cv2
    img = g.screenshot() if img is None else img
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (85, 10, 200), (105, 120, 255))
    m[:int(0.55 * h)] = 0
    m[:, :int(0.2 * w)] = 0
    m[:, int(0.8 * w):] = 0
    n, _l, st, _c = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if a > (0.02 * w) ** 2 and 0.04 * w < bw < 0.15 * w and 0.5 < bh / max(1, bw) * w / h < 4:
            out.append(((x + bw / 2) / w, (y + bh / 2) / h))
    return sorted(out)


def _scout_camp_by_row(g, sleep):
    """Scout row in the Queue Overview -> the game jumps to the Scout Camp -> the Explore (telescope) button."""
    if not tap_row(g, sleep, "scout", prefer_idle=True):
        return None
    sleep(1.5)
    img = g.screenshot()
    btns = hex_buttons(g, img)
    if len(btns) >= 2:
        return btns[-1]
    spot = glowing_button(g, img)
    return spot


def send_scout(g, sleep, name):
    """Idle scout -> Scout Camp -> its glowing button (Explore) -> the window's Explore/Send button.
    The Queue Overview rows of idle scouts do not move the camera (tested 25-11), so the camp is found by name."""
    import smart
    from common import close_gem_dialogs
    spot = None
    try:
        spot = _scout_camp_by_row(g, sleep)                  # v206: the queue row takes the game to the camp
    except Exception as e:
        log(f"    ! scout: queue row: {e!r}")
    if spot:
        g.click_rel(*spot); sleep(2.5)
        log("    scout: Scout Camp reached from the queue row - Explore pressed")
        return _scout_send_window(g, sleep, name)
    smart.recover_screen(g)
    pt = smart.find_building(g, sleep, "scout_camp")
    if not pt:
        log("    ! scout: the Scout Camp was not found in this city")
        smart.recover_screen(g)
        return False
    g.click_rel(*pt); sleep(2)
    btns = hex_buttons(g)
    spot = btns[-1] if len(btns) >= 2 else glowing_button(g)
    if not spot:
        log("    ! scout: no Explore button under the Scout Camp")
        smart._save_failure(g, "scout_camp", note="no glowing button under the camp")
        smart.recover_screen(g)
        return False
    g.click_rel(*spot); sleep(2.5)
    return _scout_send_window(g, sleep, name)


def _scout_send_window(g, sleep, name):
    import smart
    from common import close_gem_dialogs
    sent = False
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
        sent = True
    close_gem_dialogs(g)
    if not sent:
        smart._save_failure(g, "scout_after", note="no Explore / Send button found")
    log(f"  scout: {name} " + ("sent to explore" if sent else "NOT sent (button not found)"))
    smart.recover_screen(g)
    return sent

# ------------------------------------------------------------------ v201: the route the game itself offers
# Tapping a row in the Queue Overview moves the camera to that building and selects it; the action the row is
# about (Train / Heal / Material Production) is the GLOWING round button under the building. Positions below are
# pixel offsets from the centre of the game picture, measured on the live game (25-11, window 941 wide); the
# game's UI scales with the window width.
def rel(g, dx, dy, img=None):
    if img is not None:
        h, w = img.shape[:2]
    else:
        w, h = g.w, g.h
    k = w / 941.0
    return 0.5 + dx * k / w, 0.5 + dy * k / h


BTN_DX = (-59, -33, 0, 35, 58, 103)      # round buttons under a selected building
BTN_DY = 59


def glowing_button(g, img=None):
    """The highlighted (orange ring) round button under the selected building -> (x, y) relative, or None."""
    import cv2
    img = g.screenshot() if img is None else img
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    ring = cv2.inRange(hsv, (8, 110, 190), (34, 255, 255))
    best, score = None, 0.0
    k = w / 941.0
    r = int(34 * k)
    for dx in BTN_DX:
        x, y = rel(g, dx, BTN_DY, img)
        cx, cy = int(x * w), int(y * h)
        box = ring[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
        if box.size == 0:
            continue
        sc = float(box.mean()) / 255.0
        if sc > score:
            best, score = (x, y), sc
    return best if score > 0.06 else None


def press_row_action(g, sleep, section, match=None, words=None):
    """Queue Overview row -> the building -> its glowing action button. True when a window opened."""
    if not tap_row(g, sleep, section, words=words, match=match):
        return False
    sleep(1.0)
    img = g.screenshot()
    spot = glowing_button(g, img) or rel(g, 35, BTN_DY, img)
    g.click_rel(*spot)
    sleep(2.5)
    return True


def window_title(g, img=None):
    """Text of the title bar of an open game window ('ARCHER TRAINING', 'UNIT HEALING', 'MATERIAL PRODUCTION')."""
    import smart
    img = g.screenshot() if img is None else img
    h, w = img.shape[:2]
    x0, y0 = rel(g, -170, -155, img)
    x1, y1 = rel(g, 170, -125, img)
    crop = img[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
    return " ".join(smart._ocr_lines(crop, "qm_title.png", scale=2.5)).lower()


def window_open(g, words, img=None):
    """A game window is open: its title has one of `words`, or (title unreadable) the city behind it is dimmed."""
    import numpy as np
    img = g.screenshot() if img is None else img
    t = window_title(g, img)
    if any(w_ in t for w_ in words):
        return True
    if t.strip():
        return False
    h, w = img.shape[:2]
    corners = [img[int(.80 * h):int(.95 * h), int(.02 * w):int(.12 * w)], img[int(.80 * h):int(.95 * h), int(.88 * w):int(.98 * w)]]
    dark = float(np.mean([c.mean() for c in corners]))
    return dark < 45


def close_window(g, sleep):
    g.click_rel(*rel(g, 231, -142)); sleep(1.5)


TIER_DX = {1: -6, 2: 46, 3: 98, 4: 150, 5: 200}


def train_unit(g, sleep, unit, tier=4):
    """Unit Training row (infantry / archer / cavalry / siege) -> Train -> tier -> TRAIN (never INSTANT)."""
    from common import close_gem_dialogs
    import smart
    for attempt in range(2):                 # the first tap after the camera moved is sometimes swallowed
        if not press_row_action(g, sleep, "train", match=lambda r: unit_of(r["name"]) == unit):
            log(f"    train: the {unit} row was not found")
            return False
        if window_open(g, ("training", "train")):
            break
        log(f"    ! train: {unit}: the training window did not open (title '{window_title(g)[:40]}')"
            + (" - trying once more" if attempt == 0 else ""))
        smart.recover_screen(g)
    else:
        return False
    try:
        tier = max(1, min(5, int(tier)))
    except Exception:
        tier = 4
    g.click_rel(*rel(g, TIER_DX[tier], -94)); sleep(1.5)
    g.click_rel(*rel(g, 175, 118)); sleep(3)               # TRAIN (the blue button on the right)
    if close_gem_dialogs(g):
        log(f"    ! train: {unit}: the game asked for gems - answered NO")
        close_window(g, sleep)
        return False
    t2 = window_title(g)
    if "training" in t2:
        log(f"    ! train: {unit}: the window is still open (not enough resources?) - closing")
        close_window(g, sleep)
        return False
    log(f"  train: {unit} tier {tier} started")
    return True


def heal_now(g, sleep):
    """Unit Healing row -> hospital -> Heal -> HEAL with resources (never INSTANT)."""
    from common import close_gem_dialogs
    if not press_row_action(g, sleep, "heal"):
        return False
    if not window_open(g, ("heal",)):
        log(f"    ! heal: the healing window did not open (title '{window_title(g)[:40]}')")
        import smart
        smart.recover_screen(g)
        return False
    g.click_rel(*rel(g, 159, 113)); sleep(3)               # HEAL (blue, right)
    if close_gem_dialogs(g):
        log("    ! heal: the game asked for gems - answered NO")
        close_window(g, sleep)
        return False
    if "heal" in window_title(g):
        log("    - heal: nothing to heal or not enough resources - closing")
        close_window(g, sleep)
        return False
    log("  heal: healing started with resources")
    return True


MAT_DX = {"leather": 64, "ore": 111, "ebony": 158, "bone": 205}


def produce_materials(g, sleep, kinds=("leather", "ore", "ebony", "bone"), slots=5):
    """Material Production row -> blacksmith -> Material Production -> add materials to the free slots."""
    from common import close_gem_dialogs
    kinds = [k for k in (kinds or ()) if k in MAT_DX] or list(MAT_DX)
    if not press_row_action(g, sleep, "materials"):
        return 0
    if not window_open(g, ("material", "production")):
        log(f"    ! materials: the production window did not open (title '{window_title(g)[:40]}')")
        import smart
        smart.recover_screen(g)
        return 0
    added = 0
    for i in range(max(0, min(5, int(slots or 0)))):
        g.click_rel(*rel(g, MAT_DX[kinds[i % len(kinds)]], -66)); sleep(1.6)
        if close_gem_dialogs(g):
            log("    ! materials: the game asked for gems - answered NO")
            break
        added += 1
    close_window(g, sleep)
    log(f"  materials: {added} production(s) queued ({', '.join(kinds[j % len(kinds)] for j in range(added)) or '-'})")
    return added
