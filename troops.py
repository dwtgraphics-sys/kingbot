"""Deployed marches from the in-game "Troops" list.

The blue expand button left of the march counter (1/5 ... X/5, top-right of the game screen) opens the
"Troops" popup. Every row there has: the two commanders, Units, the target coordinates and label, a status line
with its countdown timer (HH:MM:SS) and, when the army can come back, the yellow recall button.

read_troops(g, sleep) -> list of marches, or None when the popup could not be opened (the caller then uses the
older per-card reader). Nothing here presses recall, speed-ups or anything that costs gems: it only opens the
list, reads it, scrolls it and closes it again.
"""
import base64
import datetime
import re

from common import log

COUNTER = [None, None]          # last X/Y read next to the expand button
TIMER = re.compile(r"(?:(\d+)\s*d\s*)?(\d{1,2}):(\d{2}):(\d{2})")
XY = re.compile(r"X\s*[:;.]?\s*(\d{1,4})\D{0,4}Y\s*[:;.]?\s*(\d{1,4})", re.I)
NUM = re.compile(r"\d{1,3}(?:[,.]\d{3})+|\d+")
STATUS = (  # (regex, status key used by the dashboard, mission)
    (r"gather", "gather", "gather"),
    (r"camp|await", "standby", "standby"),
    (r"garrison", "garrison", "garrison"),
    (r"prepar", "preparing", "rally"),
    (r"rally", "rally", "rally"),
    (r"return", "return", ""),
    (r"attack|battle|fight", "attack", "barbarians"),
    (r"occup|station", "standby", "standby"),
    (r"march|moving|heading", "march", ""),
)


def _secs(m):
    d, hh, mm, ss = m.groups()
    return int(d or 0) * 86400 + int(hh) * 3600 + int(mm) * 60 + int(ss)


def _expand_button(g, img):
    """(rx, ry) of the blue expand button next to the march counter, or None."""
    import cv2
    import numpy as np
    import smart
    h, w = img.shape[:2]
    y0, y1, x0 = int(0.03 * h), int(0.45 * h), int(0.78 * w)
    boxes = smart._ocr_boxes(img[y0:y1, x0:], "troops_counter.png", scale=2.0)
    cnt = next((b for b in boxes if re.fullmatch(r"\s*\d\s*/\s*\d\s*", b[4])), None) or \
        next((b for b in boxes if len(b[4]) <= 9 and re.search(r"\b\d\s*/\s*[1-6]\b", b[4])), None)   # v308: '5/5 ...'
    if cnt is None:                                           # v308: the bright counter reads better inverted
        import cv2 as _cv
        inv = 255 - img[y0:y1, x0:]
        boxes = smart._ocr_boxes(inv, "troops_counter_inv.png", scale=2.5)
        cnt = next((b for b in boxes if len(b[4]) <= 9 and re.search(r"\d\s*/\s*[1-6]", b[4])), None)
    if cnt is None:
        log("    troops: march counter (X/5) not found")
        return None
    mm = re.search(r"(\d)\s*/\s*(\d)", cnt[4])
    COUNTER[0], COUNTER[1] = int(mm.group(1)), int(mm.group(2))
    cx1, cy1, cx2, cy2 = cnt[0] + x0, cnt[1] + y0, cnt[2] + x0, cnt[3] + y0
    band_h = max(cy2 - cy1, int(0.03 * h))
    by0, by1 = max(0, int(cy1 - band_h)), min(h, int(cy2 + band_h))
    bx0 = max(0, int(cx1 - 0.09 * w))
    crop = img[by0:by1, bx0:int(cx1)]
    if crop.size:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        m = cv2.inRange(hsv, (92, 110, 150), (118, 255, 255))           # the bright blue square
        n, _, stats, cents = cv2.connectedComponentsWithStats(m)
        best = max(range(1, n), key=lambda i: stats[i][4], default=None)
        if best is not None and stats[best][4] > 0.00008 * w * h:
            x, y = cents[best]
            return (bx0 + x) / w, (by0 + y) / h
    # no blue blob seen: the button sits just left of the counter
    return (cx1 - 0.022 * w) / w, ((cy1 + cy2) / 2) / h


def _is_open(g, sleep):
    import smart
    for _ in range(3):
        img = g.screenshot()
        h, w = img.shape[:2]
        top = img[int(0.02 * h):int(0.30 * h), int(0.20 * w):int(0.80 * w)]
        boxes = smart._ocr_boxes(top, "troops_title.png", scale=1.6)
        t = next((b for b in boxes if re.search(r"\btroops?\b", b[4], re.I)), None)
        if t:
            return img, t[3] + int(0.02 * h)
        sleep(1)
    return None, None


def _rows(img, top_y):
    """Parse the visible rows of the popup."""
    import cv2
    import numpy as np
    import smart
    h, w = img.shape[:2]
    X0, X1, Y0, Y1 = int(0.08 * w), int(0.92 * w), int(top_y), int(0.96 * h)
    reg = img[Y0:Y1, X0:X1]
    boxes = [(b[0] + X0, b[1] + Y0, b[2] + X0, b[3] + Y0, b[4]) for b in smart._ocr_boxes(reg, "troops_rows.png", scale=2.0)]
    if not boxes:
        return []
    cy = lambda b: (b[1] + b[3]) / 2
    anchors = sorted({round(cy(b)) for b in boxes if XY.search(b[4].replace(" ", ""))})
    if not anchors:
        anchors = sorted({round(cy(b)) for b in boxes if re.search(r"units?", b[4], re.I)})
    if not anchors:
        return []
    merged = []
    for a in anchors:                          # one anchor per row
        if not merged or a - merged[-1] > 0.04 * h:
            merged.append(a)
    rows = []
    for i, a in enumerate(merged):
        lo = (merged[i - 1] + a) / 2 if i else a - 0.09 * h
        hi = (a + merged[i + 1]) / 2 if i + 1 < len(merged) else a + 0.09 * h
        rb = sorted([b for b in boxes if lo <= cy(b) < hi], key=lambda b: (round(cy(b) / (0.012 * h)), b[0]))
        if rb:
            rows.append((lo, hi, rb))
    out = []
    for lo, hi, rb in rows:
        txt = " | ".join(b[4] for b in rb)
        flat = txt.replace(" ", "")
        a = {"raw": txt[:200]}
        m = XY.search(flat)
        if m:
            a["x"], a["y"] = int(m.group(1)), int(m.group(2))
            a["coords"] = {"x": a["x"], "y": a["y"]}
        m = TIMER.search(txt)
        if m:
            a["timer_raw"] = m.group(0).strip()
            a["timer_seconds"] = _secs(m)
        units = None
        for j, b in enumerate(rb):
            if re.search(r"units?", b[4], re.I):
                cand = NUM.findall(re.sub(r"units?", "", b[4], flags=re.I))
                if not cand:
                    near = sorted((x for x in rb if x is not b and abs(cy(x) - cy(b)) < 0.02 * h), key=lambda x: abs(x[0] - b[2]))
                    cand = [n for x in near for n in NUM.findall(x[4])]
                if cand:
                    units = int(re.sub(r"\D", "", cand[0]))
                    break
        if units is None:
            nums = [int(re.sub(r"\D", "", n)) for b in rb for n in re.findall(r"\d{1,3}(?:,\d{3})+", b[4])]
            units = max(nums) if nums else None
        if units is not None:
            a["units"] = a["troops"] = units
        low = flat.lower()
        names = []
        for b in sorted(rb, key=lambda b: (b[1], b[0])):
            bl = b[4].lower().replace(" ", "")
            for cn in smart.COMMANDER_NAMES:
                k = cn.lower().replace(" ", "")
                if len(k) > 3 and k in bl and cn not in names and not any(cn != o and k in o.lower().replace(" ", "") for o in names):
                    names.append(cn)
        names = [n for n in names if not any(n != o and n.lower() in o.lower() for o in names)]
        if names:
            a["commanders"] = names[:2]
            a["primary_commander"] = names[0]
            a["secondary_commander"] = names[1] if len(names) > 1 else ""
        st = next((s for s in STATUS if re.search(s[0], low)), None)
        a["status"] = st[1] if st else "march"
        if st and st[2]:
            a["mission"] = st[2]
        stl = next((b[4] for b in rb if re.search(r"gather|camp|await|garrison|prepar|rally|return|attack|occup|march|moving", b[4], re.I)), "")
        a["status_text"] = stl.strip()
        lab = next((b[4] for b in rb if re.search(r"(lv\.?|lvl|level)\s*\d|fort|fortress|flag|deposit|farm|lumber|quarry|mine|gem|barbarian|keep", b[4], re.I)
                    and not XY.search(b[4].replace(" ", ""))), "")
        if lab:
            a["target_label"] = a["target"] = lab.strip()
        kind = next((k for k, rx in (("gems", r"gem"), ("food", r"farm|crop|food"), ("wood", r"lumber|wood|log"),
                                     ("stone", r"quarry|stone"), ("gold", r"gold")) if re.search(rx, low)), "")
        if kind:
            a["kind"] = kind
        m = re.search(r"(\d{1,3})\s*%", txt)
        if m and int(m.group(1)) <= 100:
            a["progress_percent"] = a["pct"] = int(m.group(1))
        # yellow recall button at the right end of the row
        try:
            band = img[int(lo):int(hi), int(0.70 * w):X1]
            hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
            ym = cv2.inRange(hsv, (15, 130, 170), (35, 255, 255))
            a["can_recall"] = bool(ym.sum() / 255 > 0.0006 * w * h)
        except Exception:
            a["can_recall"] = False
        # commander portraits: the picture left of the first text in the row
        try:
            left = int(min(b[0] for b in rb))
            por = img[int(lo):int(hi), max(X0, left - int(0.12 * w)):max(X0 + 4, left - 4)]
            if por.size and por.shape[1] > 10:
                ph = 56
                pw = max(56, int(por.shape[1] * ph / max(1, por.shape[0])))
                ok, buf = cv2.imencode(".jpg", cv2.resize(por, (min(pw, 112), ph)), [cv2.IMWRITE_JPEG_QUALITY, 72])
                if ok:
                    a["avatar"] = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
        except Exception:
            pass
        out.append(a)
    return out


def read_troops(g, sleep, expected=None):
    import smart
    from common import recover_screen
    COUNTER[0] = COUNTER[1] = None
    img = g.screenshot()
    btn = _expand_button(g, img)
    if not btn:
        return None
    g.click_rel(*btn)
    sleep(2)
    img, top = _is_open(g, sleep)
    if img is None:
        log("    troops: the Troops list did not open - using the older reader")
        recover_screen(g)
        return None
    seen, out = set(), []
    try:
        for page in range(4):
            rows = _rows(img, top)
            new = 0
            for a in rows:
                key = (a.get("x"), a.get("y"), a.get("units"), tuple(a.get("commanders") or ()))
                if key in seen:
                    continue
                seen.add(key)
                out.append(a)
                new += 1
            if not new or (expected and len(out) >= expected) or len(rows) < 3:
                break
            h, w = img.shape[:2]
            smart._drag(g, 0.5, 0.80, 0.5, 0.40)               # scroll the list
            sleep(1.5)
            img = g.screenshot()
    finally:
        recover_screen(g)                                      # close the popup, back to the plain view
        sleep(1)
    now = datetime.datetime.utcnow()
    for i, a in enumerate(out):
        a["index"] = a["slot"] = i + 1
        a["updated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        a["source"] = "troops"
        a.setdefault("timer_raw", None)
        a.setdefault("timer_seconds", None)
        a.setdefault("progress_percent", None)
        a.pop("raw", None)
    log(f"  troops list: {len(out)} march(es): " + "; ".join(
        f"{a['index']}:{a['status']} {'/'.join(a.get('commanders') or [])} {a.get('units', '?')} "
        f"({a.get('x', '?')},{a.get('y', '?')}) {a.get('timer_raw') or ''}" for a in out))
    return out
