# -*- coding: utf-8 -*-
"""
Smart activities: Kingbot finds the buttons on screen by itself (no recording needed).
A recorded routine with the same name always takes priority over the smart one.
"""
import os, time, tempfile
from common import log, pyautogui, click_mode, set_click_mode, CLICK_MODES, press_key, recover_screen, BASE, load_json, save_json

RESOURCE_BUBBLES = ["res_food", "res_wood", "res_stone", "res_gold"]


def _bubbles(g):
    img = g.screenshot()
    found = []
    for name in RESOURCE_BUBBLES:
        found += [(name, p) for p in g.find_image(name, 0.75, True, img=img)]
    return found


def _near(p, found, tol=0.02):
    return any(abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol for _, q in found)


def _click_landing(g, rx, ry, sleep, waits=4):
    """Click; if the pointer is held by something else (RDP / iPad mouse), wait and retry."""
    for i in range(waits):
        if g.click_rel(rx, ry):
            return True
        if click_mode() != "absolute":
            return False
        log("  ! pointer is held by another mouse (RDP / iPad?). Waiting 15 s ...")
        sleep(15)
    return False


def collect_city(g, sleep):
    """Click every resource bubble above farms, sawmills, quarries and gold mines.
    A method only counts as working when the clicked bubble is really gone (checked twice)."""
    if ensure_screen(g, sleep, "city", tries=2) != "city":     # v181: never collect on the map
        log("  ! collect_city: the city is not showing - skipped")
        return True
    saved = click_mode()
    log(f"  collect_city: {g.describe()}, click method: {saved}")
    found = _bubbles(g)
    if not found:
        log("  collect_city: no bubbles to collect")
        return True
    first = len(found)
    log(f"  collect_city: found {first} bubbles")
    order = ["absolute", "message"]          # the only methods that can work without the driver
    if saved in order:
        order.remove(saved)
        order.insert(0, saved)
    for mode in order:
        if mode != click_mode():
            set_click_mode(mode)
        name, (rx, ry) = found[0]
        if not _click_landing(g, rx, ry, sleep):
            log(f"  ! method '{mode}': click could not be delivered")
            continue
        sleep(2)
        gone = not _near((rx, ry), _bubbles(g))
        if gone:
            sleep(1)
            gone = not _near((rx, ry), _bubbles(g))      # confirm: detection can flicker
        if not gone:
            log(f"  ! method '{mode}' had no effect")
            continue
        log(f"  collect_city: method '{mode}' works")
        # click one bubble at a time, looking again after each click, so a click never lands
        # on a building whose bubble is already gone (that opens its Upgrade panel)
        for _ in range(first * 2 + 4):
            after = _bubbles(g)
            if not after:
                break
            name, (bx, by) = after[0]
            _click_landing(g, bx, by, sleep, waits=2)
            sleep(0.9)
        sleep(1)
        after = _bubbles(g)
        got = sum(1 for _, p in found if not _near(p, after))
        log(f"  collect_city: collected {got} of {first} bubbles")
        return True
    set_click_mode("absolute")
    log("  ! collect_city: nothing collected. If you are connected to the server by RDP, "
        "disconnect (or do not touch the screen) while Kingbot works.")
    return True


def _alliance_help_clicks(g, sleep, limit):
    """v186: press the handshake while it is showing. Returns how many presses landed."""
    pressed = 0
    for _ in range(max(0, limit)):
        spot = find_element(g, "alliance_help_button")
        if not spot:
            break
        if not click_verified(g, spot, sleep, wait=1.6, tries=1, label="alliance_help"):
            break
        pressed += 1
        sleep(0.8)
    return pressed


def alliance_help(g, sleep, max_helps=6):
    """v186: press the alliance Help (handshake) button.

    Looks on the current screen first (the city HUD shows it while members need help), then
    inside the alliance window, which it opens with O and closes again.
    """
    import control
    pressed = _alliance_help_clicks(g, sleep, max_helps)
    if pressed:
        log(f"  alliance_help: helped {pressed} request(s)")
        return True

    log("  alliance_help: nothing on the city screen - opening the alliance window")
    press_key("o"); sleep(3)
    pressed = _alliance_help_clicks(g, sleep, max_helps)
    if pressed:
        log(f"  alliance_help: helped {pressed} request(s) from the alliance window")
    else:
        log("  alliance_help: no help request right now")
    try:
        recover_screen(g)
    except Exception:
        pass
    try:
        control.CITY["alliance_help"] = {"at": _now_hhmm(), "count": pressed}
    except Exception:
        pass
    return True


def _now_hhmm():
    import datetime as _dt
    return _dt.datetime.now().strftime("%H:%M")


SMART = {"collect_city": collect_city, "alliance_help": alliance_help}


# ---------------- gather: send armies to resource points on the map ----------------
GATHER_KINDS = ["food", "wood", "stone", "gold"]
GATHER_NEXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gather_next.txt")


def _next_kind(kinds=None):
    kinds = [k for k in (kinds or GATHER_KINDS) if k in GATHER_KINDS] or GATHER_KINDS
    try:
        i = int(open(GATHER_NEXT).read().strip())
    except Exception:
        i = 0
    try:
        open(GATHER_NEXT, "w").write(str(i + 1))
    except Exception:
        pass
    return kinds[i % len(kinds)]


def _in_city(g, img=None):
    """v188: the city HUD is proven by the three-line queue button."""
    img = img if img is not None else g.screenshot()
    return bool(g.find_image("queue_btn", 0.55, img=img) or g.find_image("city_build_icon", 0.8, img=img))


def _on_map(g, img=None):
    """v188: the map is the view where the city HUD button is gone."""
    img = img if img is not None else g.screenshot()
    if _in_city(g, img=img):
        return False
    return bool(g.find_image("space_on_city", 0.75, img=img) or g.find_image("map_search_icon", 0.8, img=img))


def _click_tpl(g, name, sleep, threshold=0.78, wait=2.0, tries=3):
    for _ in range(tries):
        hits = g.find_image(name, threshold)
        if hits:
            _click_landing(g, *hits[0], sleep, waits=2)
            sleep(wait)
            return True
        sleep(1.5)
    return False


def _queue_full(g):
    """True when every march slot is already out (the army counter at the top right shows 5/5)."""
    return bool(g.find_image("queue_full", 0.92))


def _marches_out(g):
    """v136: (armies out, march slots) from the counter at the top right of the map; status icons as fallback."""
    img = g.screenshot()
    n, mx = _march_count(img)
    if n is None:
        n = 0
        while n < 5 and _march_status(img, n) != "march":
            n += 1
    return int(n), int(mx or 5)


def _balanced_kinds(kinds, target_ratios, n):
    """TASK-02: order of resource types for the next n marches - the type whose share of the city stock is the
    furthest below its target share goes first (each march sent lowers that gap a little). Uses the last
    resource-bar reading (control.RESOURCES); None if there is no reading yet."""
    import control
    stock = {k: float(control.RESOURCES.get(k) or 0) for k in GATHER_KINDS}
    kinds = [k for k in (kinds or GATHER_KINDS) if k in GATHER_KINDS] or list(GATHER_KINDS)
    tot = sum(stock[k] for k in kinds)
    if tot <= 0:
        return None
    tr = {}
    for k in kinds:
        try:
            tr[k] = max(0.0, float((target_ratios or {}).get(k, 25)))
        except Exception:
            tr[k] = 25.0
    ts = sum(tr.values()) or 1.0
    want = {k: tr[k] / ts for k in kinds}
    share = {k: stock[k] / tot for k in kinds}
    plan, bump = [], {k: 0.0 for k in kinds}
    for _ in range(max(1, int(n))):
        k = max(kinds, key=lambda x: want[x] - share[x] - bump[x])
        plan.append(k)
        bump[k] += 0.05                          # one march ≈ a small step; spreads a big gap over 2-3 types
    log("    balanced gather: stock " + ", ".join(f"{k} {share[k]:.0%}/{want[k]:.0%}" for k in kinds) +
        " -> " + " > ".join(plan))
    return plan


MARCH_CONTROL = {}      # TASK-06: dashboard march_control (set by bot.py every round)


def _march_cap_reached(g, label):
    """TASK-06: True when max_concurrent_marches armies are already out (0 / missing = no own limit)."""
    try:
        cap = int(MARCH_CONTROL.get("max_concurrent_marches") or 0)
    except Exception:
        cap = 0
    if cap <= 0:
        return False
    n_out, _ = _marches_out(g)
    if n_out is not None and n_out >= cap:
        log(f"  {label}: {n_out} armies out - the dashboard limit is {cap} at the same time")
        return True
    return False


def _search_deadline():
    """TASK-06: seconds one map search / march-list read may take before it is abandoned (default 15)."""
    try:
        return max(5, min(120, int(MARCH_CONTROL.get("search_timeout_seconds") or 15)))
    except Exception:
        return 15


COMMANDER_PRESETS = {}  # TASK-07: dashboard commander_presets {task: {primary, secondary}} (set by bot.py every round)


def _preset(task):
    """TASK-07: (primary, secondary) commander names chosen in the dashboard for <task> ("" when none)."""
    p = COMMANDER_PRESETS.get(task) if isinstance(COMMANDER_PRESETS, dict) else None
    if not isinstance(p, dict):
        return "", ""
    return str(p.get("primary") or "").strip(), str(p.get("secondary") or "").strip()


def _apply_preset(g, sleep, task):
    """TASK-07: the New Troop window is open - swap in the task's preset commanders. Without a preset (or when
    the swap fails) the loadout the game already put in is kept. Returns True when the preset was applied."""
    c1, c2 = _preset(task)
    if not c1:
        return False
    try:
        ok = _rally_swap_commanders(g, sleep, c1, c2)
    except Exception as e:
        log(f"  ! {task}: commander preset failed: {e!r}")
        ok = False
    if not g.find_image("btn_march", 0.78):
        recover_screen(g)
        return False
    log(f"    {task}: commanders {c1}{(' + ' + c2) if c2 else ''}" if ok else f"  ! {task}: preset commander {c1} not available - keeping the loadout")
    return ok


def gather(g, sleep, max_armies=5, kinds=None, reserve=0, balanced_mode=False, target_ratios=None):
    """Map > search (F) > resource type > SEARCH > GATHER > New Troop > MARCH, for each free march slot.
    Resource types rotate food > wood > stone > gold.
    v136: reserve = march slots kept free (e.g. 1 for a barbarian fort rally).
    TASK-02: balanced_mode = instead of rotating, send each march to the type that is most below its target share
    (target_ratios {"food": 40, "wood": 30, ...} in percent) of the city stock."""
    plan = _balanced_kinds(kinds, target_ratios, max_armies) if balanced_mode else None
    try:
        reserve = max(0, min(4, int(reserve or 0)))
    except Exception:
        reserve = 0
    if _queue_full(g):
        log("  gather: all armies are already out gathering (5/5) - nothing sent")
        return True
    if not goto_map(g, sleep, "gather"):
        return True
    sent = 0
    for _ in range(int(max_armies)):
        if _queue_full(g):
            log("  gather: all march slots are now busy (5/5)")
            break
        if reserve:
            n_out, n_max = _marches_out(g)
            if n_out >= n_max - reserve:
                log(f"  gather: {n_out}/{n_max} armies out - keeping {reserve} march slot(s) free as set in the dashboard")
                break
        if _march_cap_reached(g, "gather"):
            break
        kind = plan.pop(0) if plan else _next_kind(kinds)
        t_search = time.time()
        press_key("f"); sleep(3)
        if not _click_tpl(g, "icon_" + kind, sleep, 0.75):
            log("  ! gather: search panel did not open")
            press_key("esc"); sleep(1)
            break
        if not _click_tpl(g, "btn_search", sleep, wait=4):
            log("  ! gather: SEARCH button not found")
            press_key("esc"); sleep(1)
            break
        if time.time() - t_search > _search_deadline():
            log(f"  ! gather: the {kind} search took longer than {_search_deadline()} s - stopped, back to the city")
            press_key("esc"); sleep(1)
            recover_screen(g)
            break
        if not _click_tpl(g, "btn_gather", sleep, wait=3):
            log(f"  - gather: no free {kind} point found, trying the next type")
            press_key("esc"); sleep(1)
            continue
        if not _click_tpl(g, "btn_new_troop", sleep, wait=3):
            log("  gather: all march slots are busy")
            press_key("esc"); sleep(1)
            break
        if _preset("gathering_" + kind)[0] and not _apply_preset(g, sleep, "gathering_" + kind) \
                and not g.find_image("btn_march", 0.78):
            break                                                     # TASK-07: screen was reset
        if not _click_tpl(g, "btn_march", sleep, wait=3):
            log("  ! gather: MARCH button not found")
            press_key("esc"); sleep(1)
            break
        if g.find_image("btn_march", 0.78):
            log("  gather: no troops left to send")
            press_key("esc"); sleep(1)
            break
        sent += 1
        log(f"  gather: army sent to {kind}")
    if _on_map(g):
        press_key("space"); sleep(4)      # back to the city
    log(f"  gather: {sent} armies sent")
    return True


SMART["gather"] = gather


# ---------------- gather gems: scan the map around the city for gem deposits ----------------
GEM_PANS = [(0.8, 0.5, 0.2, 0.5), (0.5, 0.8, 0.5, 0.2), (0.2, 0.5, 0.8, 0.5), (0.2, 0.5, 0.8, 0.5),
            (0.5, 0.2, 0.5, 0.8), (0.5, 0.2, 0.5, 0.8), (0.8, 0.5, 0.2, 0.5), (0.8, 0.5, 0.2, 0.5)]   # ring around the city


def _white_mask(img):
    import cv2
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (0, 0, 215), (180, 60, 255))


def _find_gem_icons(g, threshold=0.72):
    """Gem deposit icons (white hexagon) on the zoomed-out map, as relative points (UI areas ignored)."""
    import cv2, numpy as np
    from common import BUILTIN_DIR
    tpl = cv2.imread(os.path.join(BUILTIN_DIR, "gem_icon.png"))
    if tpl is None:
        return []
    img = g.screenshot()
    scale = g.w / 1897.0
    if abs(scale - 1) > 0.02:
        tpl = cv2.resize(tpl, None, fx=scale, fy=scale)
    m = _white_mask(img).astype(np.float32)
    t = _white_mask(tpl).astype(np.float32)
    res = cv2.matchTemplate(m, t, cv2.TM_CCOEFF_NORMED)
    th, tw = t.shape
    ys, xs = np.where(res >= threshold)
    hits = []
    for x, y in sorted(zip(xs, ys), key=lambda p: -res[p[1], p[0]]):
        rx, ry = (x + tw / 2) / g.w, (y + th / 2) / g.h
        if rx > 0.93 or ry > 0.85 or ry < 0.08 or (rx < 0.13 and ry < 0.46):
            continue
        if all(abs(rx - hx) > 0.03 or abs(ry - hy) > 0.03 for hx, hy in hits):
            hits.append((rx, ry))
    return hits


def _send_army(g, sleep):
    """After a resource popup is open: GATHER > New Troop > MARCH. Returns 'sent', 'busy' or 'fail'."""
    if not _click_tpl(g, "btn_gather", sleep, wait=3):
        return "fail"
    if not _click_tpl(g, "btn_new_troop", sleep, wait=3):
        press_key("esc"); sleep(1)
        return "busy"
    if not _click_tpl(g, "btn_march", sleep, wait=3) or g.find_image("btn_march", 0.78):
        press_key("esc"); sleep(1)
        return "fail"
    return "sent"


GEM_PER_LEVEL = {1: 10, 2: 20}


def _gem_day(gems_now=None, sent_level=None):
    """v88: gems collected today (UTC game day). Two ways: top-bar gem count minus the day's first reading
    (spent gems never happen), and an estimate from armies sent to gem mines (Lv1 = 10, Lv2 = 20 per send)."""
    import json, datetime, control
    from common import BASE
    path = os.path.join(BASE, "gems_day.json")
    day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    try:
        d = json.load(open(path))
    except Exception:
        d = {}
    if d.get("day") != day:
        d = {"day": day, "sends": 0, "est": 0, "start": None, "last": None}
    if gems_now is not None and gems_now >= 0:
        if d.get("start") is None or (d.get("last") is not None and abs(gems_now - d["last"]) > 5000):
            d["start"] = gems_now if d.get("start") is None else d["start"]
        if d.get("last") is None or abs(gems_now - d["last"]) <= 5000:   # ignore OCR jumps
            d["last"] = gems_now
    if sent_level:
        d["sends"] += 1
        d["est"] += GEM_PER_LEVEL.get(int(sent_level), 10 * int(sent_level))
    json.dump(d, open(path, "w"))
    control.CITY["gem_sends"] = d["sends"]
    control.CITY["gems_est"] = d["est"]
    if d.get("start") is not None and d.get("last") is not None:
        control.CITY["gems_today"] = max(0, d["last"] - d["start"])
    return d


def _gem_level(g):
    """Read 'Lv. N' of the gem deposit popup (OCR); 1 if not readable."""
    import re
    img = g.screenshot()
    h, w = img.shape[:2]
    t = " ".join(_ocr_lines(img[int(0.12 * h):int(0.70 * h), int(0.15 * w):int(0.85 * w)], "gem_lv.png", scale=1.5))
    m = re.search(r"(?:Lv|Level)\.?\s*(\d)", t, re.I)
    return int(m.group(1)) if m else 1


def _gems_collected_today():
    """Gems gathered today (UTC): the larger of the send estimate and the gem-balance increase."""
    d = _gem_day()
    est = int(d.get("est") or 0)
    bar = max(0, int(d["last"]) - int(d["start"])) if d.get("start") is not None and d.get("last") is not None else 0
    return max(est, bar)


def _combat_near(img, rx, ry, r=0.10):
    """TASK-01: True if bright red march / attack lines or a fight are seen around (rx, ry) on the map.
    Counts strongly saturated red pixels in a box around the spot (the map itself has almost none)."""
    import cv2
    h, w = img.shape[:2]
    x0, x1 = max(0, int((rx - r) * w)), min(w, int((rx + r) * w))
    y0, y1 = max(0, int((ry - r * 1.6) * h)), min(h, int((ry + r * 1.6) * h))
    box = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    if box.size == 0:
        return False
    red = cv2.countNonZero(cv2.inRange(box, (0, 170, 150), (6, 255, 255))) + \
        cv2.countNonZero(cv2.inRange(box, (174, 170, 150), (180, 255, 255)))
    share = red / float(box.shape[0] * box.shape[1])
    if share > 0.012:
        log(f"    gems: red lines / fight near the deposit ({share:.1%} red) - skipped")
        return True
    return False


def _hour_in(rng, hour):
    """TASK-01: rng = [from, to] in UTC hours (to may pass midnight: [22, 6])."""
    try:
        a, b = int(rng[0]) % 24, int(rng[1]) % 24
    except Exception:
        return True
    if a == b:
        return True
    return a <= hour < b if a < b else (hour >= a or hour < b)


GEM_SCHED_FILE = os.path.join(BASE, "gem_sched_state.json")


def _gem_sched(run_max_h=4, rest_min_h=1, offset_max_min=15, day_cap_h=18):
    """GUIDE-13: gem farming runs of at most run_max_h hours, then at least rest_min_h hours of rest plus a random
    0-offset_max_min minute start offset, and at most day_cap_h hours of gem gathering per character per UTC day.
    Returns (allowed, reason)."""
    import random, time as _t
    st = load_json(GEM_SCHED_FILE, {}) or {}
    key = (_char_key() or "main") if "_char_key" in globals() else "main"
    day = _t.strftime("%Y-%m-%d", _t.gmtime())
    c = st.get(key) or {}
    if c.get("day") != day:
        c = {"day": day, "used": 0.0, "run_start": c.get("run_start") if c.get("day") == day else None, "rest_until": c.get("rest_until", 0)}
    now = _t.time()
    if now < (c.get("rest_until") or 0):
        return False, f"resting until {_t.strftime('%H:%M', _t.gmtime(c['rest_until']))} UTC"
    if c.get("run_start"):
        run = now - c["run_start"]
        if run >= float(run_max_h) * 3600:
            c["used"] = c.get("used", 0) + run
            c["run_start"] = None
            c["rest_until"] = now + float(rest_min_h) * 3600 + random.uniform(0, float(offset_max_min)) * 60
            st[key] = c; save_json(GEM_SCHED_FILE, st)
            return False, f"run of {run_max_h} h finished - resting at least {rest_min_h} h"
    if c.get("used", 0) + ((now - c["run_start"]) if c.get("run_start") else 0) >= float(day_cap_h) * 3600:
        st[key] = c; save_json(GEM_SCHED_FILE, st)
        return False, f"{day_cap_h} h of gem gathering reached today"
    if not c.get("run_start"):
        c["run_start"] = now
    st[key] = c; save_json(GEM_SCHED_FILE, st)
    return True, ""


def gather_gems(g, sleep, max_armies=4, day_limit=1200, max_level=0, search_radius=2, avoid_combat_zones=True,
                quiet_hours_only=False, quiet_hours=(22, 6), commander_preset=0,
                gem_scheduler=True, run_max_hours=4, rest_min_hours=1, start_offset_max_min=15, day_cap_hours=18):
    """Look for gem deposits around the city (zoomed-out map) and send free armies to them.
    v115: stops once today's gems reach day_limit (0 = no limit).
    TASK-01 (Smart Gem Farming): max_level (2 = only level 1-2 deposits, 0 = any), search_radius 1-3 (how far the
    camera pans around the city), avoid_combat_zones (skip deposits with red lines / fights nearby),
    quiet_hours_only + quiet_hours (UTC range), random pauses between sends. commander_preset is kept for the
    task-presets feature (TASK-07): the march uses the game's default troop until then."""
    import random
    if quiet_hours_only and not _hour_in(quiet_hours, time.gmtime().tm_hour):
        log(f"  - gather_gems: only in quiet hours {quiet_hours} UTC - not now")
        return True
    if gem_scheduler:                                       # GUIDE-13: 4 h runs, 1 h rest, 18 h/day per character
        ok, why = _gem_sched(run_max_hours, rest_min_hours, start_offset_max_min, day_cap_hours)
        if not ok:
            log(f"  - gather_gems: gem scheduler - {why}")
            return True
    try:
        pan_max = {1: 0, 2: 4, 3: len(GEM_PANS)}.get(int(search_radius or 2), 4)
    except Exception:
        pan_max = 4
    max_level = int(max_level or 0)
    limit = int(day_limit or 0)
    if limit > 0:
        got = _gems_collected_today()
        if got >= limit:
            log(f"  - gather_gems: daily limit reached ({got:,}/{limit:,} gems today) - no armies to gems until 00:00 UTC")
            return True
        log(f"    gems today: {got:,}/{limit:,}")
    if _queue_full(g):
        log("  gather_gems: all armies are already out (5/5) - nothing sent")
        return True
    if _on_map(g):                      # re-enter the map so the zoom is always the same
        press_key("space"); sleep(4)
    if not goto_map(g, sleep, "gather_gems"):
        return True
    import pyautogui
    cx, cy = g.to_screen(0.5, 0.5)
    pyautogui.moveTo(cx, cy)
    for _ in range(2):
        pyautogui.scroll(-5 * 120); sleep(2)
    sent, pans, tried = 0, 0, []
    steps = 0
    t_start = time.time()
    while sent < int(max_armies) and pans <= pan_max and steps < 20:
        steps += 1
        if _march_cap_reached(g, "gather_gems"):
            break
        if time.time() - t_start > _search_deadline() * (sent + 2) * 2:      # TASK-06: never hang on the map
            log(f"  ! gather_gems: the gem search is taking too long - stopped, back to the city")
            break
        if _queue_full(g):
            break
        if limit > 0 and _gems_collected_today() >= limit:
            log(f"  gather_gems: daily limit of {limit:,} gems reached - stopping")
            break
        hits = [h for h in _find_gem_icons(g)
                if all(abs(h[0] - t[0]) > 0.04 or abs(h[1] - t[1]) > 0.04 for t in tried)]
        if hits:
            rx, ry = hits[0]
            tried.append((rx, ry))
            log(f"  gather_gems: gem deposit seen at {rx:.2f},{ry:.2f}")
            if avoid_combat_zones and _combat_near(g.screenshot(), rx, ry):
                continue
            sleep(random.uniform(0.6, 2.4))                      # TASK-01: jitter - not the same rhythm every time
            _click_landing(g, rx, ry, sleep, waits=2); sleep(3)       # zooms in on that spot
            mine = g.find_image("gem_mine_core", 0.7)
            if mine:
                _click_landing(g, *mine[0], sleep, waits=2); sleep(2)
                lv = _gem_level(g)
                if max_level and lv > max_level:
                    log(f"  - gather_gems: level {lv} deposit skipped (only level 1-{max_level})")
                    press_key("esc"); sleep(1)
                    r = "skip"
                else:
                    r = _send_army(g, sleep)
                if r == "sent":
                    sent += 1
                    d = _gem_day(sent_level=lv)
                    log(f"  gather_gems: army sent to a level {lv} gem deposit (today: {d['sends']} sends ≈ {d['est']} gems)")
                elif r == "busy":
                    break
                elif r == "skip":
                    pass
                else:
                    log("  - gather_gems: this deposit cannot be gathered (taken?)")
                    press_key("esc"); sleep(1)
            else:
                log("  - gather_gems: deposit not found after zooming in")
            # back to the zoomed-out view at the same place
            pyautogui.moveTo(cx, cy)
            for _ in range(2):
                pyautogui.scroll(-5 * 120); sleep(2)
            continue
        if pans >= pan_max:
            break
        x1, y1, x2, y2 = GEM_PANS[pans]
        sx, sy = g.to_screen(x1, y1); ex, ey = g.to_screen(x2, y2)
        pyautogui.moveTo(sx, sy); pyautogui.mouseDown()
        pyautogui.moveTo(ex, ey, duration=0.6); pyautogui.mouseUp()
        sleep(2)
        pans += 1
        tried = []
    if _on_map(g):
        press_key("space"); sleep(4)
    log(f"  gather_gems: {sent} armies sent to gems")
    return True


SMART["gather_gems"] = gather_gems


# ---------------- auto shield ----------------
ATTACK_STATE = {"hits": 0, "last": 0.0, "shielded_at": 0.0}


def _red_border_ratio(img):
    """Share of strongly red pixels in a thin band around the game screen (the game flashes red when attacked)."""
    import numpy as np
    h, w = img.shape[:2]
    b = max(4, int(min(h, w) * 0.025))
    bands = [img[:b, :], img[-b:, :], img[:, :b], img[:, -b:]]
    tot = red = 0
    for band in bands:
        bb, gg, rr = band[..., 0].astype(int), band[..., 1].astype(int), band[..., 2].astype(int)
        m = (rr > 160) & (gg < 90) & (bb < 90)
        red += int(m.sum()); tot += m.size
    return red / max(tot, 1)


def use_peace_shield(g, sleep, hours=8):
    """Items (I) > Boosts > 8-hour (else 24-hour) Peace Shield > USE. Returns True when USE was pressed.
    TASK-04: hours=24 tries the 24-hour shield first. Only shields already in the bag - never bought with gems."""
    press_key("i"); sleep(3)
    g.click_rel(0.432, 0.235); sleep(2)                      # Boosts tab
    done = False
    for name in (("shield_24h", "shield_8h") if int(hours or 8) == 24 else ("shield_8h", "shield_24h")):
        hits = g.find_image(name, 0.85)
        if not hits:
            continue
        g.click_rel(*hits[0]); sleep(1.5)
        if not g.find_image("title_peace_shield", 0.85):
            continue
        use = g.find_image("btn_use", 0.8)
        if use:
            g.click_rel(*use[0]); sleep(2.5)
            done = True
            break
    g.click_rel(0.863, 0.235); sleep(1.5)                   # close the items window
    log("  auto_shield: PEACE SHIELD USED" if done else "  ! auto_shield: no peace shield found in the bag")
    return done


SHIELD_STATE = {"active_until": 0.0, "sched_done": {}}


def _shield_used(g, sleep, hours, why):
    """TASK-04: shield on + urgent dashboard / Telegram alert + shield status for the dashboard card."""
    import time as _t, control
    if not use_peace_shield(g, sleep, hours):
        notify("attack", "⚠️ الدرع التلقائي: لم أجد درع سلام في الحقيبة (" + why + "). " + _t.strftime("%H:%M", _t.gmtime()) + " UTC")
        control.CITY["shield"] = {"state": "missing", "why": why, "t": _t.strftime("%Y-%m-%d %H:%M", _t.gmtime())}
        return False
    SHIELD_STATE["active_until"] = _t.time() + int(hours or 8) * 3600
    control.CITY["shield"] = {"state": "on", "why": why, "hours": int(hours or 8), "t": _t.strftime("%Y-%m-%d %H:%M", _t.gmtime()),
                              "until": _t.strftime("%Y-%m-%d %H:%M", _t.gmtime(SHIELD_STATE["active_until"]))}
    notify("attack", "🛡️ الدرع التلقائي: تم تفعيل درع السلام (" + why + ") — حتى " + control.CITY["shield"]["until"] + " UTC")
    return True


def auto_shield(g, sleep, mode="on_attack", pct=20, react_scout=False, trigger_on_attack=True, trigger_on_scout=None,
                shield_duration_hours=8, scheduled_shield_times=None):
    """Check for an attack on the city and turn on a peace shield.
    Detection: red flashing border (needs two hits in a row). Hospital % mode is not built yet.
    TASK-04: trigger_on_attack / trigger_on_scout (a single red flash is enough - scouting flashes only briefly),
    shield_duration_hours 8 or 24, scheduled_shield_times ["HH:MM", ...] UTC (each at most once a day, within
    10 minutes after the time). Uses only shields in the bag; an urgent alert goes to the dashboard + Telegram."""
    import time as _t, cv2, datetime
    if trigger_on_scout is None:
        trigger_on_scout = bool(react_scout)
    hours = 24 if str(shield_duration_hours) == "24" else 8
    now_dt = datetime.datetime.utcnow()
    if isinstance(scheduled_shield_times, str):
        import re as _re
        scheduled_shield_times = _re.findall(r"\d{1,2}:\d{2}", scheduled_shield_times)
    for hm in (scheduled_shield_times or []):
        try:
            hh, mm = [int(x) for x in str(hm).strip().split(":")[:2]]
        except Exception:
            continue
        at = now_dt.replace(hour=hh % 24, minute=mm % 60, second=0, microsecond=0)
        key = f"{now_dt:%Y-%m-%d} {hh:02d}:{mm:02d}"
        if 0 <= (now_dt - at).total_seconds() <= 600 and key not in SHIELD_STATE["sched_done"]:
            SHIELD_STATE["sched_done"][key] = 1
            if _t.time() < SHIELD_STATE["active_until"] - 600:
                log(f"  auto_shield: scheduled shield {hm} UTC - a shield is still active, skipped")
            else:
                log(f"  auto_shield: scheduled shield time {hm} UTC")
                _shield_used(g, sleep, hours, "موعد مجدول " + str(hm))
    if not (trigger_on_attack or trigger_on_scout):
        return True
    img = g.screenshot()
    r = _red_border_ratio(img)
    now = _t.time()
    if r > 0.12:
        try:
            from common import BASE
            out = os.path.join(BASE, "claude_out"); os.makedirs(out, exist_ok=True)
            cv2.imwrite(os.path.join(out, f"attack_check_{int(now)}.png"), img)
        except Exception:
            pass
    if r > 0.30:
        ATTACK_STATE["hits"] = ATTACK_STATE["hits"] + 1 if now - ATTACK_STATE["last"] < 120 else 1
        ATTACK_STATE["last"] = now
        log(f"! auto_shield: red warning on screen ({r:.0%}), check {ATTACK_STATE['hits']}/2")
        need = 2 if trigger_on_attack else 1
        if trigger_on_scout:
            need = 1
        if ATTACK_STATE["hits"] >= need and now - ATTACK_STATE["shielded_at"] > 1800 and now > SHIELD_STATE["active_until"] - 600:
            if mode == "hospital_pct":
                log("  auto_shield: hospital % mode is not ready yet - using the shield on attack instead")
            if _shield_used(g, sleep, hours, "تحذير أحمر: هجوم أو تجسس" if need == 1 else "هجوم على المدينة"):
                ATTACK_STATE["shielded_at"] = now
            ATTACK_STATE["hits"] = 0
    else:
        ATTACK_STATE["hits"] = 0
    return True


SMART["auto_shield"] = auto_shield

ATTACK_NOTE = {"hits": 0, "last": 0.0, "sent": 0.0}


def attack_watch(g):
    """v105: red flashing warning border = something of ours is attacked (city, gathering army, troops on the
    map, alliance building). Two hits in a row -> dashboard + Telegram notification (at most every 10 minutes)."""
    import time as _t
    r = _red_border_ratio(g.screenshot())
    now = _t.time()
    if r > 0.30:
        ATTACK_NOTE["hits"] = ATTACK_NOTE["hits"] + 1 if now - ATTACK_NOTE["last"] < 120 else 1
        ATTACK_NOTE["last"] = now
        if ATTACK_NOTE["hits"] >= 2 and now - ATTACK_NOTE["sent"] > 600:
            ATTACK_NOTE["sent"] = now
            notify("attack", "تحذير: هجوم! ظهر التحذير الأحمر في اللعبة (هجوم على المدينة أو على جيوشك أو مبنى التحالف). " +
                   _t.strftime("%H:%M", _t.gmtime()) + " UTC")
    else:
        ATTACK_NOTE["hits"] = 0


# ---------------- TASK-05: auto-return & recall ----------------
RECALL_STATE = {"hits": 0, "last": 0.0, "done": 0.0, "no_tpl": 0.0}


def auto_recall(g, sleep, recall_on_threat=True, cooldown_minutes=10):
    """TASK-05: when the red warning border shows twice in a row (an attack on our troops / city) while armies
    are out gathering, call the gathering armies back to the city and log it (counter "recall" in Daily gains).
    Recall = tap the army card in the right column (map view) -> the Return button (template btn_recall,
    captured from the game with record.py). Without that template it only warns. Never uses gems / items."""
    import time as _t
    if not recall_on_threat:
        return True
    now = _t.time()
    if now - RECALL_STATE["done"] < max(1, int(cooldown_minutes or 10)) * 60:
        return True
    r = _red_border_ratio(g.screenshot())
    if r <= 0.30:
        RECALL_STATE["hits"] = 0
        return True
    RECALL_STATE["hits"] = RECALL_STATE["hits"] + 1 if now - RECALL_STATE["last"] < 120 else 1
    RECALL_STATE["last"] = now
    if RECALL_STATE["hits"] < 2:
        return True
    RECALL_STATE["hits"] = 0
    tpl = os.path.join(BASE, "builtin_templates", "btn_recall.png")
    if not os.path.exists(tpl) and not os.path.exists(os.path.join(BASE, "templates", "btn_recall.png")):
        if now - RECALL_STATE["no_tpl"] > 3600:
            RECALL_STATE["no_tpl"] = now
            log("! auto_recall: threat seen but the Return button picture (btn_recall) is not recorded yet - cannot recall")
            notify("attack", "⚠️ الاستدعاء التلقائي: تهديد على جيوشك، لكن صورة زر «العودة» غير مسجلة بعد — استدعِ الجيوش يدوياً.")
        return True
    if not goto_map(g, sleep, "auto_recall"):
        return True
    img = g.screenshot()
    called = 0
    for k in range(5):
        try:
            st = _march_status(img, k)
        except Exception:
            break
        if st != "gather":
            continue
        g.click_rel(0.983, MARCH_Y0 + MARCH_DY * k + 0.02); sleep(2)
        hit = g.find_image("btn_recall", 0.8)
        if hit:
            g.click_rel(*hit[0]); sleep(1.5)
            called += 1
        else:
            press_key("esc"); sleep(1)
    RECALL_STATE["done"] = now
    if called:
        try:
            stat("recall", called)
        except Exception:
            pass
        log(f"  auto_recall: {called} gathering army(ies) called back to the city (threat seen)")
        notify("attack", f"🏃 الاستدعاء التلقائي: أُعيد {called} جيش جمع إلى المدينة بسبب تهديد. " + _t.strftime("%H:%M", _t.gmtime()) + " UTC")
    else:
        log("  auto_recall: threat seen but no gathering army could be called back")
    return True


SMART["auto_recall"] = auto_recall


# ---------------- alliance center: gifts + territory resources ----------------
def _confirm_popup(g, sleep):
    c = g.find_image("btn_confirm_blue", 0.8)
    if c:
        g.click_rel(*c[0]); sleep(2)


def alliance_center(g, sleep, gifts=True, territory=True):
    """Alliance window (O): Gifts > Rare + Normal > CLAIM ALL; Territory > CLAIM resource earnings."""
    press_key("o"); sleep(3)
    if gifts:
        g.click_rel(0.724, 0.530); sleep(3)                  # Gifts
        for tab in ((0.654, 0.386), (0.515, 0.386)):         # Rare, Normal
            g.click_rel(*tab); sleep(1.5)
            # v184: the claim button through the registry (falls back to the old spot)
            claim = find_element(g, "claim_button")
            g.click_rel(*(claim or (0.755, 0.385))); sleep(3)
            _confirm_popup(g, sleep)
        g.click_rel(0.757, 0.270); sleep(2)                  # close gifts
        log("  alliance_center: alliance gifts claimed")
    if territory:
        g.click_rel(0.596, 0.530); sleep(3)                  # Territory
        c = g.find_image("btn_territory_claim", 0.8)
        if c:
            g.click_rel(*c[0]); sleep(2.5)
            _confirm_popup(g, sleep)
            log("  alliance_center: territory resources claimed")
        g.click_rel(0.758, 0.270); sleep(2)                  # close territory
    g.click_rel(0.758, 0.270); sleep(2)                      # close the alliance window
    return True


SMART["alliance_center"] = alliance_center
SMART["alliance_gifts"] = alliance_center


# ---------------- train troops ----------------
# bottom to top: a selected building shows its buttons BELOW it, so the next (higher) building is never covered
BUILDINGS = {"siege": (0.390, 0.787), "archery": (0.300, 0.668), "stable": (0.206, 0.597), "barracks": (0.137, 0.520)}
TIER_X = {1: 0.493, 2: 0.548, 3: 0.604, 4: 0.659, 5: 0.714}   # tier icons in the training window (y 0.368)


def _go_city(g, sleep):
    if _in_city(g):
        return True
    if _on_map(g):
        press_key("space"); sleep(5)
    return _in_city(g)


CITY_EMPTY = (0.445, 0.500)   # paved road in the middle of the city: clicking it only unselects


def _close_training_window(g, sleep):
    img = g.screenshot()
    if g.find_image("btn_train", 0.8, img=img) or g.find_image("btn_speedup_big", 0.8, img=img):
        g.click_rel(0.748, 0.298); sleep(1.5)


def _unselect(g, sleep):
    g.click_rel(*CITY_EMPTY); sleep(1.2)


# ---------------- v149: buildings by NAME, not by position ----------------
# Every character's city looks different (other buildings, other levels, other spots), so a
# fixed coordinate or a picture of the building only works on the character it was recorded
# on. These helpers read the NAME off the screen instead and remember, per character, where
# the building was found.

BUILDING_WORDS = {
    "barracks": ("barracks", "ثكنات", "الثكنات", "ثكنة"),
    "archery": ("archery range", "archery", "ميدان الرماية", "الرماية", "رماية"),
    "stable": ("stable", "إسطبل", "اسطبل", "الإسطبل"),
    "siege": ("siege workshop", "siege", "ورشة الحصار", "الحصار"),
    "hospital": ("hospital", "المستشفى", "مستشفى"),
    "tavern": ("tavern", "الحانة", "حانة"),
    "market": ("market", "السوق", "سوق"),
    "blacksmith": ("blacksmith", "الحداد", "حداد"),
    "embassy": ("embassy", "السفارة", "سفارة"),
    "alliance_center": ("alliance center", "مركز التحالف"),
    "city_hall": ("city hall", "قاعة المدينة"),
    "watchtower": ("watchtower", "برج المراقبة"),
    "scout_camp": ("scout camp", "scouts camp", "معسكر الكشافة", "الكشافة"),
}

# v159: the game's command list names the TROOP being trained, not the building.
TROOP_TYPE_WORDS = {
    "stable": ("cavalry", "الفرسان", "فرسان"),
    "barracks": ("infantry", "المشاة", "مشاة"),
    "archery": ("archers", "archer", "الرماة", "رماة", "الرماية"),
    "siege": ("siege", "الحصار", "المجانيق"),
}

BUTTON_WORDS = {
    "train": ("train", "تدريب"),
    "upgrade": ("upgrade", "ترقية"),
    "info": ("info", "معلومات"),
    "speedup": ("speedup", "speed up", "تسريع"),
}


def _norm_text(s):
    import re
    return re.sub(r"[^0-9a-z\u0600-\u06ff]+", " ", (s or "").lower()).strip()


UI_REGISTRY_FILE = os.path.join(BASE, "ui_registry.json")
_UI_CACHE = [0.0, {}]


def load_ui_registry():
    """v175: read ui_registry.json (cached until the file changes)."""
    try:
        mtime = os.path.getmtime(UI_REGISTRY_FILE)
    except Exception:
        return {}
    if _UI_CACHE[0] != mtime:
        _UI_CACHE[0] = mtime
        data = load_json(UI_REGISTRY_FILE, {}) or {}
        _UI_CACHE[1] = data.get("elements", {}) or {}
    return _UI_CACHE[1]


def find_icon(g, name, min_scale=0.4, max_scale=2.2, steps=12, threshold=0.70, img=None):
    """v187: find a small icon at any scale (the HUD grows with the game window).

    Returns (x, y, score, scale) in relative coordinates, or None.
    """
    try:
        import cv2
    except Exception:
        return None
    path = os.path.join(BASE, "builtin_templates", name + ".png")
    tpl0 = cv2.imread(path)
    if tpl0 is None:
        log(f"  ! icon template missing: {name}")
        return None
    picture = img if img is not None else g.screenshot()
    h, w = picture.shape[:2]
    best = None
    for i in range(max(2, int(steps))):
        sc = min_scale + (max_scale - min_scale) * i / (max(2, int(steps)) - 1)
        tpl = cv2.resize(tpl0, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_LINEAR)
        if tpl.shape[0] < 10 or tpl.shape[1] < 10 or tpl.shape[0] >= h or tpl.shape[1] >= w:
            continue
        res = cv2.matchTemplate(picture, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if best is None or mx > best[0]:
            best = (float(mx), loc[0] + tpl.shape[1] / 2, loc[1] + tpl.shape[0] / 2, sc)
    if not best or best[0] < threshold:
        return None
    return (best[1] / w, best[2] / h, best[0], best[3])


def find_element(g, name, img=None, threshold=None, allow_fallback=True):
    """v175: locate a button by name using the registry.

    Order: picture template -> OCR label -> relative to another element -> remembered position.
    Returns a relative (x, y) point or None.
    """
    element = load_ui_registry().get(name)
    if not element:
        log(f"  ! ui: '{name}' is not in ui_registry.json")
        return None
    thr = float(threshold if threshold is not None else element.get("threshold", 0.75))

    tpl = element.get("template")
    if tpl and element.get("multiscale"):
        try:
            hit = find_icon(g, tpl, threshold=thr, img=img)
            if hit:
                log(f"  ui: {name} found by icon search at {hit[0]:.3f},{hit[1]:.3f} "
                    f"(score {hit[2]:.2f}, scale {hit[3]:.2f})")
                return (hit[0], hit[1])
        except Exception as e:
            log(f"  ui: {name} icon search failed: {e!r}")
    if tpl and not element.get("multiscale"):
        try:
            picture = img if img is not None else g.screenshot()
            hits = g.find_image(tpl, thr, img=picture)
            if hits:
                hits = sorted(hits, key=lambda p: (p[1], p[0]))
                log(f"  ui: {name} found by picture at {hits[0][0]:.3f},{hits[0][1]:.3f}")
                return (float(hits[0][0]), float(hits[0][1]))
        except Exception as e:
            log(f"  ui: {name} picture lookup failed: {e!r}")

    labels = element.get("ocr_labels") or []
    if labels:
        try:
            picture = img if img is not None else g.screenshot()
            h, w = picture.shape[:2]
            boxes = _ocr_boxes(picture, "ui_%s.png" % name, 1.8)
            hits = _text_hits(boxes, labels)
            if hits:
                x, y, txt = sorted(hits, key=lambda t: (t[1], t[0]))[0]
                log(f"  ui: {name} found by text '{txt}' at {x / w:.3f},{y / h:.3f}")
                return (x / w, y / h)
        except Exception as e:
            log(f"  ui: {name} text lookup failed: {e!r}")

    rel = element.get("relative_to")
    if rel:
        base = find_element(g, rel, img=img, allow_fallback=allow_fallback)
        if base:
            dx, dy = element.get("offset", [0, 0])
            point = (base[0] + float(dx), base[1] + float(dy))
            log(f"  ui: {name} placed next to {rel} at {point[0]:.3f},{point[1]:.3f}")
            return point

    if allow_fallback and element.get("fallback"):
        fb = element["fallback"]
        log(f"  ui: {name} using the remembered position {fb[0]:.3f},{fb[1]:.3f}")
        return (float(fb[0]), float(fb[1]))

    log(f"  ui: {name} not found")
    return None


def _text_hits(boxes, vocab, x_off=0, y_off=0):
    """Centre points of the OCR lines that contain one of these words."""
    out = []
    for x1, y1, x2, y2, txt in boxes:
        t = _norm_text(txt)
        if not t:
            continue
        for w in vocab:
            nw = _norm_text(w)
            if nw and nw in t:
                out.append(((x1 + x2) / 2 + x_off, (y1 + y2) / 2 + y_off, txt))
                break
    return out


def find_button(g, action, img=None):
    """v149: locate a button by its TEXT instead of a fixed offset. Returns a relative point.
    Buttons live in the lower part of a panel, so only that band is read."""
    if img is None:
        img = g.screenshot()
    h, w = img.shape[:2]
    y0 = int(0.30 * h)
    boxes = _ocr_boxes(img[y0:h, :], "btn_%s.png" % action, 3.0)
    hits = _text_hits(boxes, BUTTON_WORDS.get(action, (action,)), 0, y0)
    if not hits:
        return None
    x, y, _txt = sorted(hits, key=lambda t: (t[1], t[0]))[0]
    return (x / w, y / h)


def _building_name_at(g, img, x, y, kinds):
    """v150: read the name written above the point and return which of `kinds` it is (or None).
    One OCR pass can identify any building, which is what learn_city() uses to map a whole city."""
    h, w = img.shape[:2]
    # v150: the name plate is not always tight above the building - read a wider band
    crop = img[max(0, int((y - 0.30) * h)):int((y + 0.12) * h),
               max(0, int((x - 0.30) * w)):min(w, int((x + 0.30) * w))]
    if crop is None or getattr(crop, "size", 0) == 0:
        return None
    # v150: the game window changes size (RDP resolution); aim the OCR at ~1000 px wide
    scale = max(1.2, min(4.0, 1000.0 / max(1, crop.shape[1])))
    txt = " ".join(_ocr_lines(crop, "name_scan.png", scale=round(scale, 1)))
    if not txt.strip():
        return None
    norm = _norm_text(txt)
    for kind in kinds:
        for wd in BUILDING_WORDS.get(kind, (kind,)):
            if _norm_text(wd) and _norm_text(wd) in norm:
                return kind
    return None


def _name_above(g, kind, x, y):
    """True when the label above the spot reads this building. Independent of shape/level/position."""
    return _building_name_at(g, g.screenshot(), x, y, [kind]) == kind


def learn_city(g, sleep, kinds=None):
    """v150: scan the city once and remember EVERY recognised building for this character.

    One pass maps the whole city (name -> spot) instead of one slow scan per building, so the
    next rounds click straight to the right place. Returns {kind: (x, y)}.
    """
    kinds = list(kinds or BUILDING_WORDS)
    found = {}
    log(f"  learning this city: {len(CITY_GRID)} spots, character {_char_key()}")
    for (x, y) in CITY_GRID:
        if not _in_city(g):
            recover_screen(g)
            if not _city_reset(g, sleep):
                break
        g.click_rel(x, y); sleep(1.6)
        try:
            kind = _building_name_at(g, g.screenshot(), x, y, kinds)
        except Exception as e:
            kind = None
            log(f"    (name read failed at {x:.2f},{y:.2f}: {e!r})")
        if kind:
            _bpos(kind, (x, y))
            found[kind] = (x, y)
            log(f"    {kind} -> {x:.2f},{y:.2f}")
        g.click_rel(*CITY_EMPTY); sleep(0.5)
    log(f"  learned {len(found)} building(s) for {_char_key()}: {', '.join(sorted(found)) or '-'}")
    return found


def _building_probe(g, sleep, kind):
    """probe(x, y) for _scan_building: the label above the clicked spot must read this building."""
    def probe(x, y):
        g.click_rel(x, y); sleep(2)
        if _name_above(g, kind, x, y):
            return True
        recover_screen(g)
        return False
    return probe


def find_building(g, sleep, kind, extra=()):
    """v149: click a building by its NAME, because every character's city is laid out differently.

    Order: the spot remembered for THIS character (building_pos.json), the first character's
    layout, `extra`, then one grid scan (rate-limited to once per 6 h by _scan_building).
    Every candidate is verified by reading the name above the building, and a verified spot
    is remembered for this character. Returns (x, y) or None.
    """
    kind = (kind or "").lower()
    spots = []
    mem = _bpos(kind)
    if mem:
        spots.append(tuple(mem))
    if BUILDINGS.get(kind):
        spots.append(tuple(BUILDINGS[kind]))
    spots += [tuple(p) for p in extra if p]
    seen = set()
    for (x, y) in spots:
        key = (round(x, 3), round(y, 3))
        if key in seen:
            continue
        seen.add(key)
        g.click_rel(key[0], key[1]); sleep(2)
        if _name_above(g, kind, key[0], key[1]):
            _bpos(kind, key)
            log(f"  {kind}: recognised by name at {key[0]:.3f},{key[1]:.3f} (character {_char_key()})")
            return key
        recover_screen(g)
    log(f"  - {kind}: not at a remembered spot - scanning the city by name")
    return _scan_building(g, sleep, kind, _building_probe(g, sleep, kind))


def _training_speedup(g, sleep, name, max_items=1):
    """v147: fast training - finish a running training with speedup ITEMS.

    Only speedup items are used, never gems: every 'spend gems' window is refused, and
    when the speedup window is not recognised nothing else is clicked - a screenshot is
    saved to claude_out and the caller carries on. Returns the number of items used.
    """
    from common import BASE, close_gem_dialogs
    img = g.screenshot()
    hexb = g.find_image("btn_speedup_hex", 0.8, img=img)
    if not hexb:
        return 0
    g.click_rel(*hexb[0])
    sleep(2)
    used = 0
    for _ in range(max(0, int(max_items))):
        if close_gem_dialogs(g):
            log("  ! fast training: a 'spend gems' window appeared - pressed NO and stopped")
            break
        img = g.screenshot()
        use = g.find_image("btn_use", 0.82, img=img)
        if not use:
            try:
                import cv2
                cv2.imwrite(os.path.join(BASE, "claude_out", "speed_window_%s.png" % name), img)
            except Exception:
                pass
            log(f"  ! fast training: {name}: the speedup window was not recognised "
                f"(nothing clicked, screenshot saved to claude_out)")
            break
        g.click_rel(*use[0])
        sleep(2)
        used += 1
    img = g.screenshot()
    x = g.find_image("btn_x", 0.8, img=img)
    if x:
        g.click_rel(*x[0])
        sleep(1.5)
    if close_gem_dialogs(g):
        log("  ! fast training: a 'spend gems' window appeared - pressed NO (nothing was spent)")
    return used


def train_troops(g, sleep, tier=4, fast=False, buildings=None, use_bag=False,
                 inf_tier=None, arch_tier=None, cav_tier=None, siege_tier=None):
    """Train troops in every IDLE military building (never INSTANT, never gems).
    v137: each troop type has its own level (infantry / archers / cavalry / siege); 'tier' is the fallback.
    v147: 'fast' (the dashboard's fast-training switch) uses speedup items on a training that is
    already running - one item per building per round, and gems are still never touched."""
    if not _go_city(g, sleep):
        log("  ! train_troops: not in the city view")
        return True
    def _t(v, d):
        return int(v) if str(v).strip().isdigit() and 1 <= int(v) <= 5 else d
    base_tier = _t(tier, 4)
    TIERS_BY = {"barracks": _t(inf_tier, base_tier), "archery": _t(arch_tier, base_tier),
                "stable": _t(cav_tier, base_tier), "siege": _t(siege_tier, base_tier)}
    trained = []
    for name in [b for b in BUILDINGS if b in (buildings or list(BUILDINGS))]:
        if name not in BUILDINGS:
            continue
        _close_training_window(g, sleep)
        # v159: the user's own route - the game's command list, never a city search.
        # Tap "train cavalry" in the list; the game jumps to that building by itself.
        troop_key = QUEUE_ROWS_KEY.get(name, name)
        jumped = queue_goto_unit(g, sleep, troop_key)
        if not jumped:
            # v174: the Queue Overview always lists the four military units, idle or training, so a
            # missing row means the panel was not read - the city scan only made the task slow
            # enough for the 15-minute watchdog to abort it. Skip and let the next round retry.
            log(f"  - train_troops: {name}: the {troop_key} row could not be read - skipped this round")
            continue
        img = g.screenshot()
        if g.find_image("btn_speedup_hex", 0.8, img=img):
            if fast:
                n = _training_speedup(g, sleep, name)
                if n:
                    log(f"  - train_troops: {name} is training - used {n} speedup item(s)")
                else:
                    log(f"  - train_troops: {name} is training - no speedup used")
            else:
                log(f"  - train_troops: {name} is still training, no speedup")
            continue

        # the list sometimes opens the training window itself; otherwise press the train button
        opened = bool(g.find_image("btn_train", 0.8, img=img))
        if not opened:
            tp = find_element(g, "train_button", img=img)
            if tp:
                opened = click_verified(g, tp, sleep, expect="training_window", wait=2.5,
                                        label=f"train_button ({name})")
                log(f"  - train_troops: {name}: pressed the TRAIN button" if opened
                    else f"  - train_troops: {name}: TRAIN was pressed but the window did not open")

        if not opened:
            log(f"  ! train_troops: {name}: the training window did not open from the command list")
            g.click_rel(0.749, 0.299); sleep(1.5)            # close (X) just in case
            continue
        tier = TIERS_BY.get(name, base_tier)
        g.click_rel(TIER_X.get(tier, 0.659), 0.368); sleep(1.5)
        b = g.find_image("btn_train", 0.8)
        if b:
            g.click_rel(*b[0]); sleep(3)
            trained.append(name)
            log(f"  train_troops: {name}: training tier {tier} started")
        if g.find_image("btn_train", 0.8) or not b:          # window still open (e.g. not enough resources)
            try:
                import cv2
                from common import BASE, close_gem_dialogs
                cv2.imwrite(os.path.join(BASE, "claude_out", "train_need_%s.png" % name), g.screenshot())
                close_gem_dialogs(g)
            except Exception:
                pass
            log(f"  ! train_troops: {name}: could not train (resources?) - closing"
                + (" (using bag resources is not learned yet)" if use_bag else ""))
            g.click_rel(0.749, 0.299); sleep(1.5)
    _close_training_window(g, sleep)
    log(f"  train_troops: started in {len(trained)} building(s): {', '.join(trained) or '-'}")
    return True


SMART["train_troops"] = train_troops
SMART["train"] = train_troops


# ---------------- rally on a barbarian fort ----------------
RALLY_STATE = {"stop_until": 0.0}
RALLY_TIME = {5: (0.743, 0.337), 10: (0.876, 0.337), 30: (0.743, 0.373), 480: (0.876, 0.373)}


def _close_panel(g, sleep):
    g.click_rel(0.758, 0.270); sleep(1.5)                   # X of the New Troop / alliance-size windows


def _rally_swap_commanders(g, sleep, primary_commander, secondary_commander=""):
    """v189: pick the rally commanders by name in the troop window. True when the primary was set."""
    if not g.find_image("btn_march", 0.78):
        return False
    g.click_rel(0.33, 0.37); sleep(2.5)                      # primary commander portrait
    if not _pick_commander_in_list(g, sleep, primary_commander, "rp"):
        return False
    if (secondary_commander or "").strip() and g.find_image("btn_march", 0.78):
        g.click_rel(0.405, 0.50); sleep(2.5)                 # secondary commander portrait
        _pick_commander_in_list(g, sleep, secondary_commander, "rs")
    return True


def rally_fort(g, sleep, level=10, preset=1, minutes=5, archers_only=True,
               primary_commander="", secondary_commander="", troop_type="", troops=0):
    """Launch a rally on a Barbarian Fort.

    v189: the dashboard can name the primary and secondary commander, the troop type and the troop
    count (0 = the maximum the commander can lead). Without a commander name the saved loadout
    <preset> is used as before. Never uses AP items or gems."""
    import time as _t
    if not (primary_commander or "").strip():                       # TASK-07: per-task commander preset
        primary_commander, secondary_commander = _preset("rallies")
    if _t.time() < RALLY_STATE["stop_until"]:
        log("  - rally_fort: paused (no action points earlier) - will try again later")
        return True
    if g.find_image("qin_army_icon", 0.75):
        log("  - rally_fort: Qin Shi Huang's army is still out, waiting for it to come back")
        return True
    if _queue_full(g):
        log("  - rally_fort: no free march slot")
        return True
    if not goto_map(g, sleep, "rally_fort"):
        return True
    press_key("f"); sleep(3)
    g.click_rel(0.285, 0.935); sleep(2)                      # Barbarians
    g.click_rel(0.352, 0.651); sleep(2)                      # Barbarian Fort tab
    for _ in range(12):
        g.click_rel(0.204, 0.758); sleep(0.25)               # level down to 1
    for _ in range(max(0, int(level) - 1)):
        g.click_rel(0.394, 0.758); sleep(0.25)               # level up
    g.click_rel(0.298, 0.820); sleep(4)                      # SEARCH
    r = g.find_image("btn_rally", 0.8)
    if not r:
        log("  ! rally_fort: no level %s fort found right now (RALLY button missing)" % level)
        back = g.find_image("btn_back", 0.8)
        if back:
            g.click_rel(*back[0]); sleep(2)
        return True
    g.click_rel(*r[0]); sleep(3)
    g.click_rel(*RALLY_TIME.get(int(minutes), RALLY_TIME[5])); sleep(1)
    g.click_rel(0.815, 0.419); sleep(3)                      # RALLY (prep time chosen)
    if not g.find_image("btn_march", 0.78):
        log("  ! rally_fort: troop window did not open (out of action points?) - stopping rallies for 1 hour, no AP items used")
        RALLY_STATE["stop_until"] = _t.time() + 3600
        press_key("esc"); sleep(1.5)
        return True
    g.click_rel(0.752, 0.468 + (int(preset) - 1) * 0.0396); sleep(2)   # loadout <preset>
    if (primary_commander or "").strip():
        # v189: the user chose the commanders - swap them in instead of checking for Qin Shi Huang
        if not _rally_swap_commanders(g, sleep, primary_commander, secondary_commander):
            log("  ! rally_fort: could not change the commanders - keeping loadout %s" % preset)
    elif not g.find_image("qin_face", 0.72):
        log("  ! rally_fort: the commander is not Qin Shi Huang - rally cancelled")
        try:
            import cv2
            from common import BASE
            cv2.imwrite(os.path.join(BASE, "claude_out", "rf_not_qin.png"), g.screenshot())
        except Exception:
            pass
        _close_panel(g, sleep)
        press_key("space"); sleep(4)
        return True
    if (troop_type or "").strip() and g.find_image("btn_march", 0.78):
        _set_troop_type(g, sleep, troop_type, troops)
    if archers_only and not g.find_image("archer_check_on", 0.85):
        g.click_rel(0.652, 0.317); sleep(1.5)                # archers only
    m = g.find_image("btn_march", 0.78)
    g.click_rel(*(m[0] if m else (0.656, 0.696))); sleep(3)
    if g.find_image("btn_march", 0.78):
        log("  ! rally_fort: MARCH did not go (action points?) - stopping rallies for 1 hour, no AP items used")
        RALLY_STATE["stop_until"] = _t.time() + 3600
        _close_panel(g, sleep)
    else:
        try:
            stat("rally")
        except Exception:
            pass
        log(f"  rally_fort: rally launched on a level {level} fort with Qin Shi Huang (archers, {minutes} min)")
    if _on_map(g):
        press_key("space"); sleep(4)
    return True


SMART["rally_fort"] = rally_fort


# ---------------- read resources + gems from the top bar ----------------
RES_NAMES = ["food", "wood", "stone", "gold", "gems"]


def _parse_amount(tok):
    import re
    m = re.match(r"^(\d+(?:[.,]\d+)?)([KMBkmb]?)$", tok)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return int(v * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2).upper()])


def _bar_image(img):
    """The 5 values of the resource bar, each cut out (icons removed), enlarged and stacked as text lines."""
    import cv2, numpy as np
    h, w = img.shape[:2]
    if w != 946:
        img = cv2.resize(img, (946, int(h * 946 / w)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
    bar = cv2.cvtColor(img[0:int(h * 0.035), int(w * 0.655):int(w * 0.985)], cv2.COLOR_BGR2GRAY)
    lines = []
    for k in range(5):
        seg = bar[:, k * 63 + 24:k * 63 + 64]
        if seg.shape[1] < 40:
            seg = cv2.copyMakeBorder(seg, 0, 0, 0, 40 - seg.shape[1], cv2.BORDER_REPLICATE)
        seg = cv2.resize(seg, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
        seg = 255 - cv2.normalize(seg, None, 0, 255, cv2.NORM_MINMAX)
        lines.append(cv2.copyMakeBorder(seg, 30, 30, 40, 40, cv2.BORDER_CONSTANT, value=255))
    return np.vstack(lines)


def _clean_amount(line, plain=False):
    """'284.4M' -> 284400000. plain=True (gems): digits only, no unit."""
    import re
    t = line.replace(" ", "").replace(",", ".").replace("O", "0").replace("o", "0")
    if plain:
        d = re.sub(r"[^0-9]", "", t)
        return int(d) if d else None
    for _ in range(4):
        t = re.sub(r"(?<=[\d.S$])[S$]|[S$](?=[\d.S$])", "8", t)   # 'S' is a misread 8 here
    t = re.sub(r"(?<=[\d.])[Il|]", "1", t)
    t = re.sub(r"(\d\.\d)(14|1A|IVI|lVl|N1|H)$", r"\1M", t)    # common misreads of M
    m = re.search(r"(\d+(?:\.\d+)?)([KMB])?", t)
    if not m:
        return None
    num, unit = m.group(1), m.group(2)
    if unit and "." not in num and len(num) == 4:
        num = num[:3] + "." + num[3:]                               # '8544M' -> '854.4M' (dot not read)
    return int(float(num) * {None: 1, "K": 1e3, "M": 1e6, "B": 1e9}[unit])


def read_resources(g, sleep=None):
    """OCR the resource bar (Windows built-in OCR). Updates control.RESOURCES and returns the dict."""
    import cv2, subprocess, time as _t
    from common import BASE
    img = g.screenshot()
    path = os.path.join(BASE, "claude_out", "res_bar.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, _bar_image(img))
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            os.path.join(BASE, "ocr.ps1"), path],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=40, creationflags=0x08000000)
        out, err = r.stdout, r.stderr
    except Exception as e:
        log(f"  ! read_resources: OCR failed: {e!r}")
        return {}
    if "NO_OCR_ENGINE" in out:
        log("  ! read_resources: Windows OCR is not available on this server")
        return {}
    lines = [l.strip() for l in out.splitlines() if l.strip() and any(c.isdigit() for c in l)]
    vals = [_clean_amount(l if i != 4 else (l.split() or [l])[0], plain=(i == 4)) for i, l in enumerate(lines)]   # gems: first number only
    vals = [v for v in vals if v is not None]
    if len(vals) == 5:
        big = [v for v in vals[:4] if v >= 1000]
        unit = 1e6 if big and min(big) >= 1e6 else 1e3 if big else 1e6
        vals = [int(v * unit) if i < 4 and v < 1000 else v for i, v in enumerate(vals)]   # unit lost by OCR
        res = dict(zip(RES_NAMES, vals))
        res["read_at"] = _t.strftime("%Y-%m-%d %H:%M")
        res["ocr"] = " | ".join(lines)[:120]
        import control
        control.RESOURCES.clear(); control.RESOURCES.update(res)
        try:
            _gem_day(gems_now=res.get("gems"))
        except Exception:
            pass
        try:
            _stats_resources(res)
        except Exception as e:
            log(f"  ! stats: {e!r}")
        log("  resources: " + ", ".join(f"{k} {res[k]:,}" for k in RES_NAMES) + f"   (OCR: {res['ocr']})")
        return res
    log(f"  ! read_resources: could not read the bar (OCR lines: {lines[:6]} {err.strip()[:120]})")
    return {}


# ---------------- v105: day stats (30-day history), notifications, Telegram push ----------------
STAT_KEYS = ("food", "wood", "stone", "gold", "gems", "barb", "rally", "rally_join", "mail", "recall")


def _stats_load():
    import json
    from common import BASE
    try:
        return json.load(open(os.path.join(BASE, "stats_days.json"), encoding="utf-8"))
    except Exception:
        return {"days": {}, "last_res": {}, "notes": []}


def _stats_save(d):
    import json, control
    from common import BASE
    days = d.setdefault("days", {})
    for k in sorted(days)[:-30]:
        days.pop(k, None)
    d["notes"] = d.get("notes", [])[-60:]
    json.dump(d, open(os.path.join(BASE, "stats_days.json"), "w", encoding="utf-8"), ensure_ascii=False)
    control.CITY["history"] = [dict(day=k, **days[k]) for k in sorted(days)]
    control.CITY["notes"] = d["notes"][-40:]


def _today():
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


RELOGIN = [0]                 # GUIDE-13: time the "logged in on another device" dialog was seen
CAPTCHA_SCAN = [0.0, 0.0]     # TASK-09: last template check, last OCR check


def captcha_visible(g, force=False):
    """TASK-09: True when the game shows a verification (captcha) window. Templates named captcha*.png
    (templates/ or builtin_templates/) are checked every 10 s; the centre of the screen is read by OCR every 2 min
    (or at once with force=True). Never clicks."""
    import time as _t, re as _re, glob
    now = _t.time()
    if not force and now - CAPTCHA_SCAN[0] < 10:
        return False
    CAPTCHA_SCAN[0] = now
    try:
        img = g.screenshot()
    except Exception:
        return False
    from common import TEMPL_DIR, BUILTIN_DIR
    names = {os.path.splitext(os.path.basename(f))[0] for d in (TEMPL_DIR, BUILTIN_DIR) for f in glob.glob(os.path.join(d, "captcha*.png"))}
    for n in sorted(names):
        try:
            if g.find_image(n, 0.82, img=img):
                log(f"  captcha: template {n} found")
                return True
        except Exception:
            pass
    if not force and now - CAPTCHA_SCAN[1] < 120:
        return False
    CAPTCHA_SCAN[1] = now
    try:
        h, w = img.shape[:2]
        txt = " ".join(_ocr_lines(img[int(0.12 * h):int(0.55 * h), int(0.25 * w):int(0.75 * w)], "captcha_ocr.png", scale=1.6))
    except Exception:
        return False
    if _re.search(r"another device|other device|logged in elsewhere|account.{0,20}(?:logged|signed) in", txt, _re.I):
        log(f"  relogin: 'another device' on screen {txt[:100]!r}")
        RELOGIN[0] = now                                     # GUIDE-13: handled by bot.relogin_wait
        return False
    hits = _re.findall(r"verif\w*|captcha|human|robot|puzzle|slide to|security check", txt, _re.I)
    if len(set(x.lower()[:6] for x in hits)) >= 2 or _re.search(r"verification|captcha", txt, _re.I):
        log(f"  captcha: text on screen {txt[:120]!r}")
        return True
    return False


def notify(kind, text, d=None):
    """Dashboard notification (+ Telegram). kind: attack / mail / day / barb / rally / info."""
    import time as _t
    own = d is None
    d = _stats_load() if own else d
    d.setdefault("notes", []).append({"t": _t.strftime("%Y-%m-%d %H:%M"), "utc": _t.strftime("%H:%M", _t.gmtime()),
                                      "kind": kind, "text": text})
    if own:
        _stats_save(d)
    log(f"  NOTIFY [{kind}] {text}")
    try:
        import telegram_link
        telegram_link.notify(("🚨 " if kind == "attack" else "✉️ " if kind == "mail" else "📊 " if kind == "day" else "🔔 ") + text)
    except Exception:
        pass


def _day_summary(day, rec):
    names = {"food": "طعام", "wood": "خشب", "stone": "حجر", "gold": "ذهب", "gems": "جواهر"}
    parts = [f"{names[k]} {int(rec.get(k, 0)):,}" for k in names]
    return (f"ملخص يوم {day}: " + " · ".join(parts) +
            f" | برابرة: {int(rec.get('barb', 0))} · حصون: {int(rec.get('rally', 0))} + انضمام {int(rec.get('rally_join', 0))}")


def stat(key, n=1, d=None):
    """Add n to today's counter (UTC game day). Sends yesterday's summary when a new day starts."""
    own = d is None
    d = _stats_load() if own else d
    days = d.setdefault("days", {})
    day = _today()
    if day not in days:
        prev = sorted(days)[-1] if days else None
        days[day] = {k: 0 for k in STAT_KEYS}
        if prev:
            notify("day", _day_summary(prev, days[prev]), d)
    days[day][key] = days[day].get(key, 0) + n
    if own:
        _stats_save(d)
    return d


def _stats_resources(res):
    """Gains = positive steps between two readings of the resource bar (gathering, collecting, rewards).
    Spending is not counted. Odd OCR jumps (more than +60% at once) are ignored."""
    d = _stats_load()
    last = d.get("last_res", {})
    for k in ("food", "wood", "stone", "gold"):
        v, old = res.get(k), last.get(k)
        if v is None:
            continue
        if old and v > old and v - old <= 0.6 * old:
            stat(k, v - old, d)
        last[k] = v
    d["last_res"] = last
    stat("gems", 0, d)
    try:
        import control
        gt = control.CITY.get("gems_today")
        if gt is not None:
            d["days"][_today()]["gems"] = int(gt)
    except Exception:
        pass
    _stats_save(d)


SMART["read_resources"] = read_resources


# ---------------- alliance rallies page (two blue flags) - probe for learning ----------------
def _open_war_page(g, sleep, quiet=False):
    """Click the TWO-FLAGS icon (alliance war / rallies). It only shows while rallies exist,
    and its place moves when other icons appear."""
    w = g.find_image("icon_war", 0.75)
    if not w:
        if not quiet:
            log("  - join_rally: no alliance rally right now (two-flags icon not shown)")
        return False
    g.click_rel(*w[0]); sleep(2.5)
    return True


def rally_probe(g, sleep):
    """Open the alliance war/rallies page, save a picture of it (claude_out/rp_*.png, last 30), close it."""
    import cv2, glob, time as _t
    from common import BASE
    if not (g.find_image("space_on_city", 0.75) or g.find_image("space_on_map", 0.75)):
        return True
    if not _open_war_page(g, sleep):
        return True
    img = g.screenshot()
    out = os.path.join(BASE, "claude_out"); os.makedirs(out, exist_ok=True)
    cv2.imwrite(os.path.join(out, f"rp_{_t.strftime('%m%d_%H%M%S')}.png"), img)
    for f in sorted(glob.glob(os.path.join(out, "rp_*.png")))[:-30]:
        try: os.remove(f)
        except Exception: pass
    x = g.find_image("btn_x", 0.85, img=img)
    g.click_rel(*(x[0] if x else (0.757, 0.269))); sleep(1.5)        # X
    return True


SMART["rally_probe"] = rally_probe


# ---------------- join alliance rallies on barbarian forts ----------------
def _ocr_image(img_bgr, name="ocr_tmp.png", variants=("bin", "plain", "bin2")):
    """Windows OCR on a small text crop. Tries a few clean-ups; returns the first non-empty text."""
    import cv2, subprocess
    from common import BASE
    g0 = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    for v in variants:
        if v == "raw":
            g = g0
            path = os.path.join(BASE, "claude_out", name)
            cv2.imwrite(path, g)
            try:
                r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                    os.path.join(BASE, "ocr.ps1"), path],
                                   capture_output=True, encoding="utf-8", errors="replace", timeout=40, creationflags=0x08000000)
                txt = r.stdout.strip()
            except Exception:
                txt = ""
            if any(c.isdigit() for c in txt):
                return txt
            continue
        g = cv2.resize(g0, None, fx=3 if v != "bin2" else 5, fy=3 if v != "bin2" else 5, interpolation=cv2.INTER_CUBIC)
        g = 255 - cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX)
        if v.startswith("bin"):
            _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        g = cv2.copyMakeBorder(g, 40, 40, 60, 60, cv2.BORDER_CONSTANT, value=255)
        path = os.path.join(BASE, "claude_out", name)
        cv2.imwrite(path, g)
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                os.path.join(BASE, "ocr.ps1"), path],
                               capture_output=True, encoding="utf-8", errors="replace", timeout=40, creationflags=0x08000000)
            txt = " ".join(r.stdout.split())
        except Exception:
            txt = ""
        if any(c.isdigit() for c in txt):
            return txt
    return ""


def _rally_amount(text):
    """'Rallied Army Capacity: 210,682/2,000,000' -> 210682 (None if not readable)."""
    import re
    t = text.replace(" ", "").replace(".", ",").replace("O", "0").replace("o", "0").replace("I", "/").replace("|", "/")
    m = re.search(r"(\d[\d,]*)/(\d[\d,]*)", t) or re.search(r"(\d[\d,]{2,})()", t)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


DIGIT_T = {"0": [[15.9, 187.2, 255.0, 183.2, 0.0], [183.3, 243.1, 135.5, 255.0, 159.4], [207.2, 167.4, 0.0, 151.5, 255.0], [255.0, 159.5, 0.0, 135.6, 255.0], [207.2, 175.4, 8.0, 179.4, 239.1], [183.3, 237.1, 195.3, 255.0, 151.4], [0.0, 135.4, 255.0, 167.2, 0.0]], "1": [[85.0, 212.3, 212.7, 127.3, 0.0], [170.0, 233.7, 255.0, 191.0, 0.0], [0.0, 127.3, 212.7, 191.0, 0.0], [0.0, 127.3, 212.7, 191.0, 0.0], [0.0, 127.3, 212.7, 191.0, 0.0], [170.0, 233.7, 255.0, 233.7, 170.0], [255.0, 255.0, 255.0, 233.7, 170.0]], "2": [[218.6, 245.9, 255.0, 200.1, 36.4], [255.0, 91.3, 146.1, 255.0, 255.0], [0.0, 0.0, 109.7, 227.7, 255.0], [0.0, 0.0, 128.0, 209.3, 72.9], [0.0, 191.0, 255.0, 191.0, 0.0], [255.0, 255.0, 236.9, 218.6, 218.6], [255.0, 255.0, 255.0, 255.0, 255.0]], "3": [[255.0, 255.0, 255.0, 255.0, 255.0], [0.0, 0.0, 128.0, 255.0, 255.0], [0.0, 0.0, 128.0, 255.0, 255.0], [0.0, 191.0, 255.0, 255.0, 255.0], [0.0, 0.0, 128.0, 255.0, 255.0], [255.0, 255.0, 255.0, 255.0, 255.0], [0.0, 191.0, 255.0, 191.0, 0.0]], "4": [[0.0, 0.0, 255.0, 255.0, 255.0], [0.0, 0.0, 255.0, 255.0, 255.0], [0.0, 255.0, 255.0, 255.0, 255.0], [0.0, 255.0, 0.0, 255.0, 255.0], [255.0, 255.0, 255.0, 255.0, 255.0], [0.0, 0.0, 0.0, 255.0, 255.0], [0.0, 0.0, 0.0, 0.0, 255.0]], "5": [[127.5, 223.0, 255.0, 255.0, 255.0], [255.0, 255.0, 191.5, 127.5, 127.5], [255.0, 255.0, 191.5, 95.5, 0.0], [127.5, 127.5, 191.5, 255.0, 255.0], [0.0, 0.0, 0.0, 64.0, 255.0], [255.0, 159.5, 127.5, 159.5, 255.0], [127.5, 223.0, 255.0, 223.0, 127.5]], "6": [[0.0, 229.4, 255.0, 242.2, 153.0], [153.0, 255.0, 76.6, 51.0, 51.0], [255.0, 178.6, 76.6, 140.2, 0.0], [255.0, 255.0, 255.0, 255.0, 204.0], [204.0, 178.6, 0.0, 178.6, 255.0], [153.0, 255.0, 229.6, 216.8, 204.0], [0.0, 76.4, 255.0, 191.2, 51.0]], "8": [[0.0, 255.0, 255.0, 255.0, 0.0], [0.0, 255.0, 0.0, 255.0, 255.0], [0.0, 255.0, 255.0, 255.0, 0.0], [0.0, 255.0, 255.0, 255.0, 0.0], [255.0, 255.0, 0.0, 255.0, 255.0], [0.0, 255.0, 255.0, 255.0, 255.0], [0.0, 0.0, 255.0, 255.0, 0.0]]}


def _rally_count(img, fx, fy):
    """Troops already in a rally row: digits before the '/' of 'Rallied Army Capacity: N/M'.
    Rebuilds the digits without commas and reads them with Windows OCR (template fallback)."""
    import cv2, numpy as np, re
    h, w = img.shape[:2]
    x1, x2 = int((fx - 0.130) * w), int((fx - 0.018) * w)
    y1, y2 = int((fy + 0.022) * h), int((fy + 0.046) * h)
    crop = img[max(0, y1):y2, max(0, x1):x2]
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sc = 946.0 / w
    _, b = cv2.threshold(g, 170, 255, cv2.THRESH_BINARY)
    n, lab, st, cen = cv2.connectedComponentsWithStats(b)
    comps = []
    for i in range(1, n):
        x, y, ww, hh, a = st[i]
        hh2 = hh * sc
        if hh2 >= 8:
            comps.append((x, "/", None))
        elif hh2 >= 6:
            comps.append((x, "d", (x, y, ww, hh)))
    comps.sort(key=lambda t: t[0])
    digits = []
    for x, k, box in comps:
        if k == "/":
            break
        digits.append(box)
    if not digits or len(digits) > 8:
        return None
    # template guess
    guess = ""
    for (x, y, ww, hh) in digits:
        gl = cv2.resize(b[y:y + hh, x:x + ww], (5, 7), interpolation=cv2.INTER_AREA).astype(float)
        guess += min(DIGIT_T, key=lambda d: np.abs(np.array(DIGIT_T[d]) - gl).sum())
    # OCR on the rebuilt digits (no commas)
    ch = max(bb[3] for bb in digits)
    canvas = np.full((ch + 4, sum(bb[2] + 2 for bb in digits) + 4), int(np.median(g)), np.uint8)
    cx = 2
    for (x, y, ww, hh) in digits:
        canvas[2:2 + hh, cx:cx + ww] = g[y:y + hh, x:x + ww]
        cx += ww + 2
    big = cv2.resize(canvas, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    big = 255 - cv2.normalize(big, None, 0, 255, cv2.NORM_MINMAX)
    line = cv2.copyMakeBorder(big, 30, 30, 40, 40, cv2.BORDER_CONSTANT, value=255)
    txt = _ocr_image(cv2.cvtColor(np.vstack([line, line]), cv2.COLOR_GRAY2BGR), "jr_cap.png", variants=("raw",))
    d = re.sub(r"[^0-9]", "", (txt.split() or [""])[0].replace("O", "0").replace("S", "8"))
    if len(d) != len(digits):
        log(f"    (rally count: OCR '{txt[:20]}' not usable, template guess {guess})")
        d = guess
    else:
        log(f"    (rally count read by OCR: {d})")
    try:
        return int(d)
    except ValueError:
        return None


JOINED = {}     # fort row key -> time, to avoid joining the same rally twice


def _march_minutes(g, mx, my):
    """TASK-03: the march time shown next to MARCH (h:mm:ss / mm:ss) in minutes, or None if not readable."""
    import re
    img = g.screenshot()
    h, w = img.shape[:2]
    crop = img[max(0, int((my - 0.09) * h)):min(h, int((my + 0.03) * h)), max(0, int((mx - 0.30) * w)):min(w, int((mx + 0.08) * w))]
    try:
        t = " ".join(b[4] for b in _ocr_boxes(crop, "jr_time.png", scale=2.0))
    except Exception:
        return None
    m = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", t) or re.search(r"(?<!\d)()(\d{1,2}):(\d{2})(?!\d)", t)
    if not m:
        return None
    hh = int(m.group(1) or 0)
    return hh * 60 + int(m.group(2)) + int(m.group(3)) / 60.0


def join_rally(g, sleep, max_troops=600000, max_armies=2, quiet=False, min_ap_reserve=0, max_march_time_minutes=0,
               target_types="forts", commander_preset=0):
    """War page (two blue flags) -> rallies on 'Barbarian Fort' only -> skip if the rally already has
    max_troops or more -> JOIN -> MARCH with the troops the game selects. Never uses AP items or gems.
    TASK-03: min_ap_reserve = do not join when the last action-points reading (governor profile) is at or below it
    (AP items are never used); max_march_time_minutes = back out when the march would take longer (0 = any);
    target_types: "forts" (barbarian forts - the only type the bot can recognise for now); commander_preset is
    kept for the task-presets feature (TASK-07)."""
    import cv2, time as _t
    import control
    from common import BASE
    try:
        res_ap, ap = int(min_ap_reserve or 0), control.CITY.get("ap") or {}
        if res_ap and ap.get("max") and int(ap.get("cur", 0)) <= res_ap:
            if not quiet:
                log(f"  - join_rally: action points {ap.get('cur')}/{ap.get('max')} at or below the reserve {res_ap} - not joining")
            return True
    except Exception:
        pass
    if not g.find_image("icon_war", 0.75):
        if not quiet:
            log("  - join_rally: no alliance rally right now (two-flags icon not shown)")
        return True
    if _queue_full(g):
        if not quiet:
            log("  - join_rally: no free march slot")
        return True
    if not (g.find_image("space_on_city", 0.75) or g.find_image("space_on_map", 0.75)):
        recover_screen(g)
    joined = 0
    for _ in range(int(max_armies)):
        if not _open_war_page(g, sleep, quiet=True):
            break
        img = g.screenshot()
        h, w = img.shape[:2]
        cv2.imwrite(os.path.join(BASE, "claude_out", "jr_page.png"), img)
        forts = g.find_image("txt_barb_fort", 0.85, img=img)
        target = None
        for fx, fy in sorted(forts, key=lambda p: p[1]):
            x1, x2 = int((fx - 0.130) * w), int((fx - 0.018) * w)          # numbers only
            y1, y2 = int((fy + 0.027) * h), int((fy + 0.045) * h)
            # progress bar colour: green = preparing (can join), orange = already marching
            bx, by = int((fx - 0.200) * w), int((fy + 0.054) * h)
            b, gg, r = [int(v) for v in img[min(by, h - 1), max(bx, 0)]]
            if not (gg > r + 20 and gg > b):
                continue
            amount = _rally_count(img, fx, fy)
            txt = str(amount)
            key = f"{fx:.2f},{fy:.2f}"
            if amount is None:
                log(f"  - join_rally: fort rally found but troop count not readable ('{txt[:40]}') - skipped")
                continue
            if amount >= int(max_troops):
                if not quiet or True:
                    log(f"  - join_rally: fort rally already has {amount:,} troops (limit {int(max_troops):,}) - skipped")
                continue
            if _t.time() - JOINED.get(key + txt[:12], 0) < 300:
                continue
            target = (fx, fy, amount, key + txt[:12])
            break
        if not target:
            if not forts and not quiet:
                log("  - join_rally: rallies exist but none on a barbarian fort")
            x = g.find_image("btn_x", 0.85, img=img)
            g.click_rel(*(x[0] if x else (0.757, 0.269))); sleep(1.5)   # X of the war page
            break
        fx, fy, amount, key = target
        g.click_rel(fx + 0.002, fy + 0.055); sleep(3)            # JOIN (+)
        cv2.imwrite(os.path.join(BASE, "claude_out", "jr_after_join.png"), g.screenshot())
        tj = g.find_image("btn_tap_join", 0.8)               # War Details: "Tap to Join"
        if tj:
            g.click_rel(*tj[0]); sleep(3)
            cv2.imwrite(os.path.join(BASE, "claude_out", "jr_after_tap.png"), g.screenshot())
        nt = g.find_image("btn_new_troop", 0.8)
        if nt:
            g.click_rel(*nt[0]); sleep(2.5)
            _apply_preset(g, sleep, "rallies")                       # TASK-07
        m = g.find_image("btn_march", 0.78)
        if m and int(max_march_time_minutes or 0) > 0:
            mins = _march_minutes(g, *m[0])
            if mins is not None and mins > int(max_march_time_minutes):
                log(f"  - join_rally: march would take {mins:.1f} min (limit {int(max_march_time_minutes)}) - not joining")
                JOINED[key] = _t.time()
                recover_screen(g)
                break
            if mins is not None:
                log(f"    join_rally: march time {mins:.1f} min")
        m = g.find_image("btn_march", 0.78)
        if not m:
            log("  ! join_rally: could not join this rally (own rally, already marching, full or no AP) - skipping it")
            JOINED[key] = _t.time()
            cv2.imwrite(os.path.join(BASE, "claude_out", "jr_fail.png"), g.screenshot())
            recover_screen(g)
            break
        g.click_rel(*m[0]); sleep(3)
        if g.find_image("btn_march", 0.78):
            log("  ! join_rally: MARCH did not go - stopping")
            cv2.imwrite(os.path.join(BASE, "claude_out", "jr_fail.png"), g.screenshot())
            recover_screen(g)
            break
        JOINED[key] = _t.time()
        joined += 1
        try:
            stat("rally_join")
        except Exception:
            pass
        log(f"  join_rally: joined a barbarian fort rally (it had {amount:,} troops)")
        recover_screen(g)
        if _queue_full(g):
            break
    if joined or not quiet:
        log(f"  join_rally: {joined} army(ies) joined fort rallies")
    return True


SMART["join_rally"] = join_rally


# ---------------- VIP chests + daily objectives ----------------
def vip_chests(g, sleep):
    """VIP window: daily VIP-points chest (top right) + 'FREE EVERY DAY' chest. Never the paid offer."""
    g.click_rel(0.075, 0.046); sleep(3)                       # VIP badge
    g.click_rel(0.705, 0.385); sleep(3)                       # daily points chest (CLAIM)
    g.click_rel(0.5, 0.15); sleep(1.5)                        # close the reward card (inside VIP window area is safe)
    c = g.find_image("btn_claim_green", 0.8)
    if c and c[0][0] > 0.6:
        g.click_rel(*c[0]); sleep(3)
        g.click_rel(0.5, 0.15); sleep(1.5)
        log("  vip_chests: free daily VIP chest claimed")
    recover_screen(g)
    log("  vip_chests: done")
    return True


def daily_objectives(g, sleep):
    """Daily Objectives: CLAIM every finished objective, then open the activity chests (20..100)."""
    g.click_rel(0.017, 0.195); sleep(3)
    n = 0
    for _ in range(10):
        c = g.find_image("btn_claim_obj", 0.8)
        if not c:
            break
        g.click_rel(*c[0]); sleep(2.5)
        n += 1
    for x in (0.349, 0.442, 0.541, 0.632, 0.724):            # activity chests 20/40/60/80/100
        g.click_rel(x, 0.380); sleep(2)
        c = g.find_image("btn_claim_green", 0.8) or g.find_image("btn_claim_obj", 0.8)
        if c and 0.35 < c[0][1] < 0.75 and 0.3 < c[0][0] < 0.7:
            g.click_rel(*c[0]); sleep(2.5)
        g.click_rel(0.47, 0.30); sleep(1)                    # close a chest card (title bar of the window)
    log(f"  daily_objectives: {n} objective reward(s) claimed, chests checked")
    recover_screen(g)
    return True


SMART["vip_chests"] = vip_chests
SMART["daily_objectives"] = daily_objectives
SMART["daily_rewards"] = daily_objectives


def probe_screens(g, sleep, save):
    """Take screenshots of the screens Claude needs to build the next smart activity (gather).
    save(name, path) uploads each picture. Only presses Space (map/city) and F (search)."""
    tmp = tempfile.gettempdir()
    from control import take_screenshot

    def shot(name):
        p = take_screenshot(os.path.join(tmp, f"kingbot_{name}.jpg"))
        if p:
            save(name, p)

    g.focus()
    shot("probe_1_city")
    press_key("space"); sleep(5)
    shot("probe_2_map")
    press_key("f"); sleep(3)
    shot("probe_3_search")
    press_key("esc"); sleep(2)
    shot("probe_4_after_esc")
    press_key("space"); sleep(5)
    shot("probe_5_back")
    log("Probe screenshots sent.")


# ---------------- alliance technology donation (v57) ----------------
def alliance_tech(g, sleep, max_donations=20):
    """Alliance (O) > Technology > officer-recommended skill > blue DONATE (resources) until chances run out.
    The orange DONATE button costs gems and is never pressed."""
    from common import close_gem_dialogs
    import queue_manager
    rec = None
    if queue_manager.tap_row(g, sleep, "donate"):           # v197: Queue Overview > Alliance Donations
        rec = g.find_image("officer_rec", 0.8)
        if not rec and not [p for p in g.find_image("btn_donate_res", 0.85) if p[0] > 0.6]:
            recover_screen(g)
    if not rec and not [p for p in g.find_image("btn_donate_res", 0.85) if p[0] > 0.6]:
        press_key("o"); sleep(3)
        g.click_rel(0.532, 0.645); sleep(3)                  # Technology
        rec = g.find_image("officer_rec", 0.8)
    if rec:
        g.click_rel(rec[0][0], rec[0][1] + 0.03); sleep(3)   # recommended skill card
    else:
        g.click_rel(0.29, 0.44); sleep(3)                    # first skill card
    done = 0
    for _ in range(int(max_donations)):
        img = g.screenshot()
        b = g.find_image("btn_donate_res", 0.85, img=img)
        b = [p for p in b if p[0] > 0.6]
        if not b:
            break
        h, w = img.shape[:2]
        px = img[int(b[0][1] * h), int(b[0][0] * w)]
        if not (int(px[0]) > int(px[2]) + 60):             # button not blue (greyed - no chances left)
            break
        g.click_rel(*b[0]); sleep(1.3)
        if close_gem_dialogs(g):                            # gems must never be spent
            log("  ! alliance_tech: a gem window appeared - answered NO and stopped")
            break
        done += 1
    if not done:
        try:
            import cv2
            from common import BASE
            cv2.imwrite(os.path.join(BASE, "claude_out", "at_none.png"), g.screenshot())
        except Exception:
            pass
    log(f"  alliance_tech: {done} donation(s) made with resources" if done else
        "  - alliance_tech: no donation chances left right now - will try later")
    recover_screen(g); sleep(1)
    recover_screen(g)
    return True


SMART["alliance_tech"] = alliance_tech


# ---------------- attack barbarians (v59, step 1: search + troop window) ----------------
BARB_STATE = {"stop_until": 0}


def _barb_find_attack(g):
    import cv2
    from common import BASE
    img = g.screenshot()
    try:
        cv2.imwrite(os.path.join(BASE, "claude_out", "ba_search.png"), img)
    except Exception:
        pass
    a = g.find_image("btn_attack_red", 0.75, img=img)
    return a[0] if a else None


def _barb_search(g, sleep, lo, hi):
    """Open the barbarian search at level <hi>; if nothing comes up (level not unlocked / none near),
    step down one level inside the panel and search again, down to <lo>. Returns (attack_pos, level)."""
    for attempt in range(2):
        press_key("f"); sleep(3)
        g.click_rel(0.285, 0.935); sleep(2)                  # Barbarians icon
        g.click_rel(0.245, 0.649); sleep(1.5)                # Barbarians tab (not Fort)
        if g.find_image("barb_tab_on", 0.85):
            break
        import cv2
        from common import BASE
        cv2.imwrite(os.path.join(BASE, "claude_out", "ba_nopanel%d.png" % attempt), g.screenshot())
        recover_screen(g); sleep(2)
    else:
        log("  ! attack_barbarians: the barbarian search panel did not open")
        return None, int(hi)
    for _ in range(60):
        g._click_absolute(0.204, 0.758); sleep(0.08)         # level down to 1 (fast clicks inside the panel)
    for _ in range(max(0, int(hi) - 1)):
        g._click_absolute(0.394, 0.758); sleep(0.12)         # level up
    lvl = int(hi)
    while True:
        sleep(0.8)
        g.click_rel(0.299, 0.821); sleep(3.5)                # SEARCH
        pos = _barb_find_attack(g)
        if pos:
            return pos, lvl
        if lvl <= int(lo) or not g.find_image("btn_back", 0.8):
            return None, lvl
        log(f"    no level {lvl} barbarian came up, trying {lvl - 1}")
        g._click_absolute(0.204, 0.758); lvl -= 1              # one level down, panel still open


def _barb_shot(g, name):
    try:
        import cv2
        from common import BASE
        cv2.imwrite(os.path.join(BASE, "claude_out", name), g.screenshot())
    except Exception:
        pass


def _queue_cards(g, img=None):
    """Armies in the right-hand 'Queue n/5' column that opens after ATTACK.
    Returns [(x, y, gathering)] relative - card centre and whether its status icon is green (gathering)."""
    import cv2
    img = g.screenshot() if img is None else img
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    colv = hsv[int(0.26 * h):int(0.75 * h), int(0.935 * w):int(0.995 * w), 2]
    if (colv < 110).mean() < 0.35:                            # the dark queue column is not open
        return []
    out = []
    for k in range(5):
        cy = 0.3155 + 0.0852 * k
        ix, iy = int(0.9767 * w), int((cy + 0.0225) * h)
        box = hsv[iy - 6:iy + 7, ix - 7:ix + 8]
        green = cv2.countNonZero(cv2.inRange(box, (40, 110, 110), (85, 255, 255)))
        blue = cv2.countNonZero(cv2.inRange(box, (92, 120, 120), (128, 255, 255)))
        red = cv2.countNonZero(cv2.inRange(box, (0, 120, 120), (10, 255, 255))) + \
            cv2.countNonZero(cv2.inRange(box, (165, 120, 120), (180, 255, 255)))
        if max(green, blue, red) < 25:                        # no status icon -> no army card (or the + hex)
            continue
        out.append((0.966, cy, green >= max(blue, red)))
    return out


def _card_march(g, sleep, card):
    """Click an army card in the queue column, then the orange March in its popup. True if pressed."""
    import cv2
    g.click_rel(card[0], card[1]); sleep(1.5)
    img = g.screenshot()
    h, w = img.shape[:2]
    y0, y1 = int((card[1] - 0.14) * h), int((card[1] + 0.14) * h)
    x0, x1 = int(0.78 * w), int(0.92 * w)
    hsv = cv2.cvtColor(img[max(0, y0):y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (12, 150, 190), (28, 255, 255))     # orange March button
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    best = max(range(1, n), key=lambda i: st[i][4], default=None)
    if best is None or st[best][4] < 400:
        return False
    g.click_rel((x0 + cen[best][0]) / w, (max(0, y0) + cen[best][1]) / h); sleep(3)
    return True


def _barb_close(g, sleep):
    """Close the ATTACK queue panel without marching: tap empty map spots until the column is gone."""
    for spot in ((0.42, 0.82), (0.30, 0.55), (0.60, 0.30)):
        if not _queue_cards(g):
            break
        g.click_rel(*spot); sleep(1.5)
        recover_screen(g); sleep(0.5)
    if _queue_cards(g):
        log("  ! attack_barbarians: the army panel did not close")
        _barb_shot(g, "ba_stuck.png")


def _ap_refill(g, sleep):
    """AP window: press the blue USE of an action-point item (never a gem price). True if one was used."""
    from common import close_gem_dialogs
    img = g.screenshot()
    use = g.find_image("btn_use", 0.8, img=img)
    if not use:
        return False
    h, w = img.shape[:2]
    for x, y in use:
        px = img[int(y * h), int(x * w)]
        if int(px[0]) > int(px[2]) + 40:                        # blue USE button only
            g.click_rel(x, y); sleep(2)
            if close_gem_dialogs(g):
                log("  ! attack_barbarians: a gem window appeared - answered NO")
                return False
            log("  attack_barbarians: used one reserve action-point item")
            return True
    return False


def _ap_blocked(g):
    return bool(g.find_image("btn_use", 0.85) or g.find_image("btn_march", 0.78))



# ---------------- v138: army builder (commanders + troop type) and extra marches ----------------
TROOP_WORDS = {
    "infantry": ("axeman", "swordsman", "pikeman", "spearman", "warrior", "legion", "infantry", "samurai", "berserker",
                 "huskarl", "hwarang", "jaguar", "immortal", "throwing", "longswordsman", "hoplite", "guard"),
    "archer": ("crossbow", "bowman", "archer", "longbow", "chu-ko", "chukonu", "yumi", "camel", "hwacha", "slinger", "amazon"),
    "cavalry": ("knight", "cavalry", "horse", "lancer", "mamluk", "conquistador", "cataphract", "rider", "keshik", "elephant", "bear"),
    "siege": ("catapult", "trebuchet", "ballista", "siege", "mangonel", "battering"),
}


def _norm_name(t):
    import re as _re
    return _re.sub(r"[^a-z]", "", (t or "").lower())


def _pick_commander_in_list(g, sleep, name, tag):
    """The commander list is open: find <name> by OCR (scrolling down a few times) and click it.
    Saves a picture of every page to claude_out so a wrong layout can be fixed. True if clicked."""
    import cv2
    from common import BASE
    want = _norm_name(name)
    if not want:
        return False
    for page in range(6):
        img = g.screenshot()
        h, w = img.shape[:2]
        cv2.imwrite(os.path.join(BASE, "claude_out", "cmd_%s%d.png" % (tag, page)), img)
        for x1, y1, x2, y2, txt in _ocr_boxes(img, "cmd_ocr.png"):
            t = _norm_name(txt)
            if len(t) >= 4 and (t in want or want in t or (len(want) > 6 and want[:7] in t)):
                g.click_rel(((x1 + x2) / 2) / w, ((y1 + y2) / 2) / h); sleep(1.5)
                # a USE / SELECT / CONFIRM button may follow
                for key in ("btn_use", "btn_confirm", "btn_select"):
                    try:
                        b = g.find_image(key, 0.8)
                    except Exception:
                        b = None
                    if b:
                        g.click_rel(*b[0]); sleep(1.5)
                        break
                log(f"    army: {tag} commander -> {name}")
                return True
        _drag(g, 0.50, 0.70, 0.50, 0.38)
        sleep(1.2)
    log(f"  ! army: commander '{name}' not found in the list (pictures saved as cmd_{tag}*.png)")
    return False


def _set_troop_type(g, sleep, troop_type, troops):
    """New Troop window: CLEAR, then fill the first row of <troop_type>. Rows are matched by unit name (OCR)."""
    import cv2
    from common import BASE
    words = TROOP_WORDS.get(troop_type or "", ())
    if not words:
        return False
    g.click_rel(0.521, 0.697); sleep(1.2)                    # CLEAR
    for page in range(3):
        img = g.screenshot()
        h, w = img.shape[:2]
        crop = img[int(0.31 * h):int(0.59 * h), int(0.47 * w):int(0.74 * w)]
        for x1, y1, x2, y2, txt in _ocr_boxes(crop, "troop_rows.png"):
            if any(k in txt.lower() for k in words):
                ry = (int(0.31 * h) + (y1 + y2) / 2) / h + 0.028    # the slider sits under the unit name
                # drag the knob to the far right (max), the game caps it at the march size
                _drag(g, 0.513, ry, 0.70, ry)
                sleep(1.2)
                cv2.imwrite(os.path.join(BASE, "claude_out", "army_troops.png"), g.screenshot())
                log(f"    army: troops -> {troop_type} ({txt.strip()})")
                if int(troops or 0) > 0:
                    _set_troop_count(g, sleep, ry, int(troops))
                return True
        _drag(g, 0.60, 0.55, 0.60, 0.36); sleep(1.2)
    log(f"  ! army: no {troop_type} row found - the loadout troops are kept")
    return False


def _set_troop_count(g, sleep, ry, troops):
    """v189: after the slider is at max, drag it back to the requested count.

    The maximum is read from the 'current / max' text next to the slider; when that cannot be
    read the maximum is kept and the log says so.
    """
    import re
    try:
        img = g.screenshot()
        h, w = img.shape[:2]
        boxes = _ocr_boxes(img[int((ry - 0.05) * h):int((ry + 0.05) * h), int(0.55 * w):int(0.95 * w)],
                           "troop_count_ocr.png", 2.0)
    except Exception as e:
        log(f"    army: could not read the troop count ({e!r}) - keeping the maximum")
        return False
    text = " ".join(t for *_xy, t in boxes)
    nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", text)]
    capacity = max(nums) if nums else 0
    if capacity <= 0:
        log(f"    army: troop maximum not readable ('{text[:40]}') - keeping the maximum")
        return False
    want = min(int(troops), capacity)
    frac = max(0.02, min(1.0, want / float(capacity)))
    x_from = 0.513 + (0.70 - 0.513) * frac
    _drag(g, 0.70, ry, x_from, ry)
    sleep(1.0)
    log(f"    army: troop count asked {want:,} of a maximum {capacity:,}")
    return True


def _build_army(g, sleep, loadout=1, commander1="", commander2="", troop_type="", troops=0):
    """New Troop window is open. Red loadout <n> first; if a primary commander is set, swap in the chosen
    commanders and troop type. Anything that fails keeps what the loadout already put in."""
    g.click_rel(0.753, 0.428 + (int(loadout or 1) - 1) * 0.0394); sleep(2)   # red loadout <n>
    if not (commander1 or "").strip():
        if troop_type and g.find_image("btn_march", 0.78):
            _set_troop_type(g, sleep, troop_type, troops)
        return
    g.click_rel(0.33, 0.37); sleep(2.5)                      # primary commander portrait -> list
    if not _pick_commander_in_list(g, sleep, commander1, "p"):
        recover_screen(g) if not g.find_image("btn_march", 0.78) else None
        sleep(1)
    if (commander2 or "").strip() and g.find_image("btn_march", 0.78):
        g.click_rel(0.405, 0.50); sleep(2.5)                 # secondary commander
        if not _pick_commander_in_list(g, sleep, commander2, "s"):
            recover_screen(g) if not g.find_image("btn_march", 0.78) else None
            sleep(1)
    if troop_type and g.find_image("btn_march", 0.78):
        _set_troop_type(g, sleep, troop_type, troops)


def _send_extra_march(g, sleep, lvl, m, use_ap_items):
    """Send one more army from the city to a level <lvl> barbarian (the same target: the nearest one)."""
    pos, _ = _barb_search(g, sleep, lvl, lvl)
    if not pos:
        log(f"  ! extra march: level {lvl} barbarian not found again")
        return False
    g.click_rel(*pos); sleep(3)
    nt = g.find_image("btn_new_troop", 0.78)
    if not nt:
        log("  ! extra march: no free march slot (New Troop missing)")
        _barb_close(g, sleep)
        return False
    g.click_rel(*nt[0]); sleep(3)
    _build_army(g, sleep, m.get("loadout") or 1, m.get("commander1") or "", m.get("commander2") or "",
                m.get("troop_type") or "", m.get("troops") or 0)
    b = g.find_image("btn_march", 0.78)
    g.click_rel(*(b[0] if b else (0.656, 0.696))); sleep(3)
    if _ap_blocked(g):
        if not (use_ap_items and g.find_image("btn_use", 0.85) and _ap_refill(g, sleep)):
            log("  extra march: action points finished")
            recover_screen(g); sleep(1); recover_screen(g)
            return False
        b = g.find_image("btn_march", 0.78)
        if b:
            g.click_rel(*b[0]); sleep(3)
    return not _ap_blocked(g)


def attack_barbarians(g, sleep, min_level=1, max_level=10, hold=True, loadout=1, need_qin=False, dry_run=False,
                      chain=True, use_ap_items=False, max_attacks=30, wait_between=40, commander1="", commander2="",
                      troops=100000, troop_type="archer", marches=1, extra_marches=None):
    """Search a barbarian (max_level down to min_level), tick 'Hold position', attack with loadout <n>.
    chain: the same army keeps hunting - after each kill it searches the next barbarian near it and attacks it,
    one after another, until action points run out (or max_attacks). use_ap_items: when AP runs out, use reserve
    AP items from the bag (never gems) and carry on."""
    import time as _t
    if not (commander1 or "").strip():                              # TASK-07: per-task commander preset
        commander1, commander2 = _preset("barbarians")
    if _t.time() < BARB_STATE["stop_until"]:
        log("  - attack_barbarians: paused (no action points earlier)")
        return True
    if _queue_cards(g):                                       # a queue panel was left open
        _barb_close(g, sleep)
    if _in_city(g) or not _on_map(g):
        press_key("space"); sleep(6)
    if not goto_map(g, sleep, "attack_barbarians"):
        return True
    lo, hi = sorted((int(min_level), int(max_level)))
    kills, army_out, our_y = 0, False, None
    rounds = int(max_attacks) if chain else 1
    for rnd in range(rounds):
        pos, lvl = _barb_search(g, sleep, lo, hi)
        if not pos:
            log(f"  ! attack_barbarians: no barbarian level {lo}-{hi} found near")
            break
        if hold:
            hp = [p for p in g.find_image("hold_pos_off", 0.85) if abs(p[1] - pos[1]) < 0.1]
            if hp:
                g.click_rel(*hp[0]); sleep(0.8)
            pos = _barb_find_attack(g) or pos
        g.click_rel(*pos); sleep(3)                              # ATTACK
        _barb_shot(g, "ba_troops%d.png" % min(rnd, 2))
        if dry_run:
            log(f"  attack_barbarians (test): level {lvl} found, troop window saved - nothing sent")
            break
        sent = False
        cards = _queue_cards(g)
        free = [c for c in cards if not c[2]]
        log(f"    queue column: {len(cards)} army card(s), {len(free)} not gathering")
        if army_out or (free and not g.find_image("btn_new_troop", 0.78)):
            pick = None
            if free:
                pick = next((c for c in free if our_y is not None and abs(c[1] - our_y) < 0.02), free[-1])
            if pick and _card_march(g, sleep, pick):
                our_y = pick[1]
                _barb_shot(g, "ba_chain%d.png" % min(rnd, 2))
                for _ in range(2):
                    if not g.find_image("btn_use", 0.85):
                        break
                    if not (use_ap_items and _ap_refill(g, sleep)):
                        log("  attack_barbarians: action points finished" +
                            ("" if use_ap_items else " (reserve AP items are off)") + " - stopping for 1 hour")
                        BARB_STATE["stop_until"] = _t.time() + 3600
                        _barb_close(g, sleep)
                        return True
                    _card_march(g, sleep, pick)
                sent = not g.find_image("btn_use", 0.85)
                army_out = army_out or sent
        if not sent and army_out:
            _barb_shot(g, "ba_nomarch.png")
            log("  ! attack_barbarians: the army on the map did not march - stopping the chain")
            _barb_close(g, sleep)
            break
        if not sent:
            nt = g.find_image("btn_new_troop", 0.78)
            if not nt:
                if army_out:
                    log("  ! attack_barbarians: could not pick the army on the map - stopping the chain")
                else:
                    log("  ! attack_barbarians: no free march slot (New Troop missing) and no idle army on the map")
                _barb_close(g, sleep)
                break
            g.click_rel(*nt[0]); sleep(3)
            _build_army(g, sleep, loadout, commander1, commander2, troop_type if (commander1 or "").strip() else "", troops)
            if need_qin and not g.find_image("qin_face", 0.72):
                log("  ! attack_barbarians: Qin Shi Huang is not in this loadout / not in the city - attack cancelled")
                _barb_shot(g, "ba_not_qin.png")
                recover_screen(g)
                break
            m = g.find_image("btn_march", 0.78)
            g.click_rel(*(m[0] if m else (0.656, 0.696))); sleep(3)
            for _ in range(2):
                if not _ap_blocked(g):
                    break
                if not (use_ap_items and g.find_image("btn_use", 0.85) and _ap_refill(g, sleep)):
                    break
                m = g.find_image("btn_march", 0.78)
                if m:
                    g.click_rel(*m[0]); sleep(3)
            if _ap_blocked(g):
                log("  attack_barbarians: action points finished" +
                    ("" if use_ap_items else " (reserve AP items are off)") + " - stopping for 1 hour")
                BARB_STATE["stop_until"] = _t.time() + 3600
                recover_screen(g); sleep(1); recover_screen(g)
                break
            army_out = True
            extra = [m for m in (extra_marches or []) if isinstance(m, dict)][:max(0, int(marches or 1) - 1)]
            for i, m in enumerate(extra):
                sleep(2)
                ok = _send_extra_march(g, sleep, lvl, m, use_ap_items)
                log(f"  attack_barbarians: extra march {i + 2} -> level {lvl} " + ("sent" if ok else "NOT sent"))
                if not ok:
                    break
        kills += 1
        try:
            stat("barb")
        except Exception:
            pass
        log(f"  attack_barbarians: attack {kills} -> level {lvl} barbarian (red loadout {loadout}, {max(1, int(marches or 1))} march(es), hold {'on' if hold else 'off'})")
        if not (chain and hold) or rnd == rounds - 1:
            break
        sleep(float(wait_between) + (25 if kills == 1 else 0))     # march + battle
        recover_screen(g)
    log(f"  attack_barbarians: {kills} attack(s) this run")
    return True


SMART["attack_barbarians"] = attack_barbarians


COMMANDER_NAMES = ["Aethelflaed", "Afonso", "Alexander Nevsky", "Alexander the Great", "Alp Arslan", "Archimedes", "Artemisia", "Arthur Pendragon", "Ashurbanipal", "Attila", "Babur", "Bai Qi", "Baibars", "Belisarius", "Belisarius Prime", "Bertrand du Guesclin", "Bjorn Ironside", "Boudica", "Boudica Prime", "Cao Cao", "Casimir", "Catherine de' Medici", "Centurion", "Chandragupta", "Charlemagne", "Charles Martel", "Cheok Jun-Gyeong", "Choe Yeong", "City Keeper", "Cleopatra", "Constance", "Constantine", "Cyrus the Great", "Diaochan", "Dido", "Dragon Lancer", "Edward", "El Cid", "Eleanor of Aquitaine", "Elizabeth", "Eulji Mundeok", "Flavius Aetius", "Frederick", "Gaius Marius", "Gajah Mada", "Gang Gamchan", "Genghis Khan", "Gilgamesh", "Gonzalo de Cordoba", "Gorgo", "Guan Yu", "Hannibal Barca", "Harald Sigurdsson", "Hayam Wuruk", "Hector", "Henry", "Heraclius", "Hermann", "Hermann Prime", "Honda Tadakatsu", "Huo Qubing", "Imhotep", "Ishida Mitsunari", "Ivar the Boneless", "Jadwiga", "Jan Zizka", "Joan of Arc", "Joan of Arc Prime", "John Hunyadi", "Julius Caesar", "Justinian", "Keira", "Kusunoki Masashige", "Lancelot", "Lapu-Lapu", "Leonidas", "Liu Che", "Lohar", "Lu Bu", "Margaret", "Markswoman", "Mary", "Matilda of Flanders", "Matthias", "Mehmed", "Minamoto no Yoshitsune", "Mulan", "Narses", "Nebuchadnezzar", "Osman", "Pakal", "Pelagius", "Pepin", "Pericles", "Philip", "Pyrrhus", "Qin Shi Huang", "Ragnar Lodbrok", "Ragnar Lodbrok Prime", "Ramesses", "Richard", "Saladin", "Sargon the Great", "Sarka", "Scipio Aemilianus", "Scipio Africanus", "Seondeok", "Shajar al-Durr", "Shapur", "Siyaj K'ak", "Stephen III", "Subutai", "Suleiman", "Sun Tzu", "Sun Tzu Prime", "Takeda Shingen", "Tariq ibn Ziyad", "Theodora", "Thutmose", "Tokugawa Ieyasu", "Tomoe Gozen", "Tomyris", "Torgny", "Trajan", "Vercingetorix", "Wak Chanil Ajaw", "William I", "William Wallace", "Wu Zetian", "Xiang Yu", "Yahya ibn Khalid", "Yi Seong-Gye", "Yi Sun-Sin", "Zenobia", "Zhuge Liang"]


def read_commanders(g, sleep):
    """Open New Troop on a barbarian (nothing is sent), open the commander list and read every commander the
    player owns: name (OCR, matched to the known list) + a small portrait. Sent to the dashboard picker."""
    import cv2, base64, control
    from common import BASE
    if _in_city(g) or not _on_map(g):
        press_key("space"); sleep(6)
    pos, _ = _barb_search(g, sleep, 1, 10)
    if not pos:
        log("  read_commanders: no barbarian to open the troop window - retry in 30 min"); recover_screen(g); return "retry"
    g.click_rel(*pos); sleep(3)
    nt = g.find_image("btn_new_troop", 0.78)
    if not nt:
        log("  read_commanders: no New Troop (all march slots busy) - retry in 30 min"); _barb_close(g, sleep); return "retry"
    g.click_rel(*nt[0]); sleep(3)
    g.click_rel(0.33, 0.37); sleep(2.5)                      # commander list
    known = {_norm_name(n): n for n in COMMANDER_NAMES}
    found, levels, last = {}, {}, None
    for page in range(8):
        img = g.screenshot()
        h, w = img.shape[:2]
        cv2.imwrite(os.path.join(BASE, "claude_out", "cmdlist%d.png" % page), img)
        boxes = _ocr_boxes(img, "cmdlist_ocr.png")
        for x1, y1, x2, y2, txt in boxes:
            t = _norm_name(txt)
            if len(t) < 4:
                continue
            name = known.get(t) or next((v for k, v in known.items() if len(k) >= 5 and (k in t or t in k)), None)
            if not name or name in found:
                continue
            cx = (x1 + x2) / 2
            side = int(max(56, min(0.13 * w, (x2 - x1) * 1.5)))
            px0, py1 = int(cx - side / 2), int(y1) - 2
            crop = img[max(0, py1 - side):max(1, py1), max(0, px0):px0 + side]
            av = ""
            if crop.size:
                crop = cv2.resize(crop, (64, 64), interpolation=cv2.INTER_AREA)
                ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 72])
                if ok:
                    av = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
            lvl = 0
            import re as _re
            cxn = (x1 + x2) / 2
            for bx1, by1, bx2, by2, bt in boxes:                 # level: "Lv. 60" / a number on the same card
                bcx, bcy = (bx1 + bx2) / 2, (by1 + by2) / 2
                if abs(bcx - cxn) > 0.08 * w or not (y1 - 0.20 * h <= bcy <= y2 + 0.06 * h) or (bx1, by1) == (x1, y1):
                    continue
                m = _re.search(r"(?:lv|lvl|level)\.?\s*(\d{1,2})", bt.lower()) or _re.fullmatch(r"\s*(\d{1,2})\s*", bt)
                if m and 1 <= int(m.group(1)) <= 60:
                    lvl = max(lvl, int(m.group(1)))
            found[name] = av
            levels[name] = lvl
        sig = tuple(sorted(found))
        if sig == last:
            break
        last = sig
        _drag(g, 0.50, 0.72, 0.50, 0.36); sleep(1.5)
    control.CITY["commanders"] = [{"name": n, "img": a, "level": levels.get(n, 0)} for n, a in found.items()]
    control.CITY["commanders_at"] = __import__("time").strftime("%Y-%m-%d %H:%M")
    _persist_save()
    try:                                                     # v141: keep every character's commanders apart
        from common import BASE, load_json, save_json
        who = (control.CITY.get("rotation") or {}).get("char") or control.CITY.get("profile_char") or _char_key()
        if who and found:
            import re as _re
            key = _re.sub(r"[^0-9A-Za-z_-]+", "_", str(who)).strip("_")[:30] or "char"
            pf = os.path.join(BASE, "commanders_by_char.json")
            store = load_json(pf, {})
            store[key] = {"list": control.CITY["commanders"], "at": control.CITY["commanders_at"]}
            save_json(pf, store)
    except Exception as e:
        log(f"  ! read_commanders: could not keep per character: {e!r}")
    if not found:
        log("  read_commanders: nothing read - retry in 30 min (pictures: claude_out/cmdlist*.png)")
    log(f"  read_commanders: {len(found)} commander(s) read: " + ", ".join(list(found)[:12]))
    recover_screen(g); sleep(1); recover_screen(g); sleep(1)
    _barb_close(g, sleep)
    return True if found else "retry"


SMART["read_commanders"] = read_commanders
SMART["attack_barbarians_test"] = lambda g, sleep: attack_barbarians(g, sleep, 8, 12, True, True)
SMART["attack_barbarians_once"] = lambda g, sleep: attack_barbarians(g, sleep, 8, 12, True, 1, True, False, chain=False)
SMART["attack_barbarians_chain3"] = lambda g, sleep: attack_barbarians(g, sleep, 8, 12, True, 1, True, False, chain=True, max_attacks=3)


# ---------------- VIP shop: buy everything priced in resources (v67) ----------------
def _price_buttons(img):
    """Orange price buttons in the shop list: [(x, y, w, h, is_gem)] in pixels."""
    import cv2
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (10, 180, 200), (25, 255, 255))
    m[:int(0.33 * h)] = 0; m[int(0.72 * h):] = 0; m[:, :int(0.25 * w)] = 0; m[:, int(0.6 * w):] = 0
    n, _, st, _ = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        x, y, bw, bh, ar = st[i]
        if ar < 600 or bw < 0.05 * w or bh < 0.022 * h:
            continue
        icon = img[y:y + bh, x:x + int(bw * 0.4)].astype(int)
        b, g_, r = icon[:, :, 0], icon[:, :, 1], icon[:, :, 2]
        red = int(((r > 150) & (g_ < 90) & (b < 90)).sum())
        out.append((x, y, bw, bh, red > 8))
    return sorted(out, key=lambda t: (t[1], t[0]))


def vip_shop(g, sleep, max_buys=60):
    """City > VIP Shop bubble above the Shop building. Buys every pack priced in RESOURCES (never gems):
    one click buys 1, then the quick 'x N' button buys the rest of the stock. Saves the refresh timer."""
    import cv2, control
    from common import close_gem_dialogs, BASE
    _city_reset(g, sleep)
    g.click_rel(0.518, 0.045); sleep(3)                      # VIP Shop bubble (only shown sometimes)

    def _shop_probe(cx, cy):
        g.click_rel(cx, cy); sleep(2)                        # Shop building
        hx = g.find_image("btn_vipshop_hex", 0.8)
        if hx:
            g.click_rel(*hx[0]); sleep(3)
            return bool(g.find_image("vip_shop_title", 0.8))
        return False

    if not g.find_image("vip_shop_title", 0.8):
        recover_screen(g)
        _city_reset(g, sleep)
        mem = _bpos("vip_shop")
        ok = False
        if mem:                                              # v137: this character's remembered spot
            ok = _shop_probe(*mem)
            if not ok:
                recover_screen(g); _city_reset(g, sleep)
        if not ok:
            _drag(g, 0.5, 0.30, 0.5, 0.60); sleep(2)         # bring the Shop building into view (main city layout)
            cv2.imwrite(os.path.join(BASE, "claude_out", "vs_drag.png"), g.screenshot())
            for (cx, cy) in ((0.518, 0.40), (0.518, 0.36), (0.518, 0.44), (0.48, 0.40), (0.56, 0.40), (0.518, 0.32)):
                g.click_rel(cx, cy); sleep(2)                # Shop building (camera position varies a little)
                hx = g.find_image("btn_vipshop_hex", 0.8)
                if hx:
                    g.click_rel(*hx[0]); sleep(3)
                    break
            cv2.imwrite(os.path.join(BASE, "claude_out", "vs_click.png"), g.screenshot())
        if not g.find_image("vip_shop_title", 0.8):
            recover_screen(g)
            _city_reset(g, sleep)
            _scan_building(g, sleep, "vip_shop", _shop_probe)    # other city layout: search once, remember it
    if not g.find_image("vip_shop_title", 0.8):
        log("  - vip_shop: the VIP Shop did not open - will try again next round")
        recover_screen(g)
        return "retry"
    img = g.screenshot()
    h, w = img.shape[:2]
    t = " ".join(_ocr_lines(img[int(0.326 * h):int(0.356 * h), int(0.26 * w):int(0.47 * w)], "vipshop_timer.png", scale=3))
    if t:
        import re as _re
        control.CITY["vip_shop_refresh"] = _re.sub(r"(?i)^.*?in\s*:?", "", t).strip() or t
        control.CITY["vip_shop_read"] = time.strftime("%Y-%m-%d %H:%M")
        log(f"  vip_shop: refreshes in {control.CITY['vip_shop_refresh']}")
    bought, seen_pages, tried = 0, 0, set()
    while bought < int(max_buys) and seen_pages < 6:
        img = g.screenshot()
        did = False
        for (x, y, bw, bh, gem) in _price_buttons(img):
            key = (seen_pages, x // 12, y // 12)
            if gem or key in tried:
                continue
            tried.add(key)
            cx, cy = (x + bw / 2) / w, (y + bh / 2) / h
            g.click_rel(cx, cy); sleep(1.5)                  # buys one
            if close_gem_dialogs(g):
                log("  ! vip_shop: a gem window appeared - answered NO and stopped")
                recover_screen(g)
                return True
            img2 = g.screenshot()
            quick = [b for b in _price_buttons(img2) if abs(b[1] - y) < 8 and b[0] + b[2] < x and not b[4]]
            if quick:                                        # 'x N' = the rest of the stock
                qx, qy, qw, qh, _ = max(quick, key=lambda b: b[0])
                g.click_rel((qx + qw / 2) / w, (qy + qh / 2) / h); sleep(1.5)
                close_gem_dialogs(g)
            bought += 1; did = True
            break                                            # re-read the list after each purchase
        if not did:
            sx, sy = g.to_screen(0.42, 0.66); ex, ey = g.to_screen(0.42, 0.40)
            pyautogui.moveTo(sx, sy); pyautogui.mouseDown()
            pyautogui.moveTo(ex, ey, duration=0.6); pyautogui.mouseUp()
            sleep(1.5); seen_pages += 1
    cv2.imwrite(os.path.join(BASE, "claude_out", "vip_shop_last.png"), g.screenshot())
    log(f"  vip_shop: {bought} resource pack(s) bought, gem packs skipped")
    recover_screen(g)
    return True


SMART["vip_shop"] = vip_shop


def _drag(g, x1, y1, x2, y2, dur=0.6):
    sx, sy = g.to_screen(x1, y1); ex, ey = g.to_screen(x2, y2)
    pyautogui.moveTo(sx, sy); pyautogui.mouseDown()
    pyautogui.moveTo(ex, ey, duration=dur); pyautogui.mouseUp()


def shop_probe(g, sleep):
    import cv2
    from common import BASE
    if not _in_city(g):
        press_key("space"); sleep(6)
    _drag(g, 0.5, 0.30, 0.5, 0.60); sleep(2)
    cv2.imwrite(os.path.join(BASE, "claude_out", "sp1.png"), g.screenshot())
    g.click_rel(0.518, 0.40); sleep(2)
    cv2.imwrite(os.path.join(BASE, "claude_out", "sp2.png"), g.screenshot())
    return True


SMART["shop_probe"] = shop_probe


# ---------------- city queues + marches for the dashboard (v69) ----------------


def _ocr_lines(img_bgr, name="ocr_lines.png", scale=2.5, invert=False):
    import cv2, subprocess
    from common import BASE
    g0 = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    g0 = cv2.resize(g0, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if invert:
        g0 = 255 - g0
    path = os.path.join(BASE, "claude_out", name)
    cv2.imwrite(path, g0)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            os.path.join(BASE, "ocr.ps1"), path],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=60, creationflags=0x08000000)
        return [l.strip() for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def _secs(t):
    import re
    m = re.search(r"(?:(\d+)\s*d\s*)?(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?", t)
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def _fmt_left(sec):
    h, r = divmod(int(sec), 3600)
    return (f"{h // 24} d {h % 24} h {r // 60} min" if h >= 24 else f"{h} h {r // 60} min") if h else f"{r // 60} min"


SECTIONS = {"unit training": "train", "unit healing": "heal", "building queues": "build", "tech research": "res",
            "alliance donations": "don", "material production": "mat", "armament": "arm", "scout queues": "scout"}


QWORDS = {"heal": ("capacity", "heal"), "build": ("building", "upgrad"), "res": ("research", "tech"),
          "mat": ("producible", "produc", "material"), "skip": ("travel", "dispatch", "chance", "scout")}


QUEUE_SECTIONS = ("unit training", "unit healing", "building queues", "tech research",
                  "alliance donations", "material production", "armament acquirement",
                  "scout queues", "queue overview")

QUEUE_STATUS_START = ("idle", "training", "time remaining", "chances", "producible",
                      "travels", "remaining", "standing", "donate", "completed")


def read_queues(g, sleep):
    """v197: the Queue Overview is read by queue_manager (all sections, folded ones opened, scrolled to the end)."""
    import queue_manager
    queue_manager.scan(g, sleep)
    return True


SMART["read_queues"] = read_queues


# ---------------- v137: find buildings per character (tavern / shop move between cities) ----------------
def _bpos_file():
    from common import BASE
    return os.path.join(BASE, "building_pos.json")


def _char_key():
    import control
    c = next((c for c in (control.CITY.get("characters") or []) if c.get("current")), None)
    return (c or {}).get("name") or "default"


def _bpos(kind=None, xy=None, fail=None):
    import json
    p = _bpos_file()
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        d = {}
    ent = d.setdefault(_char_key(), {})
    if xy is None and fail is None:
        return ent.get(kind)
    if xy is not None:
        ent[kind] = [round(xy[0], 3), round(xy[1], 3)]
        ent.pop(kind + "_fail", None)
    if fail is not None:
        ent[kind + "_fail2"] = fail       # v151: new key, old "_fail" cooldowns are ignored
    try:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception as e:
        log(f"    ! building_pos save failed: {e!r}")


def _city_reset(g, sleep):
    """Same camera every time: city -> map -> city (the game re-centres the city view)."""
    if not _in_city(g):
        recover_screen(g)
    if _in_city(g):
        press_key("space"); sleep(4)
    press_key("space"); sleep(5)
    return _in_city(g)


CITY_GRID = [(x / 100, y / 100) for y in range(30, 79, 8) for x in range(20, 90, 9)]


def _scan_building(g, sleep, kind, probe):
    """Click every spot of a grid over the city until probe(x, y) says the building opened.
    Remembers the spot for this character. At most one scan per 6 hours per building."""
    import time as _t
    # v151: "_fail2" - the previous cooldowns were written by the old, narrower name reader and
    # would block a re-scan for 6 hours; a new key lets the improved reader try again now.
    last = (_bpos(kind + "_fail2") or 0)
    if _t.time() - float(last) < 6 * 3600:
        return None
    log(f"    searching the city for the {kind} (this character's city layout)...")
    t_end = _t.time() + 6 * 60                       # v204: a scan never blocks the bot for more than 6 minutes
    for (x, y) in CITY_GRID:
        if _t.time() > t_end:
            log(f"    ! {kind}: city search stopped after 6 minutes")
            break
        if not _in_city(g):
            recover_screen(g)
            if not _city_reset(g, sleep):
                break
        if probe(x, y):
            _bpos(kind, (x, y))
            log(f"    {kind} found at {x:.2f},{y:.2f} - remembered for {_char_key()}")
            return (x, y)
    _bpos(kind, fail=_t.time())
    log(f"    ! {kind} not found in the city - next search in 6 hours")
    return None


# ---------------- tavern free chests (v75) ----------------
def _blue_buttons(img, y0=0.62, y1=0.73):
    import cv2
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (95, 150, 180), (110, 255, 255))
    m[:int(y0 * h)] = 0; m[int(y1 * h):] = 0
    n, _, st, _ = cv2.connectedComponentsWithStats(m)
    return [((x + bw / 2) / w, (y + bh / 2) / h) for x, y, bw, bh, ar in (st[i] for i in range(1, n))
            if ar > 900 and bw > 0.05 * w]


def _tavern_try(g, sleep, x, y, need_name=False):
    g.click_rel(x, y); sleep(2)                              # Tavern building
    if need_name:                                            # scanning: only press the button under a building called Tavern
        img = g.screenshot()
        h, w = img.shape[:2]
        crop = img[max(0, int((y - 0.22) * h)):int((y + 0.04) * h), max(0, int((x - 0.22) * w)):min(w, int((x + 0.22) * w))]
        txt = " ".join(_ocr_lines(crop, "tavern_scan.png", scale=2)).lower()
        if "tavern" not in txt and "taver" not in txt:
            return False
    g.click_rel(x, min(0.95, y + 0.115)); sleep(3)           # chests button (just under the building)
    if g.find_image("tavern_silver_title", 0.8):
        return True
    from common import close_gem_dialogs
    close_gem_dialogs(g)
    return False


def _open_tavern(g, sleep):
    """v137: reset the camera, try this character's remembered spot, then the default spot,
    and if both fail search the city once (cities differ between characters)."""
    _city_reset(g, sleep)
    spots = []
    mem = _bpos("tavern")
    if mem:
        spots.append(tuple(mem))
    if (0.835, 0.505) not in spots:
        spots.append((0.835, 0.505))
    for (x, y) in spots:
        if _tavern_try(g, sleep, x, y):
            if not mem or tuple(mem) != (x, y):
                _bpos("tavern", (x, y))
            return True
        recover_screen(g)
        _city_reset(g, sleep)
    return bool(_scan_building(g, sleep, "tavern", lambda x, y: _tavern_try(g, sleep, x, y, need_name=True)))


def tavern(g, sleep, max_open=12):
    """Tavern: open ONLY free chests (blue OPEN button). Orange OPEN = keys -> never pressed. Never gems."""
    import cv2, control, time as _t
    from common import close_gem_dialogs, BASE
    if ensure_screen(g, sleep, "city", tries=2) != "city":     # v181
        log("  ! tavern: the city is not showing - skipped")
        return True
    if not _open_tavern(g, sleep):
        log("  ! tavern: the tavern did not open")
        recover_screen(g)
        return True
    opened = 0
    for _ in range(int(max_open)):
        img = g.screenshot()
        if not g.find_image("tavern_silver_title", 0.8, img=img):
            break                                            # not on the chest page any more - stop
        btn = _blue_buttons(img)
        if not btn:
            break
        g.click_rel(*btn[0]); sleep(4)                       # free chest
        if close_gem_dialogs(g):
            log("  ! tavern: a gem window appeared - answered NO and stopped")
            break
        for _k in range(8):                                  # skip the reward animation / commander card
            img2 = g.screenshot()
            if g.find_image("tavern_silver_title", 0.8, img=img2):
                break
            cf = g.find_image("btn_confirm_cmd", 0.8, img=img2)
            if cf:
                g.click_rel(*cf[0]); sleep(2.5)
            else:
                g.click_rel(0.5, 0.92); sleep(2)
        opened += 1
    img = g.screenshot()
    h, w = img.shape[:2]
    t = " ".join(_ocr_lines(img[int(0.615 * h):int(0.64 * h), int(0.2 * w):int(0.82 * w)], "tavern_ocr.png", scale=3))
    control.CITY["tavern"] = t[:80]
    control.CITY["tavern_read"] = _t.strftime("%H:%M")
    cv2.imwrite(os.path.join(BASE, "claude_out", "tavern_last.png"), img)
    log(f"  tavern: {opened} free chest(s) opened   ({t[:80]})")
    g.click_rel(0.021, 0.025); sleep(2)                      # back
    recover_screen(g)
    return True


def tavern_legendary(g, sleep):
    """Legendary chest: once a day, ONLY if the button says it is free."""
    from common import close_gem_dialogs
    if not _in_city(g):
        press_key("space"); sleep(6)
    g.click_rel(0.835, 0.505); sleep(2)
    g.click_rel(0.900, 0.603); sleep(3)                      # legendary chests button
    img = g.screenshot()
    h, w = img.shape[:2]
    t = " ".join(_ocr_lines(img[int(0.645 * h):int(0.73 * h), int(0.4 * w):int(0.6 * w)], "legend_ocr.png", scale=3)).lower()
    if "free" in t:
        btn = _blue_buttons(img, 0.64, 0.71)
        if btn:
            g.click_rel(*btn[0]); sleep(4)
            close_gem_dialogs(g)
            for _k in range(4):
                g.click_rel(0.5, 0.92); sleep(2)
            log("  tavern_legendary: free legendary chest opened")
    else:
        log(f"  - tavern_legendary: no free legendary chest today ({t[:40]})")
    g.click_rel(0.021, 0.025); sleep(2)
    recover_screen(g)
    return True


SMART["tavern"] = tavern
SMART["tavern_legendary"] = tavern_legendary


def troop_probe(g, sleep):
    """Open a New Troop window on a barbarian (nothing is sent) and take pictures of the loadout buttons."""
    import cv2
    from common import BASE
    if _in_city(g) or not _on_map(g):
        press_key("space"); sleep(6)
    pos, lvl = _barb_search(g, sleep, 8, 12)
    if not pos:
        log("  troop_probe: no barbarian"); recover_screen(g); return True
    pos = _barb_find_attack(g) or pos
    g.click_rel(*pos); sleep(3)
    nt = g.find_image("btn_new_troop", 0.78)
    if not nt:
        log("  troop_probe: no New Troop"); recover_screen(g); return True
    g.click_rel(*nt[0]); sleep(3)
    cv2.imwrite(os.path.join(BASE, "claude_out", "tp1.png"), g.screenshot())
    g.click_rel(0.753, 0.386); sleep(2)                      # switch to the RED loadouts
    for i, (x, y) in enumerate([(0.753, 0.428), (0.753, 0.468), (0.753, 0.507), (0.753, 0.547)]):
        g.click_rel(x, y); sleep(2)
        cv2.imwrite(os.path.join(BASE, "claude_out", "tpr%d.png" % (i + 1)), g.screenshot())
    g.click_rel(0.33, 0.37); sleep(3)                        # primary commander
    cv2.imwrite(os.path.join(BASE, "claude_out", "tp3.png"), g.screenshot())
    recover_screen(g); sleep(1)
    g.click_rel(0.405, 0.50); sleep(3)                       # secondary commander
    cv2.imwrite(os.path.join(BASE, "claude_out", "tp4.png"), g.screenshot())
    recover_screen(g); sleep(1); recover_screen(g)
    return True


SMART["troop_probe"] = troop_probe


# ---------------- v139: material production at the Blacksmith ----------------
MAT_SLOTS = {"leather": 0.567, "ore": 0.618, "ebony": 0.668, "bone": 0.719}   # x of the 4 materials (y 0.408)
MAT_GRID = [(x / 100, y / 100) for y in range(28, 80, 7) for x in range(8, 92, 7)]


def _mat_open_window(g, sleep):
    img = g.screenshot()
    h, w = img.shape[:2]
    txt = " ".join(_ocr_lines(img[int(0.27 * h):int(0.33 * h), int(0.33 * w):int(0.67 * w)], "mat_title.png", scale=2)).lower()
    return "material" in txt or "production" in txt


def _mat_try(g, sleep, x, y, need_name=True):
    """Click the Blacksmith at x,y; read its label to place the 3 buttons; press the right one (Material Production)."""
    g.click_rel(x, y); sleep(2)
    img = g.screenshot()
    h, w = img.shape[:2]
    x0, y0 = max(0, int((x - 0.25) * w)), max(0, int((y - 0.25) * h))
    crop = img[y0:int(min(1, y + 0.08) * h), x0:min(w, int((x + 0.25) * w))]
    lab = None
    for bx1, by1, bx2, by2, t in _ocr_boxes(crop, "mat_scan.png"):
        if "smith" in t.lower():
            lab = ((x0 + (bx1 + bx2) / 2) / w, (y0 + (by1 + by2) / 2) / h)
            break
    if not lab:
        if need_name:
            recover_screen(g)
            return False
        lab = (x + 0.03, y - 0.08)
    for dx in (0.066, 0.075, 0.057):
        g.click_rel(min(0.97, lab[0] + dx), min(0.95, lab[1] + 0.172)); sleep(2.5)
        if _mat_open_window(g, sleep):
            return True
        from common import close_gem_dialogs
        close_gem_dialogs(g)
        if not _in_city(g):
            recover_screen(g); sleep(1)
        g.click_rel(x, y); sleep(2)
    recover_screen(g)
    return False


def _mat_queue_sig(g):
    import cv2
    img = g.screenshot()
    h, w = img.shape[:2]
    q = img[int(0.34 * h):int(0.68 * h), int(0.27 * w):int(0.50 * w)]
    return cv2.resize(cv2.cvtColor(q, cv2.COLOR_BGR2GRAY), (60, 40)).astype("int16")


def materials(g, sleep, kinds=("leather", "ore", "ebony", "bone"), every=None):
    """City > Blacksmith > Material Production: fill the production queue (up to 5) with the chosen materials,
    in turn. Production is paid with resources; gem windows are always answered NO."""
    import numpy as np
    from common import close_gem_dialogs
    kinds = [k for k in (kinds or []) if k in MAT_SLOTS] or ["leather", "ore", "ebony", "bone"]
    import queue_manager
    opened = False
    if queue_manager.tap_row(g, sleep, "materials"):        # v197: Queue Overview > Material Production
        opened = _mat_open_window(g, sleep)
        if not opened:
            log("    materials: the Material Production row did not open the window - using the Blacksmith")
            recover_screen(g)
    if not opened:
        _city_reset(g, sleep)
    mem = None if opened else _bpos("blacksmith")
    if mem and _mat_try(g, sleep, mem[0], mem[1], need_name=False):
        opened = True
    if not opened and mem:                                   # v143: the camera can sit a little off - look near the old spot first
        for dx, dy in ((0, 0.12), (0, -0.12), (0.12, 0), (-0.12, 0), (0, 0.24), (0, -0.24), (0, 0.35), (0, -0.35)):
            x, y = mem[0] + dx, mem[1] + dy
            if 0.06 < x < 0.94 and 0.2 < y < 0.85 and _mat_try(g, sleep, x, y, need_name=True):
                _bpos("blacksmith", (x, y)); opened = True
                log(f"    blacksmith found near the old spot at {x:.2f},{y:.2f}")
                break
    import time as _t
    from common import BASE, load_json, save_json
    cdf = os.path.join(BASE, "mat_scan_cd.json")
    cd = load_json(cdf, {})
    if not opened and _t.time() < cd.get(_char_key(), 0):
        log("  materials: Blacksmith not found recently - next full search later (no clicking around now)")
        recover_screen(g)
        return True
    if not opened:
        cd[_char_key()] = _t.time() + 6 * 3600              # at most one full search per 6 hours per character
        save_json(cdf, cd)
        for (x, y) in MAT_GRID:
            if not _in_city(g):
                recover_screen(g)
                if not _city_reset(g, sleep):
                    break
            if _mat_try(g, sleep, x, y, need_name=True):
                _bpos("blacksmith", (x, y))
                log(f"    blacksmith found at {x:.2f},{y:.2f} - remembered for {_char_key()}")
                opened = True
                break
    if not opened:
        log("  ! materials: could not open Material Production (Blacksmith not found)")
        recover_screen(g)
        return True
    added, i = 0, 0
    for _ in range(6):
        k = kinds[i % len(kinds)]
        before = _mat_queue_sig(g)
        g.click_rel(MAT_SLOTS[k], 0.408); sleep(2)
        if close_gem_dialogs(g):
            log("  ! materials: a gem window appeared - answered NO")
            break
        after = _mat_queue_sig(g)
        if float(np.abs(after - before).mean()) < 4:
            break                                            # queue full (or not enough resources)
        added += 1
        i += 1
    try:
        import cv2
        cv2.imwrite(os.path.join(BASE, "claude_out", "mat_after.png"), g.screenshot())
    except Exception:
        pass
    names = {"leather": "leather", "ore": "iron ore", "ebony": "ebony", "bone": "animal bone"}
    log(f"  materials: {added} production(s) queued" + (" (" + ", ".join(names[kinds[j % len(kinds)]] for j in range(added)) + ")" if added else " - queue already full"))
    try:
        stat("materials", added)
    except Exception:
        pass
    g.click_rel(0.745, 0.299); sleep(1.5)                    # close
    recover_screen(g)
    return True


SMART["materials"] = materials


def sunset_probe(g, sleep):
    import cv2
    from common import BASE
    if not _in_city(g):
        press_key("space"); sleep(6)
    g.click_rel(0.706, 0.962); sleep(3)                      # Campaign
    g.click_rel(0.417, 0.370); sleep(4)                      # Sunset Canyon
    g.click_rel(0.500, 0.709); sleep(4)                      # CHALLENGE
    img = g.screenshot()
    cv2.imwrite(os.path.join(BASE, "claude_out", "sc3.png"), img)
    i = _canyon_weakest(g, img)
    g.click_rel(0.667, CANYON_ROWS[i] - 0.014); sleep(5)     # CHALLENGE on the weakest opponent
    cv2.imwrite(os.path.join(BASE, "claude_out", "sc4.png"), g.screenshot())
    return True


CANYON_ROWS = [0.439, 0.502, 0.564, 0.627, 0.689]            # y of the opponents' power lines


def _canyon_weakest(g, img):
    """Index of the opponent with the lowest power (OCR); 0 if nothing could be read."""
    import re
    h, w = img.shape[:2]
    best, bi = None, 0
    for i, y in enumerate(CANYON_ROWS):
        t = _ocr_image(img[int((y - 0.014) * h):int((y + 0.014) * h), int(0.345 * w):int(0.45 * w)], "canyon_p.png", ("plain", "bin"))
        d = re.sub(r"[^0-9]", "", t or "")
        if len(d) >= 6:
            v = int(d)
            log(f"    canyon opponent {i + 1}: power {v:,}")
            if best is None or v < best:
                best, bi = v, i
    return bi


SMART["sunset_probe"] = sunset_probe


# ---------------- Sunset Canyon (v86): free challenge attempts only ----------------
def _canyon_attempts(g, img):
    import re
    h, w = img.shape[:2]
    t = _ocr_image(img[int(0.305 * h):int(0.33 * h), int(0.48 * w):int(0.63 * w)], "canyon_att.png", ("plain", "bin"))
    m = re.search(r"(\d+)\s*/\s*(\d+)", t or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def sunset_canyon(g, sleep, max_battles=7):
    """Campaign → Sunset Canyon → CHALLENGE → weakest opponent → Skip Battle → OK, while free attempts remain.
    Never REFRESH (costs gems after the free ones), never buys attempts."""
    import cv2, control, time as _t
    from common import close_gem_dialogs, BASE
    if not _in_city(g):
        press_key("space"); sleep(6)
    g.click_rel(0.706, 0.962); sleep(3)                      # Campaign
    g.click_rel(0.417, 0.370); sleep(5)                      # Sunset Canyon
    fought = 0
    for _ in range(int(max_battles)):
        cb = g.find_image("canyon_challenge", 0.8)
        if not cb:
            log("  ! sunset_canyon: the Sunset Canyon page is not open")
            break
        g.click_rel(*cb[0]); sleep(4)                        # opponent list
        img = g.screenshot()
        if not g.find_image("canyon_list_title", 0.8, img=img):
            log("  ! sunset_canyon: the opponent list did not open")
            break
        left, total = _canyon_attempts(g, img)
        if left is not None:
            control.CITY["canyon"] = f"{left}/{total}"
            if left <= 0:
                log("  - sunset_canyon: no free attempts left today")
                break
        i = _canyon_weakest(g, img)
        g.click_rel(0.667, CANYON_ROWS[i] - 0.014); sleep(5)  # CHALLENGE the weakest
        if close_gem_dialogs(g):
            log("  ! sunset_canyon: a gem window appeared - answered NO and stopped")
            break
        sk = g.find_image("canyon_skip_off", 0.85)
        if sk:
            g.click_rel(*sk[0]); sleep(1)                    # tick Skip Battle
        ok = g.find_image("canyon_ok", 0.8)
        if not ok:
            log("  ! sunset_canyon: the battle OK button was not found")
            cv2.imwrite(os.path.join(BASE, "claude_out", "canyon_err.png"), g.screenshot())
            break
        g.click_rel(*ok[0]); sleep(8)                        # battle (skipped)
        fought += 1
        for _k in range(8):                                  # result screen → back to the canyon page
            if g.find_image("canyon_challenge", 0.8):
                break
            g.click_rel(0.5, 0.88); sleep(2.5)
        cv2.imwrite(os.path.join(BASE, "claude_out", "canyon_last.png"), g.screenshot())
    control.CITY["canyon_read"] = _t.strftime("%H:%M")
    log(f"  sunset_canyon: {fought} battle(s) fought (free attempts only)")
    for _k in range(3):
        if _in_city(g) or _on_map(g):
            break
        g.click_rel(0.021, 0.025); sleep(2.5)                # back
    recover_screen(g)
    return True


SMART["sunset_canyon"] = sunset_canyon


# ---------------- TASK-10: Guardians hunter (no AP, no potions; commanders from the "guardians" preset) ----------------
GUARD_STATE = {"warned": 0.0}


def hunt_guardians(g, sleep, max_attacks=2, search_radius=2):
    """Zoomed-out map around the city -> a guardian (template guardian*.png, recorded once with record.py) ->
    ATTACK -> New Troop with the dashboard "guardians" commanders -> MARCH. A window asking for action points or
    items is closed (esc) and the hunt stops: it never uses AP items or gems."""
    import glob, pyautogui, time as _t
    from common import TEMPL_DIR, BUILTIN_DIR, close_gem_dialogs
    names = sorted({os.path.splitext(os.path.basename(f))[0] for d in (TEMPL_DIR, BUILTIN_DIR)
                    for f in glob.glob(os.path.join(d, "guardian*.png"))})
    if not names:
        if _t.time() - GUARD_STATE["warned"] > 24 * 3600:
            GUARD_STATE["warned"] = _t.time()
            log("  - hunt_guardians: no guardian picture yet (record 'guardian' once with record.py on the map)")
            notify("info", "صيد الحراس: سجّل صورة الحارس مرة واحدة (guardian) من الخريطة حتى يتعرّف عليه البوت.")
        return True
    if _queue_full(g) or _march_cap_reached(g, "hunt_guardians"):
        log("  hunt_guardians: no free march slot")
        return True
    if _on_map(g):
        press_key("space"); sleep(4)
    if not goto_map(g, sleep, "hunt_guardians"):
        return True
    cx, cy = g.to_screen(0.5, 0.5)
    pyautogui.moveTo(cx, cy)
    for _ in range(2):
        pyautogui.scroll(-5 * 120); sleep(2)
    pan_max = {1: 0, 2: 4, 3: len(GEM_PANS)}.get(int(search_radius or 2), 4)
    sent, pans, tried, t0 = 0, 0, [], _t.time()
    while sent < int(max_attacks) and pans <= pan_max and _t.time() - t0 < _search_deadline() * 8:
        hits = []
        for n in names:
            try:
                hits += g.find_image(n, 0.8, find_all=True) or []
            except Exception:
                pass
        hits = [h for h in hits if all(abs(h[0] - t[0]) > 0.04 or abs(h[1] - t[1]) > 0.04 for t in tried)]
        if not hits:
            if pans >= pan_max:
                break
            x1, y1, x2, y2 = GEM_PANS[pans]
            _drag(g, x1, y1, x2, y2); sleep(2)
            pans += 1
            continue
        rx, ry = hits[0]
        tried.append((rx, ry))
        g.click_rel(rx, ry); sleep(2.5)
        at = g.find_image("btn_attack_red", 0.78)
        if not at:
            log("  - hunt_guardians: no ATTACK button on this guardian (already attacked?)")
            press_key("esc"); sleep(1)
            continue
        g.click_rel(*at[0]); sleep(3)
        if close_gem_dialogs(g) or g.find_image("btn_use", 0.85):
            log("  ! hunt_guardians: the game asks for action points / items - never used; hunt stopped")
            press_key("esc"); sleep(1)
            break
        nt = g.find_image("btn_new_troop", 0.78)
        if not nt:
            log("  hunt_guardians: all march slots are busy")
            press_key("esc"); sleep(1)
            break
        g.click_rel(*nt[0]); sleep(3)
        _apply_preset(g, sleep, "guardians")
        m = g.find_image("btn_march", 0.78)
        if not m:
            recover_screen(g)
            break
        g.click_rel(*m[0]); sleep(3)
        if g.find_image("btn_march", 0.78):
            log("  hunt_guardians: no troops left to send")
            press_key("esc"); sleep(1)
            break
        sent += 1
        log(f"  hunt_guardians: army sent to a guardian ({sent}/{int(max_attacks)})")
    if _on_map(g):
        press_key("space"); sleep(4)
    log(f"  hunt_guardians: {sent} attack(s) sent")
    return True


SMART["hunt_guardians"] = hunt_guardians


# ---------------- heal / build / research (v91) ----------------
_OCR_CACHE = {}          # fingerprint -> (time, result)


def _ocr_fingerprint(img_bgr):
    """v182: cheap identity of a picture (64x64 thumbnail), used as the OCR cache key."""
    try:
        import cv2, hashlib
        small = cv2.resize(img_bgr, (64, 64), interpolation=cv2.INTER_AREA)
        return hashlib.sha1(small.tobytes()).hexdigest()
    except Exception:
        return None


def _ocr_cached(kind, img_bgr, scale, compute):
    """v182: run `compute` once per picture for a few seconds."""
    import time as _t
    key = (_ocr_fingerprint(img_bgr), kind, round(float(scale), 1))
    now = _t.time()
    hit = _OCR_CACHE.get(key)
    if hit and now - hit[0] < 4.0:
        return hit[1]
    value = compute()
    if key[0] is not None:
        _OCR_CACHE[key] = (now, value)
        if len(_OCR_CACHE) > 12:
            oldest = min(_OCR_CACHE, key=lambda k: _OCR_CACHE[k][0])
            _OCR_CACHE.pop(oldest, None)
    return value


def _ocr_boxes(img_bgr, name="ocr_boxes.png", scale=2.0):
    """v182: cached OCR with positions."""
    return _ocr_cached("boxes", img_bgr, scale,
                       lambda: _ocr_boxes_uncached(img_bgr, name, scale))


def _ocr_boxes_uncached(img_bgr, name="ocr_boxes.png", scale=2.0):
    """Windows OCR with positions: [(x1, y1, x2, y2, text)] in the ORIGINAL image pixels."""
    import cv2, subprocess
    from common import BASE
    big = cv2.resize(img_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    path = os.path.join(BASE, "claude_out", name)
    cv2.imwrite(path, big)
    out = []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            os.path.join(BASE, "ocr_boxes.ps1"), path],
                           capture_output=True, timeout=60, creationflags=0x08000000)
        raw = r.stdout or b""
        try:
            txt = raw.decode("utf-8")
        except UnicodeDecodeError:
            txt = raw.decode("cp1252", errors="replace")
        r.stdout, r.stderr = txt, (r.stderr or b"").decode("utf-8", errors="replace")
        for ln in r.stdout.splitlines():
            p = ln.split("|", 4)
            if len(p) == 5 and p[0].lstrip("-").isdigit():
                out.append((int(p[0]) / scale, int(p[1]) / scale, int(p[2]) / scale, int(p[3]) / scale, p[4].strip()))
        if not out:
            log(f"    (ocr_boxes: nothing - out={r.stdout[:150]!r} err={r.stderr[:200]!r})")
    except Exception as e:
        log(f"    (ocr_boxes failed: {e!r})")
    return out


def _queue_card(g, sleep, y):
    """☰ Queue Overview → tap a card (the game jumps to that building and selects it)."""
    if not _in_city(g):
        press_key("space"); sleep(6)
    g.click_rel(0.019, 0.143); sleep(2.5)
    if not g.find_image("queue_title", 0.8):
        return False
    g.click_rel(0.09, y); sleep(3)
    return True


QUEUE_WORDS = {
    "heal": ("hospital", "healing", "hospital capacity", "مستشفى", "علاج", "المستشفى"),
    "build": ("building", "upgrad", "build", "بناء", "ترقية"),
    "res": ("research", "tech", "بحث", "تكنولوجيا"),
    "train": ("train", "barracks", "archery", "stable", "siege", "تدريب", "ثكنات", "الرماية", "إسطبل", "الحصار"),
}



QUEUE_ROWS_KEY = {"stable": "cavalry", "barracks": "infantry", "archery": "archer", "siege": "siege"}


SCREEN_TEMPLATES = (
    ("city", "queue_btn", 0.55),          # v188: the city HUD carries the queue button
    ("start", "click_to_start", 0.80),
    ("training_window", "btn_train", 0.80),
    ("gem_dialog", "notice_title", 0.80),
    ("map", "space_on_city", 0.75),
)

SCREEN_WORDS = (
    ("queue_panel", ("queue overview",)),
    ("profile", ("action points", "civilization", "highest acclaim")),
    ("mail", ("new mail", "bulk editor", "read & claim all")),
    ("alliance", ("technology", "territory", "alliance gifts")),
    ("tavern", ("free chests", "legendary chests")),
    ("training_window", ("unit training", "instant", "train")),
)


CLICK_PROBED = [False]


def probe_click_mode(g, sleep, force=False):
    """v183: find a click method that reaches the game, using a harmless action (the queue panel).

    Runs once per process unless force=True. Returns the mode that worked.
    """
    if CLICK_PROBED[0] and not force:
        return click_mode()
    CLICK_PROBED[0] = True
    start = click_mode()
    for mode in ("absolute", "message", "cursor"):
        if mode == "interception":
            continue
        try:
            set_click_mode(mode)
        except Exception:
            continue
        try:
            boxes, img = queue_panel(g, sleep)
        except Exception:
            boxes, img = [], None
        if img is not None:
            try:
                queue_close(g, sleep)
            except Exception:
                pass
            log(f"  click mode: '{mode}' reaches the game")
            return mode
        log(f"  click mode: '{mode}' did not reach the game")
    log("  ! no click method reached the game - keeping the previous one")
    try:
        set_click_mode(start)
    except Exception:
        pass
    return start


def what_screen(g, img=None):
    """v176: name the screen in front of the bot.

    Returns one of: start, training_window, gem_dialog, map, city, queue_panel, profile, mail,
    alliance, tavern, unknown.
    """
    try:
        picture = img if img is not None else g.screenshot()
    except Exception:
        return "unknown"
    for name, template, thr in SCREEN_TEMPLATES:
        try:
            if g.find_image(template, thr, img=picture):
                return name
        except Exception:
            pass
    try:
        boxes = _ocr_boxes(picture, "screen_type.png", 1.6)
    except Exception:
        return "unknown"
    text = " ".join((t or "").lower() for *_xy, t in boxes)
    if not text.strip():
        return "unknown"
    for name, words in SCREEN_WORDS:
        if any(wd in text for wd in words):
            return name
    return "unknown"


FAILURE_FILE = os.path.join(BASE, "failures.jsonl")


def _save_failure(g, label, note="", point=None):
    """v178: keep the picture of a failed action, plus one line in failures.jsonl."""
    import datetime as _dt
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (label or "action"))[:40]
    folder = os.path.join(BASE, "claude_out")
    path = ""
    try:
        import cv2
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"fail_{safe}_{stamp}.png")
        cv2.imwrite(path, g.screenshot())
    except Exception as e:
        log(f"  ! could not save the failure picture: {e!r}")
    try:
        screen = what_screen(g)
    except Exception:
        screen = "?"
    try:
        import json as _json
        with open(FAILURE_FILE, "a", encoding="utf-8") as f:
            f.write(_json.dumps({"time": stamp, "label": label, "screen": screen, "note": note,
                                 "point": list(point) if point else None,
                                 "file": path}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    log(f"  ! failure saved: {label} on screen '{screen}' -> {os.path.basename(path)}")
    return path


def click_verified(g, point, sleep, expect=None, wait=2.0, tries=2, label=""):
    """v178: click, then prove the screen reacted. Retries once, then reports a failure.

    expect : a screen name from what_screen() that must appear after the click
    Returns True when the click had a visible effect (or produced `expect`).
    """
    name = label or f"click {point[0]:.3f},{point[1]:.3f}"
    for attempt in range(max(1, tries)):
        try:
            before = g.screenshot()
        except Exception as e:
            log(f"  verify: no picture before '{name}': {e!r}")
            return False
        try:
            g.click_rel(point[0], point[1])
        except Exception as e:
            log(f"  verify: click failed for '{name}': {e!r}")
        sleep(wait)
        try:
            after = g.screenshot()
        except Exception:
            return False
        if expect:
            try:
                if what_screen(g, img=after) == expect:
                    return True
            except Exception:
                pass
        try:
            change = float(abs(after.astype(int) - before.astype(int)).mean())
        except Exception:
            change = 0.0
        if change > 1.5:
            return True
        log(f"  verify: '{name}' did nothing (picture change {change:.2f}), try {attempt + 1}/{tries}")
        if attempt == 0:
            try:
                recover_screen(g)
            except Exception:
                pass
    _save_failure(g, name, note="the click produced no visible change", point=point)
    return False


def learn_element_from_failure(g, sleep, half=32):
    """v180: crop the last failed element as a template and add it to the registry.

    Returns the element name, or None when there is no usable failure record.
    """
    import json as _json
    import datetime as _dt
    try:
        lines = [ln for ln in open(FAILURE_FILE, encoding="utf-8").read().splitlines() if ln.strip()]
        record = _json.loads(lines[-1])
    except Exception as e:
        log(f"  ! learn_element: no failure record ({e!r})")
        return None
    point = record.get("point")
    if not point:
        log("  ! learn_element: the last failure has no click point")
        return None
    try:
        import cv2
        picture = g.screenshot()
        h, w = picture.shape[:2]
        cx, cy = int(point[0] * w), int(point[1] * h)
        x1, y1 = max(0, cx - half), max(0, cy - half)
        crop = picture[y1:cy + half, x1:cx + half]
        if crop is None or crop.size == 0:
            log("  ! learn_element: the crop was empty")
            return None
        stamp = _dt.datetime.now().strftime("%H%M%S")
        name = "learned_%s_%s" % ("".join(ch if ch.isalnum() else "_" for ch in record.get("label", "x"))[:24], stamp)
        folder = os.path.join(BASE, "builtin_templates")
        os.makedirs(folder, exist_ok=True)
        cv2.imwrite(os.path.join(folder, name + ".png"), crop)
        reg = load_json(UI_REGISTRY_FILE, {}) or {}
        elements = reg.setdefault("elements", {})
        elements[name] = {"template": name,
                          "note": "learned from a failure at %s (screen %s)" % (record.get("time"), record.get("screen"))}
        save_json(UI_REGISTRY_FILE, reg)
        _UI_CACHE[0] = 0.0        # force a registry reload
        log(f"  learned element '{name}' from the last failure (size {crop.shape[1]}x{crop.shape[0]})")
        return name
    except Exception as e:
        log(f"  ! learn_element failed: {e!r}")
        return None


def ensure_screen(g, sleep, target, tries=3):
    """v176: get the game to `target` (city / map / queue_panel / training_window).

    Returns the screen name that is showing at the end.
    """
    screen = what_screen(g)
    if screen == target:
        return screen
    if target == "city" and screen == "map":
        log("  screen: map -> city (SPACE)")
        press_key("space"); sleep(5)
        screen = what_screen(g)
        if screen == "city":
            return screen
    for _ in range(tries):
        log(f"  screen: {screen} -> wanted {target}, recovering")
        try:
            recover_screen(g)
        except Exception:
            pass
        sleep(1.5)
        screen = what_screen(g)
        if screen == target:
            return screen
    log(f"  screen: still {screen} (wanted {target})")
    return screen


def goto_map(g, sleep, label=""):
    """v179: make sure the map is showing. Returns True when it is."""
    screen = ensure_screen(g, sleep, "map")
    if screen != "map":
        log(f"  ! {label or 'task'}: could not reach the map (screen: {screen})")
        return False
    return True


def queue_panel(g, sleep):
    """v164: open the game's Queue Overview (the three-line button at the top-left).

    The button is found by its picture (queue_btn) so it follows any window size; the panel is
    confirmed by its own title. Returns (ocr boxes, screenshot) or ([], None)."""
    def read(img):
        h, w = img.shape[:2]
        boxes = _ocr_boxes(img[:, :int(0.45 * w)], "queue_ocr.png", max(1.5, min(3.0, 900.0 / max(1, w))))
        if any("queue overview" in t.lower() for *_xy, t in boxes):
            return boxes, True
        try:                                  # v197: on a small window the title OCR fails - trust the panel colour
            import queue_manager
            return boxes, queue_manager.panel_visible(img)
        except Exception:
            return boxes, False

    # v185: the button is part of the city HUD; on the map the click reaches nothing
    screen_now = what_screen(g)
    if screen_now != "city":
        log(f"  queue: screen is {screen_now} - going to the city first")
        if ensure_screen(g, sleep, "city", tries=2) != "city":
            log("  queue: the city is not showing")
            return [], None

    img = g.screenshot()
    boxes, opened = read(img)
    if opened:                       # v165: already open - do not click the button again
        return boxes, img

    spot = find_element(g, "queue_button", img=img)
    spots = [spot] if spot else [(0.0219, 0.1332), (0.019, 0.148), (0.019, 0.143)]
    for attempt in range(2):                 # v170: a missed click is retried once after ESC
        for spot in spots:
            g.click_rel(spot[0], spot[1]); sleep(2.2)
            img = g.screenshot()
            boxes, opened = read(img)
            if opened:
                return boxes, img
        if attempt == 0:
            press_key("esc"); sleep(1.2)
            img = g.screenshot()
            hits = g.find_image("queue_btn", 0.55, img=img)
            spots = [hits[0]] if hits else spots
    _save_failure(g, "queue_button", note="the Queue Overview did not open")   # v178
    return [], None


def queue_close(g, sleep):
    """v177: close the Queue Overview, but only when it is really open (ESC on a clear screen is
    refused by the safety guard and only filled the log)."""
    try:
        if what_screen(g) != "queue_panel":
            return
    except Exception:
        pass
    press_key("esc"); sleep(1.0)


def queue_goto_unit(g, sleep, troop_key):
    """v164: tap the troop row (cavalry / infantry / archer / siege) in the Queue Overview.

    The game then jumps to that building and selects it, which is the route the user described.
    Returns True when a row was tapped."""
    try:                                     # v199: the Queue Overview reader (folded sections, scrolling, small windows)
        import queue_manager
        if queue_manager.tap_row(g, sleep, "train", match=lambda r: queue_manager.unit_of(r["name"]) == troop_key):
            log(f"  queue: tapped the {troop_key} row")
            return True
    except Exception as e:
        log(f"  ! queue: unit row via queue_manager failed: {e!r}")
    boxes, img = queue_panel(g, sleep)
    if not boxes:
        return False
    vocab = TROOP_WORDS.get(troop_key, ())
    h, w = img.shape[:2]

    # v166: only rows inside the "Unit Training" section may be tapped. Without this, the
    # RESEARCH row "Long Swordsman Lvl 1" matched "swordsman" and the bot jumped to research.
    def header_y(word):
        for x1, y1, x2, y2, t in boxes:
            if word in (t or "").lower():
                return (y1 + y2) / 2.0
        return None

    top = header_y("unit training")
    bottom = header_y("unit healing") or header_y("building queues")
    for x1, y1, x2, y2, txt in boxes:
        t = (txt or "").lower()
        if not any(v in t for v in vocab):
            continue
        cy = (y1 + y2) / 2.0
        if top is not None and cy < top:
            continue
        if bottom is not None and cy > bottom:
            continue
        if any(bad in t for bad in ("lvl", "level", "queue", "research")):
            continue
        y = (y1 + y2) / 2.0 / h
        g.click_rel(0.10, y); sleep(3.0)
        log(f"  queue: tapped '{txt}' ({troop_key})")
        # v165: the game jumps to the building; close the list so its buttons are visible
        img2 = g.screenshot()
        h2, w2 = img2.shape[:2]
        still = _ocr_boxes(img2[:, :int(0.45 * w2)], "queue_after.png", 1.5)
        if any("queue overview" in t.lower() for *_xy, t in still):
            press_key("esc"); sleep(1.2)
        return True
    log(f"  queue: no {troop_key} row on the panel")
    queue_close(g, sleep)
    return False


def queue_goto(g, sleep, kind, words=None):
    """v153: open ☰ and jump to the row of `kind` (the game selects that building).

    Used for anything that is already running - healing, a building upgrade, research, a
    training queue - where tapping the right row is far more reliable than a city position.
    `words` overrides the vocabulary (e.g. the name of one military building).
    """
    sec = {"build": "build", "res": "research", "heal": "heal"}.get(kind)
    if sec and not words:                    # v199: tap the ROW (Building Queue 1 / Tech Research), never the header
        try:
            import queue_manager
            if queue_manager.tap_row(g, sleep, sec, prefer_idle=(sec == "build")):
                return True
        except Exception as e:
            log(f"  ! queue: {kind} row via queue_manager failed: {e!r}")
    # v166: the same templated panel the training uses (the old fixed spots missed the button)
    boxes, img = queue_panel(g, sleep)
    if not boxes:
        return False
    vocab = words or QUEUE_WORDS.get(kind, (kind,))
    h = img.shape[0]
    for x1, y1, x2, y2, txt in boxes:
        t = _norm_text(txt)
        if t and any(_norm_text(wd) and _norm_text(wd) in t for wd in vocab):
            y = (y1 + y2) / 2.0 / h
            g.click_rel(0.10, y); sleep(3)
            log(f"  queue: jumped to '{txt[:40]}' ({kind})")
            return True
    g.click_rel(0.188, 0.500); sleep(1.5)
    if g.find_image("queue_title", 0.8):
        recover_screen(g)
    return False


def _use_speedups(g, sleep, kind):
    """v153: use speedup ITEMS on the queue that is running (healing / building / research).

    Same rules as fast training: one item per call, speedup items only, and any "spend gems"
    window is refused. When the speedup window is not recognised nothing else is clicked.
    """
    n = _training_speedup(g, sleep, kind)
    if n:
        log(f"    {kind}: used {n} speedup item(s)")
    else:
        log(f"    {kind}: no speedup used (window not recognised or nothing running)")
    return n


def heal(g, sleep, speedups=False, use_bag=False):
    """Hospital: press the blue HEAL (resources) - never INSTANT, never gems."""
    from common import close_gem_dialogs
    import control
    hosp = control.CITY.get("hospital", "")
    if hosp.startswith("0/"):
        log("  - heal: no wounded troops")
        return True
    # v167: the queue panel only lists a "Unit Healing" section header, not the hospital, so
    # heal goes straight to the building (found by name) - the same lookup that works for training.
    import queue_manager
    hx = None
    if queue_manager.tap_row(g, sleep, "heal"):          # v197: Queue Overview > Unit Healing -> the hospital
        hx = g.find_image("hex_heal", 0.8)
        if not hx:
            g.click_rel(0.5, 0.5); sleep(2)                 # the camera is on the hospital - select it
            hx = g.find_image("hex_heal", 0.8)
    if not hx:
        pt = find_building(g, sleep, "hospital")
        if not pt:
            log("  ! heal: the hospital was not found in this city")
            recover_screen(g)
            return True
        g.click_rel(*pt); sleep(2)
        hx = g.find_image("hex_heal", 0.8)
    if not hx:
        log("  - heal: the hospital is already healing (or no heal button)")
        if speedups:
            _use_speedups(g, sleep, "healing")
        recover_screen(g); return True
    g.click_rel(*hx[0]); sleep(3)
    if not g.find_image("heal_title", 0.8):
        log("  ! heal: the healing window did not open"); recover_screen(g); return True
    b = g.find_image("btn_heal_blue", 0.8)
    if not b:
        log("  - heal: nothing to heal"); recover_screen(g); return True
    g.click_rel(*b[0]); sleep(3)
    if close_gem_dialogs(g):
        log("  - heal: not enough resources (gem offer refused)" + (" - bag resources not learned yet" if use_bag else ""))
    elif g.find_image("heal_title", 0.8):
        log("  ! heal: the HEAL did not start (resources?)")
    else:
        log("  heal: healing started with resources")
        if speedups:
            _use_speedups(g, sleep, "healing")
    recover_screen(g)
    return True


def build_upgrade(g, sleep, mode="smart", speedups=False, use_bag=False):
    """Free builder → the game's own suggestion from the Queue Overview (Building Queue 1) → blue Upgrade.
    Never INSTANT, never gems. mode 'smart' = City Hall line first (falls back to the game's suggestion)."""
    from common import close_gem_dialogs
    import control
    busy = [q for q in control.CITY.get("queues", []) if q.get("kind") == "build" and not q.get("done")]
    if len(busy) >= 2:
        log("  - build_upgrade: both builders are busy"); return True
    if not queue_goto(g, sleep, "build") and not _queue_card(g, sleep, 0.462):
        log("  ! build_upgrade: the Queue Overview did not open"); recover_screen(g); return True
    import queue_manager as _qm
    sleep(1.0)
    spot = _qm.glowing_button(g)                         # v204: the row selects the building; Upgrade glows under it
    if spot:
        g.click_rel(*spot); sleep(3)
    else:
        up = g.find_image("hex_upgrade", 0.85)
        if not up:
            log("  - build_upgrade: no free builder / no upgrade button"); _save_failure(g, "build_row", note="no glowing button"); recover_screen(g); return True
        g.click_rel(*up[0]); sleep(3)
    img = g.screenshot()
    h, w = img.shape[:2]
    title = _qm.window_title(g, img) or " ".join(_ocr_lines(img[int(0.285 * h):int(0.32 * h), int(0.3 * w):int(0.7 * w)], "build_title.png", scale=2))
    b = g.find_image("btn_upgrade_blue", 0.8, img=img)
    if not b:                                            # v204: the blue UPGRADE button by its text (never INSTANT)
        hits = [x for x in _ocr_boxes(img[int(0.5 * h):, int(0.5 * w):], "build_btn.png", 1.8)
                if "upgrade" in x[4].lower() and "instant" not in x[4].lower()]
        if hits:
            x1, y1, x2, y2, _t = hits[-1]
            b = [((int(0.5 * w) + (x1 + x2) / 2) / w, (int(0.5 * h) + (y1 + y2) / 2) / h)]
    if not b:
        log(f"  - build_upgrade: '{title}' cannot be upgraded now (requirements?)"); recover_screen(g); return True
    g.click_rel(*b[0]); sleep(3)
    if close_gem_dialogs(g):
        log(f"  - build_upgrade: not enough resources for '{title}' (gem offer refused)"
            + (" - bag resources not learned yet" if use_bag else ""))
    elif g.find_image("btn_upgrade_blue", 0.8):
        log(f"  ! build_upgrade: '{title}' did not start")
    else:
        log(f"  build_upgrade: started - {title}" + ("" if mode == "all" else "  (smart mode uses the game's suggestion for now)"))
        if speedups:
            _use_speedups(g, sleep, "building")
    recover_screen(g)
    return True


RES_STATE = {"last": "military"}


def research(g, sleep, focus="balanced", speedups=False, use_bag=False):
    """Academy (via Queue Overview → Tech Research): pick a tech that is not at max level and research it."""
    import re, cv2
    from common import close_gem_dialogs, BASE
    import control
    if any(q.get("kind") == "res" and not q.get("done") for q in control.CITY.get("queues", [])):
        log("  - research: a research is already running"); return True
    if not queue_goto(g, sleep, "res") and not _queue_card(g, sleep, 0.585):
        log("  ! research: the Queue Overview did not open"); recover_screen(g); return True
    try:                                                 # v204: row -> Academy selected -> its glowing Research button
        import queue_manager as _qm
        sleep(1.0)
        spot = _qm.glowing_button(g)
        if spot:
            g.click_rel(*spot); sleep(3)
            log(f"    research: academy window '{_qm.window_title(g)[:40]}'")
            cv2.imwrite(os.path.join(BASE, "claude_out", "res_window.png"), g.screenshot())
    except Exception as e:
        log(f"    ! research: glowing button: {e!r}")
    tab = focus
    if focus == "balanced":
        tab = "economy" if RES_STATE["last"] == "military" else "military"
    RES_STATE["last"] = tab
    g.click_rel(0.19, 0.37 if tab == "economy" else 0.461); sleep(2.5)
    for _ in range(6):                                       # scroll to the start of the tree
        _drag(g, 0.30, 0.52, 0.72, 0.52, 0.4); sleep(0.8)
    started = False
    for page in range(10):
        img = g.screenshot()
        h, w = img.shape[:2]
        x0, y0 = int(0.225 * w), int(0.32 * h)
        crop = img[y0:int(0.73 * h), x0:int(0.77 * w)]
        import numpy as _np
        bb, gg, rr = [crop[:, :, i].astype(int) for i in range(3)]
        bm = ((bb > 110) & (rr < 80) & (gg < 150) & (gg > 40)).astype(_np.uint8) * 255
        n_, _l, st_, _c = cv2.connectedComponentsWithStats(bm)
        bars = sorted([tuple(st_[i][:4]) for i in range(1, n_) if st_[i][2] > 30 and 4 <= st_[i][3] <= 20], key=lambda t: (t[1], t[0]))
        parts = []
        for (bx, by, bw, bh) in bars:
            pc = crop[max(0, by - 2):by + bh + 2, max(0, bx - 4):bx + bw + 4]
            pc = cv2.resize(pc, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            pm = _np.where(pc.min(axis=2) > 180, 0, 255).astype(_np.uint8)
            n2, l2, st2, _c2 = cv2.connectedComponentsWithStats(255 - pm)
            for i2 in range(1, n2):                          # drop the bar outline / edges
                x2_, y2_, w2_, h2_, _a2 = st2[i2]
                if x2_ == 0 or y2_ == 0 or x2_ + w2_ >= pm.shape[1] or y2_ + h2_ >= pm.shape[0] or w2_ > 0.5 * pm.shape[1]:
                    pm[l2 == i2] = 255
            pm = cv2.erode(pm, _np.ones((3, 3), _np.uint8))     # thicker digits for the OCR
            parts.append(cv2.copyMakeBorder(pm, 16, 16, 30, 30 + max(0, 400 - pm.shape[1]), cv2.BORDER_CONSTANT, value=255))
        boxes, cands = [], []
        if parts:
            wmax = max(p_.shape[1] for p_ in parts)
            sheet = _np.vstack([cv2.copyMakeBorder(p_, 0, 0, 0, wmax - p_.shape[1], cv2.BORDER_CONSTANT, value=255) for p_ in parts])
            lines = _ocr_lines(cv2.cvtColor(sheet, cv2.COLOR_GRAY2BGR), "res_levels.png", scale=1.5)
            boxes = [(0, 0, 0, 0, t) for t in lines]
            if len(lines) == len(bars):
                for (bx, by, bw, bh), t in zip(bars, lines):
                    m = re.search(r"(\d{1,2})\s*[/|lI\s,.:;]\s*(\d{1,2})", t)
                    if m and int(m.group(1)) < int(m.group(2)):
                        cands.append(((x0 + bx + bw / 2) / w, (y0 + by + bh / 2) / h, f"{m.group(1)}/{m.group(2)}"))
            else:
                log(f"    research: {len(bars)} level bars but {len(lines)} OCR lines: {lines}")
        log(f"    research page {page + 1}: OCR {[x[4] for x in boxes][:16]} -> candidates {[c[2] for c in cands]}")
        for (cx, cy, t) in cands:
            g.click_rel(cx, cy - 0.01); sleep(2.5)           # the node (its level bar)
            img2 = g.screenshot()
            cv2.imwrite(os.path.join(BASE, "claude_out", "res_node_win.png"), img2)
            txt = " ".join(x[4] for x in _ocr_boxes(img2[int(0.28 * h):int(0.75 * h), int(0.23 * w):int(0.77 * w)], "res_node.png", 1.5)).lower()
            log(f"    research node {t}: {txt[:120]}")
            if "maximum" in txt or "require" in txt or "researching" in txt:
                g.click_rel(0.745, 0.299); sleep(1.5)        # X
                continue
            btns = [x for x in _ocr_boxes(img2[int(0.55 * h):int(0.75 * h), int(0.45 * w):int(0.77 * w)], "res_btn.png", 2.0)
                    if "research" in x[4].lower() and "instant" not in x[4].lower()]
            if not btns:
                g.click_rel(0.745, 0.299); sleep(1.5)
                continue
            bx1, by1, bx2, by2, _t = btns[0]
            g.click_rel((int(0.45 * w) + (bx1 + bx2) / 2) / w, (int(0.55 * h) + (by1 + by2) / 2) / h); sleep(3)
            if close_gem_dialogs(g):
                log("  - research: not enough resources (gem offer refused)" + (" - bag resources not learned yet" if use_bag else ""))
                g.click_rel(0.745, 0.299); sleep(1.5)
                continue
            log(f"  research: started a {tab} technology (level {t})")
            started = True
            if speedups:
                _use_speedups(g, sleep, "research")
            break
        if started:
            break
        _drag(g, 0.70, 0.52, 0.30, 0.52, 0.5); sleep(1.2)   # next part of the tree
    if not started:
        cv2.imwrite(os.path.join(BASE, "claude_out", "res_none.png"), g.screenshot())
        log(f"  - research: no {tab} technology could be started")
    recover_screen(g); sleep(1); recover_screen(g)
    return True


SMART["heal"] = heal
SMART["build_upgrade"] = build_upgrade
SMART["research"] = research


def barb_probe(g, sleep):
    """Test: search a barbarian, ATTACK, click the last non-gathering army card, save screenshots, close."""
    if _queue_cards(g):
        _barb_close(g, sleep)
    if _in_city(g) or not _on_map(g):
        press_key("space"); sleep(6)
    pos, lvl = _barb_search(g, sleep, 8, 12)
    if not pos:
        log("  barb_probe: no barbarian"); recover_screen(g); return True
    g.click_rel(*pos); sleep(3)
    _barb_shot(g, "bp_1_panel.png")
    cards = _queue_cards(g)
    free = [c for c in cards if not c[2]]
    log(f"  barb_probe: cards {cards}")
    if free:
        g.click_rel(free[-1][0], free[-1][1]); sleep(2)
        _barb_shot(g, "bp_2_card.png")
    _barb_close(g, sleep)
    _barb_shot(g, "bp_3_closed.png")
    return True


SMART["barb_probe"] = barb_probe


# ---------------- v105: mail - read everything, claim all attachments, notify private messages ----------------
MAIL_TABS = {"personal": (0.204, 0.030), "report": (0.290, 0.030), "alliance": (0.376, 0.030), "system": (0.462, 0.030)}


def _tab_badge(img, tab):
    """Red number badge on the top-right of a mail tab."""
    import cv2
    h, w = img.shape[:2]
    x, y = MAIL_TABS[tab]
    box = img[0:int(0.03 * h), int((x + 0.008) * w):int((x + 0.045) * w)]
    hsv = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)
    red = cv2.inRange(hsv, (0, 150, 120), (8, 255, 255)) | cv2.inRange(hsv, (170, 150, 120), (180, 255, 255))
    return cv2.countNonZero(red) > 25


def _mail_is_open(img):
    """Parchment bottom bar of the mail window (tan: R>190, G>150, B 90-140)."""
    h, w = img.shape[:2]
    b, gg, r = img[int(0.95 * h):int(0.98 * h), int(0.42 * w):int(0.56 * w)].reshape(-1, 3).mean(0)
    return r > 185 and gg > 150 and 80 < b < 150 and r > b + 60


def read_mail(g, sleep, personal=True, report=True, alliance=True, system=True, notify_private=True):
    """Mail (M): every chosen tab -> 'Read & Claim All' (green button, bottom left). Private messages are read
    first and sent to the dashboard / Telegram. Nothing is bought; gem windows are answered NO."""
    import hashlib
    from common import close_gem_dialogs
    if _queue_cards(g):
        _barb_close(g, sleep)
    recover_screen(g); sleep(1)
    for _ in range(2):
        press_key("m"); sleep(4)
        if _mail_is_open(g.screenshot()):
            break
        recover_screen(g); sleep(2)
    _barb_shot(g, "mail_open.png")
    if not _mail_is_open(g.screenshot()):
        log("  ! read_mail: the mail window did not open")
        recover_screen(g)
        return True
    img0 = g.screenshot()
    log("    mail badges: " + ", ".join(f"{t} {'yes' if _tab_badge(img0, t) else 'no'}" for t in MAIL_TABS))
    opened = 0
    for tab, on in (("personal", personal), ("report", report), ("alliance", alliance), ("system", system)):
        if not on:
            continue
        img = g.screenshot()
        had = _tab_badge(img, tab)
        g.click_rel(*MAIL_TABS[tab]); sleep(2.5)
        if tab == "personal" and had and notify_private:
            try:
                img = g.screenshot(); h, w = img.shape[:2]
                boxes = _ocr_boxes(img[int(0.09 * h):int(0.93 * h), int(0.18 * w):int(0.39 * w)], "mail_personal.png")
                lines = [b[4] for b in sorted(boxes, key=lambda b: (b[1], b[0])) if len(b[4].strip()) > 1][:8]
                text = " / ".join(lines)[:300]
                key = hashlib.md5(text.encode("utf-8")).hexdigest()
                d = _stats_load()
                if text and d.get("mail_seen") != key:
                    d["mail_seen"] = key
                    notify("mail", "رسالة خاصة جديدة في البريد: " + text, d)
                    _stats_save(d)
            except Exception as e:
                log(f"  ! read_mail: could not read the private mail ({e!r})")
        if not had:
            continue
        g.click_rel(0.182, 0.961); sleep(2.5)                 # Read & Claim All
        c = g.find_image("btn_confirm_blue", 0.8) or g.find_image("btn_confirm_cmd", 0.8)
        if c:
            g.click_rel(*c[0]); sleep(2)
        if close_gem_dialogs(g):
            log("  ! read_mail: a gem window appeared - answered NO")
        opened += 1
        log(f"  read_mail: {tab} - read & claimed all")
    try:
        stat("mail", opened)
    except Exception:
        pass
    g.click_rel(0.821, 0.030); sleep(2)                       # X
    recover_screen(g)
    log(f"  read_mail: {opened} tab(s) with new mail done")
    return True


SMART["read_mail"] = read_mail
SMART["mails"] = read_mail          # v148: the dashboard sends the task named "mails"; it was skipped as unknown


# ---------------- v110: characters - read them all, switch to the one picked in the dashboard ----------------
def _open_characters(g, sleep):
    recover_screen(g); sleep(1)
    if _queue_cards(g):
        _barb_close(g, sleep)
    g.click_rel(0.030, 0.040); sleep(3)                      # governor avatar -> profile
    g.click_rel(0.244, 0.910); sleep(3)                      # settings
    g.click_rel(0.150, 0.624); sleep(3)                      # Account / Characters
    return g.screenshot()


def _char_cards(img):
    """Character cards: [{name, kingdom, power, current, x, y, avatar}] from OCR of the Account/Characters page."""
    import cv2, base64, re
    h, w = img.shape[:2]
    x0, y0, x1, y1 = int(0.26 * w), int(0.40 * h), int(0.85 * w), int(0.78 * h)
    boxes = _ocr_boxes(img[y0:y1, x0:x1], "chars.png")
    boxes = [(b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0, b[4].strip()) for b in boxes if b[4].strip()]
    cards = []
    for b in boxes:
        m = re.search(r"(?:#\s*|k(?:ingdom)?\.?\s*)?(\d{3,5})\s*(.*)", b[4], re.IGNORECASE)
        if not m or not m.group(1):
            continue
        cx = (b[0] + b[2]) / 2
        same_col = [o for o in boxes if abs(o[0] - b[0]) < 0.03 * w]
        above = [o for o in same_col if 0 < b[1] - o[1] < 0.045 * h]
        below = [o for o in same_col if 0 < o[1] - b[1] < 0.035 * h]
        name = max(above, key=lambda o: o[1])[4] if above else ""
        if not name or name == "?":
            name = m.group(2).strip()
        if not name:
            name = "?"
        power = ""
        for o in below:
            pm = re.search(r"([\d,\.]{4,})", o[4])
            if pm:
                power = pm.group(1)
        ax, ay = int(b[0] - 0.045 * w), int(b[1] + 0.005 * h)  # avatar circle left of the text
        r = int(0.03 * w)
        crop = img[max(0, ay - r):ay + r, max(0, ax - r):ax + r]
        av = ""
        if crop.size:
            ok, buf = cv2.imencode(".jpg", cv2.resize(crop, (56, 56)), [cv2.IMWRITE_JPEG_QUALITY, 70])
            av = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode() if ok else ""
        chk = img[max(0, ay - r):ay + r, max(0, ax - int(1.6 * r)):max(1, ax - r // 2)]
        hsv = cv2.cvtColor(chk, cv2.COLOR_BGR2HSV) if chk.size else None
        current = bool(hsv is not None and cv2.countNonZero(cv2.inRange(hsv, (45, 120, 120), (80, 255, 255))) > 30)
        cards.append({"name": name, "kingdom": "#" + m.group(1) + " " + m.group(2).strip(), "power": power,
                      "current": current, "x": round(cx / w, 4), "y": round(((b[1] + b[3]) / 2) / h, 4), "avatar": av})
    return cards


def read_characters(g, sleep):
    """Settings > Account/Characters: read every character and send the list to the dashboard."""
    try:
        return _read_characters(g, sleep)
    finally:
        g.click_rel(0.880, 0.226); sleep(1)                  # never leave the characters page open


def _read_characters(g, sleep):
    import control, time as _t
    img = _open_characters(g, sleep)
    _barb_shot(g, "chars_page.png")
    cards = _char_cards(img)
    control.CITY["characters"] = cards
    control.CITY["characters_at"] = _t.strftime("%Y-%m-%d %H:%M")
    if cards:
        _persist_save()
    log(f"  read_characters: {len(cards)} character(s): " + ", ".join(f"{c['name']} ({c['kingdom']}){' *' if c['current'] else ''}" for c in cards))
    g.click_rel(0.880, 0.226); sleep(2)                      # settings X
    recover_screen(g)
    return True


def _click_yes(g, sleep):
    """'Character Login - Log in as this character?' -> the cyan YES button (right of the red NO)."""
    import cv2
    img = g.screenshot(); h, w = img.shape[:2]
    y0, y1, x0, x1 = int(0.52 * h), int(0.70 * h), int(0.50 * w), int(0.72 * w)
    hsv = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (85, 120, 180), (105, 255, 255))
    n, _, st, cen = cv2.connectedComponentsWithStats(m)
    b = max(range(1, n), key=lambda k: st[k][4], default=None)
    if b is None or st[b][4] < 1500:
        return False
    g.click_rel((x0 + cen[b][0]) / w, (y0 + cen[b][1]) / h); sleep(3)
    return True


def _match_char(cards, name, kingdom=""):
    """v136: the card for this name - exact/contained first, then a close OCR match (one or two letters off).
    v148: compare cleaned names only. The dashboard stores names like "[96SBArchLord" while the game
    card reads "96SBArchLord"; the bracket used to make every switch fail with 'not found'."""
    import difflib, re as _re

    def clean(s):
        return _re.sub(r"[^0-9a-z\u0600-\u06ff]+", "", (s or "").lower())

    nm = clean(name)                     # "[96SBArchLord" -> "96sbarchlord"
    if not nm:
        return []
    kd = clean((kingdom or "").split()[0]) if (kingdom or "").split() else ""
    pool = [c for c in cards if not kd or kd in clean(c["kingdom"])] or cards
    want = [c for c in pool if nm in clean(c["name"]) or (len(clean(c["name"])) >= 3 and clean(c["name"]) in nm)]
    if not want:
        best = max(pool, key=lambda c: difflib.SequenceMatcher(None, nm, clean(c["name"])).ratio(), default=None)
        if best and difflib.SequenceMatcher(None, nm, clean(best["name"])).ratio() >= 0.7:
            want = [best]
    return want


def switch_character(g, sleep, name="", kingdom=""):
    """Switch to the character with this name (and kingdom) - picked in the dashboard."""
    img = _open_characters(g, sleep)
    cards = _char_cards(img)
    want = _match_char(cards, name, kingdom)
    if not want:
        log(f"  ! switch_character: '{name}' not found on the characters page (read: " + ", ".join(x["name"] for x in cards) + ")")
        _barb_shot(g, "chars_notfound.png")
        g.click_rel(0.880, 0.226); sleep(2); recover_screen(g)
        return "notfound"
    c = want[0]
    if c["current"]:
        log(f"  switch_character: {c['name']} is already the active character")
        g.click_rel(0.880, 0.226); sleep(2); recover_screen(g)
        return "already"
    g.click_rel(c["x"], c["y"]); sleep(3)
    _barb_shot(g, "chars_confirm.png")
    if not _click_yes(g, sleep):
        log("  ! switch_character: the YES button was not found - nothing switched")
        g.click_rel(0.880, 0.226); sleep(2); recover_screen(g)
        return "noyes"
    log(f"  switch_character: switching to {c['name']} ({c['kingdom']}) - the game reloads")
    sleep(40)
    for _ in range(6):
        recover_screen(g); sleep(5)
    return "switched"


SMART["read_characters"] = read_characters
SMART["switch_character"] = switch_character


def _profile_open(img):
    """Governor profile panel: blue panel on the left (x 0.02-0.27, y 0.30-0.55)."""
    h, w = img.shape[:2]
    b, gg, r = img[int(0.30 * h):int(0.55 * h), int(0.03 * w):int(0.26 * w)].reshape(-1, 3).mean(0)
    return b > 110 and b > r + 50


def restore_character(g, sleep, name="ArchLord", steps=40):
    """v111: get back to the main character after an accidental switch - walks through the returning-player
    tutorial (dialogs, glowing targets) until the governor profile opens, then switches character."""
    import cv2, numpy as np
    for i in range(int(steps)):
        img = g.screenshot()
        h, w = img.shape[:2]
        if not _profile_open(img):
            g.click_rel(0.030, 0.040); sleep(3)
            img = g.screenshot()
        if _profile_open(img):
            g.click_rel(0.244, 0.910); sleep(3)
            g.click_rel(0.150, 0.624); sleep(3)
            _barb_shot(g, "rc_chars.png")
            cards = _char_cards(g.screenshot())
            log("  restore_character: cards " + ", ".join(c["name"] for c in cards))
            want = [c for c in cards if name.lower() in c["name"].lower()]
            if want:
                if want[0]["current"]:
                    log("  restore_character: already on " + want[0]["name"])
                else:
                    g.click_rel(want[0]["x"], want[0]["y"]); sleep(3)
                    _barb_shot(g, "rc_confirm.png")
                    _click_yes(g, sleep)
                    log("  restore_character: switching to " + want[0]["name"])
                    sleep(40)
                    for _ in range(6):
                        recover_screen(g); sleep(5)
                _barb_shot(g, "rc_done.png")
                return True
            log("  ! restore_character: character not found on the page")
            _barb_shot(g, "rc_nochar.png")
            return True
        # tutorial step
        img = g.screenshot()
        _barb_shot(g, "rc_step%02d.png" % i)
        hsv0 = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mb = cv2.inRange(hsv0, (92, 150, 200), (110, 255, 255))      # blue CONFIRM / OK button
        mb[: int(0.1 * h)] = 0
        nb, _, sb, cb = cv2.connectedComponentsWithStats(mb)
        bb = max(range(1, nb), key=lambda k: sb[k][4], default=None)
        if bb is not None and sb[bb][4] > 1500 and sb[bb][2] > 0.06 * w:
            g.click_rel(cb[bb][0] / w, cb[bb][1] / h); sleep(3)
            continue
        v = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 2]
        dark = (v < 60).mean()
        bottom = img[int(0.84 * h):int(0.96 * h), int(0.25 * w):int(0.75 * w)].reshape(-1, 3).mean(0)
        if bottom[2] > 200 and bottom[1] > 190:                  # counselor parchment dialog
            g.click_rel(0.78, 0.94); sleep(2)
            continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m = cv2.inRange(hsv, (18, 120, 200), (35, 255, 255))
        m[: int(0.08 * h)] = 0
        n, _, st, cen = cv2.connectedComponentsWithStats(cv2.dilate(m, np.ones((5, 5), "uint8")))
        best = max(range(1, n), key=lambda k: st[k][4], default=None)
        if dark > 0.45:
            if best is not None and st[best][4] > 300:
                g.click_rel(cen[best][0] / w, cen[best][1] / h)
            else:
                g.click_rel(0.5, 0.5)
            sleep(2.5)
            continue
        if best is not None and st[best][4] > 600:
            g.click_rel(cen[best][0] / w, cen[best][1] / h); sleep(2.5)
            continue
        g.click_rel(0.5, 0.5); sleep(2)
    log("  ! restore_character: could not reach the profile")
    return True


SMART["restore_character"] = restore_character


# ---------------- v116: governor profile card (name, alliance, power, kill points, VIP, avatar) ----------------
def _ocr_bin(crop, name, thr=150, scale=3.0):
    """OCR light text on a dark/coloured background: threshold -> black text on white, padded."""
    import cv2
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, b = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)
    b = cv2.copyMakeBorder(b, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    vb = _ocr_boxes(cv2.cvtColor(b, cv2.COLOR_GRAY2BGR), name, scale=scale)
    return " ".join(x[4] for x in sorted(vb, key=lambda x: x[0]))


def _ocr_sheet(crops, name="sheet.png", thr=150):
    """Several small crops of light text -> one white sheet (dark text, 48 px rows) -> one OCR call.
    Returns the text for each crop (by row order). Windows OCR reads small lone crops badly."""
    import cv2, numpy as np
    rows = []
    for c in crops:
        gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
        _, b = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)
        f = 48.0 / max(1, b.shape[0])
        rows.append(cv2.resize(b, (max(1, int(b.shape[1] * f)), 48), interpolation=cv2.INTER_CUBIC))
    W = max(r.shape[1] for r in rows) + 80
    sheet = np.full((len(rows) * 90 + 40, W), 255, np.uint8)
    for i, r in enumerate(rows):
        sheet[30 + i * 90:30 + i * 90 + 48, 40:40 + r.shape[1]] = r
    boxes = _ocr_boxes(cv2.cvtColor(sheet, cv2.COLOR_GRAY2BGR), name, scale=1.0)
    out = [""] * len(rows)
    for b in sorted(boxes, key=lambda b: b[0]):
        k = int((((b[1] + b[3]) / 2) - 30) // 90)
        if 0 <= k < len(out):
            out[k] = (out[k] + " " + b[4]).strip()
    return out


# ---------------- v125: tiny digit reader (templates learned from numbers Windows OCR reads correctly) ----------------
DIGITS = {}


def _dig_mask(crop, dark):
    import cv2, numpy as np
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if dark:                                                  # brown text on parchment
        bg = np.percentile(g, 80)
        return (g < bg - 45).astype(np.uint8)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)               # white text on blue
    return ((g > 170) & (hsv[:, :, 1] < 90)).astype(np.uint8)


def _dig_seg(crop, dark=True):
    import cv2, numpy as np
    m = _dig_mask(crop, dark)
    rs = m.sum(1)
    if rs.max() == 0:
        return []
    rows = np.nonzero(rs > 0.4 * rs.max())[0]
    top, base = rows[0], rows[-1]
    Hd = base - top + 1
    body = m[top:base + 1]
    cs = body.sum(0)
    segs, x = [], 0
    while x < len(cs):
        if cs[x] > 0:
            x0 = x
            while x < len(cs) and cs[x] > 0:
                x += 1
            segs.append((x0, x))
        x += 1
    if not segs:
        return []
    tall = [(a, b) for a, b in segs if (body[:, a:b].sum(1) > 0).sum() >= 0.7 * Hd]
    widths = sorted(b - a for a, b in tall)
    med = widths[len(widths) // 2] if widths else Hd * 0.6
    out = []
    for x0, x1 in segs:
        k = int(round((x1 - x0) / med)) if (x1 - x0) > 1.7 * med else 1
        for i in range(k):
            a, b = x0 + (x1 - x0) * i // k, x0 + (x1 - x0) * (i + 1) // k
            part = body[:, a:b]
            r = np.nonzero(part.sum(1))[0]
            if not len(r):
                continue
            if r[-1] - r[0] + 1 >= 0.7 * Hd:
                gl = cv2.GaussianBlur(cv2.resize((part * 255).astype(np.float32), (8, 11), interpolation=cv2.INTER_AREA), (3, 3), 0)
                out.append((a, "d", gl, b - a))
            else:
                out.append((a, ",", None, b - a))
    blk = []
    for it in reversed(out):                                  # right-most block (the number)
        if blk and blk[-1][0] - (it[0] + it[3]) > 0.45 * Hd:
            break
        blk.append(it)
    return [(a, k, g) for a, k, g, _ in reversed(blk)]


def _dig_groups(crop, dark=True):
    """x-ranges of the digit groups between the commas of the right-most number in the crop."""
    import numpy as np
    m = _dig_mask(crop, dark)
    items = _dig_seg(crop, dark)
    if not items:
        return []
    groups, cur = [], []
    for idx, (x, k, _) in enumerate(items):
        if k == ",":
            if cur:
                groups.append(cur); cur = []
        else:
            cur.append(x)
    if cur:
        groups.append(cur)
    cs = m.sum(0)
    out = []
    for gx in groups:
        x0 = gx[0]
        x1 = gx[-1] + 1
        while x1 < len(cs) and cs[x1] > 0:
            x1 += 1
        out.append((max(0, x0 - 1), min(len(cs), x1 + 1)))
    return out


def _ocr_number_groups(crop, dark=True, name="numgroups.png"):
    """Windows OCR misses some long numbers (e.g. 1,141,536,008). Cut the number at its commas and OCR every
    3-digit group on its own row of a white sheet, then join. Returns the digits string or ''."""
    import cv2, numpy as np, re
    gr = _dig_groups(crop, dark)
    if not gr:
        return ""
    m = _dig_mask(crop, dark)
    rows = np.nonzero(m.sum(1))[0]
    y0, y1 = max(0, rows[0] - 2), min(m.shape[0], rows[-1] + 3)
    parts = []
    for a, b in gr:
        gpiece = cv2.cvtColor(crop[y0:y1, a:b], cv2.COLOR_BGR2GRAY).astype(np.float32)
        if not dark:
            gpiece = 255 - gpiece
        lo, hi = np.percentile(gpiece, 5), np.percentile(gpiece, 95)
        piece = np.clip((gpiece - lo) * 255.0 / max(1.0, hi - lo), 0, 255).astype(np.uint8)
        piece = cv2.copyMakeBorder(piece, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=255)
        f = 56.0 / piece.shape[0]
        parts.append(cv2.resize(piece, (max(1, int(piece.shape[1] * f)), 56), interpolation=cv2.INTER_CUBIC))
    W = max(p.shape[1] for p in parts) + 120
    sheet = np.full((len(parts) * 100 + 40, W), 255, np.uint8)
    for i, p in enumerate(parts):
        sheet[30 + i * 100:30 + i * 100 + 56, 60:60 + p.shape[1]] = p
    boxes = _ocr_boxes(cv2.cvtColor(sheet, cv2.COLOR_GRAY2BGR), name, scale=1.0)
    txt = [""] * len(parts)
    for b in boxes:
        k = int((((b[1] + b[3]) / 2) - 30) // 100)
        if 0 <= k < len(txt):
            txt[k] += re.sub(r"[^0-9OoIl|SsBZ]", "", b[4])
    fix = {"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "S": "5", "s": "5", "B": "8", "Z": "2"}
    txt = ["".join(fix.get(c, c) for c in t) for t in txt]
    if any(not t for t in txt):                               # second try: all groups on one line, wide gaps
        W2 = sum(p.shape[1] for p in parts) + 60 * len(parts) + 80
        line = np.full((116, W2), 255, np.uint8)
        x = 40
        for p in parts:
            line[30:86, x:x + p.shape[1]] = p
            x += p.shape[1] + 60
        bx = _ocr_boxes(cv2.cvtColor(line, cv2.COLOR_GRAY2BGR), name.replace(".png", "_line.png"), scale=1.0)
        toks = []
        for b in sorted(bx, key=lambda b: b[0]):
            toks += ["".join(fix.get(c, c) for c in re.sub(r"[^0-9OoIl|SsBZ]", "", t)) for t in b[4].split()]
        toks = [t for t in toks if t]
        if len(toks) == len(parts):
            txt = [t if t else toks[i] for i, t in enumerate(txt)]
    if not txt[0] and len(parts) > 1 and txt[1]:                 # lone leading digit: OCR it glued to group 2
        p0, p1 = parts[0], parts[1]
        glued = np.full((116, p0.shape[1] + p1.shape[1] + 100), 255, np.uint8)
        glued[30:86, 40:40 + p0.shape[1]] = p0
        glued[30:86, 46 + p0.shape[1]:46 + p0.shape[1] + p1.shape[1]] = p1
        bx = _ocr_boxes(cv2.cvtColor(glued, cv2.COLOR_GRAY2BGR), name.replace(".png", "_lead.png"), scale=1.0)
        r = "".join(fix.get(c, c) for c in re.sub(r"[^0-9OoIl|SsBZ]", "", " ".join(b[4] for b in bx)))
        if r.endswith(txt[1]) and 1 <= len(r) - len(txt[1]) <= 3:
            txt[0] = r[:-len(txt[1])]
        else:
            log(f"    lead digit OCR: {r!r}")
    if not txt or any(not t.isdigit() for t in txt) or any(len(t) != 3 for t in txt[1:]) or not (1 <= len(txt[0]) <= 3):
        log(f"    number groups OCR: {txt}")
        return ""
    return "".join(txt)


def _dig_load():
    import numpy as np
    from common import BASE
    if DIGITS:
        return
    try:
        z = np.load(os.path.join(BASE, "digits_tpl.npz"))
        for k in z.files:
            DIGITS[k] = list(z[k])
    except Exception:
        pass


def _dig_save():
    import numpy as np
    from common import BASE
    try:
        np.savez(os.path.join(BASE, "digits_tpl.npz"), **{k: np.array(v) for k, v in DIGITS.items()})
    except Exception:
        pass


def _dig_learn(crop, text, dark=True):
    """Learn digit shapes of the font from a crop whose text OCR read as a clean number."""
    _dig_load()
    ds = [c for c in text if c.isdigit()]
    gl = [g for _, k, g in _dig_seg(crop, dark) if k == "d"]
    if not ds or len(ds) != len(gl):
        return False
    for d, g in zip(ds, gl):
        key = ("D" if dark else "W") + d
        DIGITS.setdefault(key, []).append(g)
        DIGITS[key] = DIGITS[key][-6:]
    _dig_save()
    return True


def _dig_read(crop, dark=True, need=0.5):
    """Read a number with the learned digit shapes. Returns (digits, missing) - missing>0 = unsure."""
    import numpy as np
    _dig_load()
    pre = "D" if dark else "W"
    s, miss = "", 0
    for _, k, g in _dig_seg(crop, dark):
        if k == ",":
            continue
        best, bs = "?", -1.0
        a = g - g.mean()
        for key, gs in DIGITS.items():
            if not key.startswith(pre):
                continue
            for t in gs:
                b = t - t.mean()
                sc = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))
                if sc > bs:
                    best, bs = key[1], sc
        if bs < need:
            miss += 1
        s += best
    return s, miss


KP_ROWS = (0.486, 0.511, 0.537, 0.562, 0.589)
KP_MULT = (0.2, 2, 4, 10, 20)                                   # kill points per kill, T1..T5


def _kp_from_tiers(img):
    """Kill Statistics: OCR every tier's kills and kill points (+ the total) on one clean sheet. A tier's KP is
    trusted when it equals kills x points-per-kill; the total is the sum, cross-checked with the Total line."""
    import cv2, numpy as np, re, itertools
    h, w = img.shape[:2]
    crops = []
    for y in KP_ROWS:
        for x0, x1 in ((0.0595, 0.165), (0.19, 0.300)):
            crops.append(img[int((y - 0.011) * h):int((y + 0.011) * h), int(x0 * w):int(x1 * w)])
    crops.append(img[int(0.603 * h):int(0.625 * h), int(0.19 * w):int(0.300 * w)])
    ps = []
    for c in crops:
        gg = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float32)
        lo, hi = np.percentile(gg, 3), np.percentile(gg, 97)
        pp = np.clip((gg - lo) * 255 / max(1.0, hi - lo), 0, 255).astype(np.uint8)
        ps.append(cv2.resize(pp, None, fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4))
    RH = max(p.shape[0] for p in ps) + 40
    W = max(p.shape[1] for p in ps) + 80
    sheet = np.full((len(ps) * RH + 40, W), 255, np.uint8)
    for i, p in enumerate(ps):
        sheet[20 + i * RH:20 + i * RH + p.shape[0], 40:40 + p.shape[1]] = p
    boxes = _ocr_boxes(cv2.cvtColor(sheet, cv2.COLOR_BGR2GRAY if False else cv2.COLOR_GRAY2BGR), "kp_sheet.png", scale=1.0)
    txt = [""] * len(ps)
    for b in boxes:
        k = int((((b[1] + b[3]) / 2) - 20) // RH)
        if 0 <= k < len(txt):
            txt[k] += " " + b[4]
    fix = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "S": "5", "B": "8", "Z": "2"})
    def num(t):
        t = re.sub(r"(?<=\d)[,\. ](?=\d)", "", t.translate(fix))
        m = re.findall(r"\d{4,}", t)
        return int(max(m, key=len)) if m else None
    def is_clean(t):
        t = t.strip().translate(fix)
        if t.lower().startswith("total"):
            t = t[5:].strip(" :")
        return bool(re.fullmatch(r"\d{1,3}(?:[,\.]\d{3})+|\d{4,}", t))
    vals = [num(t) for t in txt]
    clean = [is_clean(t) for t in txt]
    log("    kill statistics sheet: " + " | ".join(t.strip() for t in txt)[:300])
    total = vals[10]
    opts = []
    for i in range(5):
        k, kp = vals[2 * i], vals[2 * i + 1]
        o = []
        calc = int(k * KP_MULT[i]) if k is not None else None
        if kp is not None and calc is not None and abs(kp - calc) <= 1:
            o = [kp]                                             # validated
        elif kp is not None and clean[2 * i + 1] and not (calc is not None and clean[2 * i]):
            o = [kp]
        elif calc is not None and clean[2 * i] and not (kp is not None and clean[2 * i + 1]):
            o = [calc]
        else:
            o = [v for v in (kp, calc) if v is not None]
        opts.append(o or [None])
    if all(len(o) == 1 and o[0] is not None for o in opts):
        sm = sum(o[0] for o in opts)
        if total is None or total == sm or not clean[10]:
            return sm
    if any(o == [None] for o in opts):
        return total if total and total > 0 else None
    sums = {sum(c) for c in itertools.product(*opts)}
    if total in sums:
        return total
    return None


def _kp_popup(g, sleep):
    """Kill Points (i) next to the label -> 'Kill Statistics' (dark text on parchment) -> 'Total: N'."""
    import re
    g.click_rel(0.078, 0.413); sleep(2.5)
    try:
        img = g.screenshot(); h, w = img.shape[:2]
        boxes = _ocr_boxes(img[int(0.42 * h):int(0.645 * h), int(0.03 * w):int(0.315 * w)], "kp_stats.png", scale=2.0)
        txt = [b[4] for b in sorted(boxes, key=lambda b: (b[1], b[0]))]
        try:
            v = _kp_from_tiers(img)
        except Exception as e:
            v = None
            log(f"    ! kill statistics sheet failed: {e!r}")
        if v:
            log(f"    KP from kill statistics: {v:,}")
            return v
        # learn the font from tier values OCR read cleanly (e.g. 225,951,220), then read the Total by shape
        ox, oy = int(0.03 * w), int(0.42 * h)
        for b in boxes:
            t = b[4].strip().replace(".", ",")
            if re.fullmatch(r"\d{1,3}(,\d{3})+", t):
                _dig_learn(img[oy + int(b[1]) - 2:oy + int(b[3]) + 3, ox + int(b[0]) - 3:ox + int(b[2]) + 3], t, dark=True)
        tot = img[int(0.597 * h):int(0.630 * h), int(0.15 * w):int(0.305 * w)]
        grp = _ocr_number_groups(tot, dark=True, name="kp_groups.png")
        if grp:
            log(f"    KP total by comma groups: {grp}")
            return int(grp)
        digs, miss = _dig_read(tot, dark=True)
        log(f"    KP total by digit shapes: {digs} (unsure {miss}); known digits: {''.join(sorted(k[1] for k in DIGITS if k[0] == 'D'))}")
        if digs and miss == 0 and digs.isdigit() and len(digs) >= 4:
            return int(digs)
        joined = " ".join(txt)
        k = joined.lower().rfind("total")
        if k >= 0:
            m = re.search(r"\b(\d{1,3}(?:[,\.]\d{3}){2,})\b", joined[k:])
            if m:
                return int(re.sub(r"[^\d]", "", m.group(1)))
        for nm, crop, sc in (("kp_total3", img[int(0.597 * h):int(0.630 * h), int(0.15 * w):int(0.305 * w)], 3.0),
                             ("kp_total2", img[int(0.590 * h):int(0.635 * h), int(0.03 * w):int(0.31 * w)], 2.0)):
            t2 = " ".join(b[4] for b in sorted(_ocr_boxes(crop, nm + ".png", scale=sc), key=lambda b: b[0]))
            m = re.search(r"\b(\d{1,3}(?:[,\.]\d{3}){2,})\b", t2)
            if m:
                return int(re.sub(r"[^\d]", "", m.group(1)))
            txt.append(nm + ":" + t2)
        log("    kill statistics OCR: " + " | ".join(txt)[:200])
        return None
    finally:
        g.click_rel(0.15, 0.80); sleep(1.5)                  # close the popup (blank part of the profile panel)


def _read_ap_ratio(img):
    """UX-01: find "Action Points ... 1,234/1,500" on the open governor profile. Returns (cur, max) or None.
    Reads the left half of the profile window; only a sane ratio (cur <= max, max 1000..3000) is accepted."""
    import re
    h, w = img.shape[:2]
    boxes = _ocr_boxes(img[int(0.10 * h):int(0.75 * h), int(0.02 * w):int(0.55 * w)], "profile_ap.png")
    rows = []
    for b in sorted(boxes, key=lambda b: b[1]):
        if rows and abs(rows[-1][0] - b[1]) < 8:
            rows[-1][1].append(b)
        else:
            rows.append([b[1], [b]])
    lines = [" ".join(x[4] for x in sorted(r[1], key=lambda x: x[0])) for r in rows]
    for i, ln in enumerate(lines):
        if "action" not in ln.lower().replace(" ", ""):
            continue
        for t in lines[i:i + 3]:
            m = re.search(r"(\d[\d,\.]*)\s*/\s*(\d[\d,\.]*)", t.replace("O", "0").replace("o", "0"))
            if m:
                cur, mx = int(re.sub(r"\D", "", m.group(1))), int(re.sub(r"\D", "", m.group(2)))
                if 1000 <= mx <= 3000 and 0 <= cur <= mx:
                    return cur, mx
    return None


def read_profile(g, sleep):
    """Open the governor profile (avatar top-left), OCR name / alliance / power / kill points, crop the portrait,
    read VIP from the top bar. Sends everything to the dashboard (control.CITY['profile'])."""
    import cv2, base64, re, control, time as _t
    recover_screen(g); sleep(1)
    if _queue_cards(g):
        _barb_close(g, sleep)
    img0 = g.screenshot(); h, w = img0.shape[:2]
    vip = ""
    try:
        vt = ""
        for nm, crop in (("wide3", img0[int(0.025 * h):int(0.07 * h), int(0.04 * w):int(0.14 * w)]),
                         ("tight", img0[int(0.033 * h):int(0.062 * h), int(0.07 * w):int(0.115 * w)])):
            vt = " ".join(b[4] for b in _ocr_boxes(crop, "vip_%s.png" % nm, scale=3.0))
            if not re.search(r"\d|S", vt):
                vt = _ocr_bin(crop, "vipb_%s.png" % nm, thr=120, scale=3.0)
            log(f"    VIP OCR {nm}: {vt!r}")
            if re.search(r"VIP|V1P|\d", vt.upper()):
                break
        vt = vt.upper()
        if not re.search(r"\d", vt):
            vb = _ocr_boxes(img0[int(0.033 * h):int(0.062 * h), int(0.07 * w):int(0.115 * w)], "vip2.png", scale=3.0)
            vt = " ".join(b[4] for b in vb).upper()
        vt = re.sub(r"VIP", " VIP ", vt)
        vt = "".join({"O": "0", "S": "5", "I": "1", "L": "1", "|": "1", "B": "8"}.get(c, c) if i > vt.find("VIP") + 2 else c for i, c in enumerate(vt))
        m = re.search(r"VIP\s*(\d{1,2})", vt) or re.search(r"(\d{1,2})\s*$", vt)
        vip = m.group(1) if m else ""
    except Exception:
        pass
    g.click_rel(0.030, 0.040); sleep(3)
    img = g.screenshot()
    prof = {"read_at": _t.strftime("%Y-%m-%d %H:%M")}
    try:
        if not _profile_open(img):
            log("  ! read_profile: the profile did not open")
            return True
        boxes = _ocr_boxes(img[int(0.26 * h):int(0.49 * h), int(0.02 * w):int(0.28 * w)], "profile.png")
        rows = []
        for b in sorted(boxes, key=lambda b: b[1]):
            if rows and abs(rows[-1][0] - b[1]) < 6:
                rows[-1][1].append(b)
            else:
                rows.append([b[1], [b]])
        lines = [" ".join(x[4] for x in sorted(r[1], key=lambda x: x[0])).strip() for r in rows]
        log("    profile OCR: " + " | ".join(lines)[:300])
        def num(t):
            m = re.search(r"([\d][\d,\.]{3,})", t)
            return int(re.sub(r"[^\d]", "", m.group(1))) if m else None
        rowy = [r[0] for r in rows]
        def val_at(k):
            """The value of label row k: several OCR variants of the row strip; first with 3+ digits wins."""
            y = int(rowy[k]) + int(0.26 * h)
            strip = img[max(0, y - 5):y + int(0.032 * h), int(0.02 * w):int(0.28 * w)]
            val = img[max(0, y - 5):y + int(0.032 * h), int(0.12 * w):int(0.28 * w)]
            tries = []
            for nm, fn in (("strip3", lambda: " ".join(b[4] for b in _ocr_boxes(strip, "pv1.png", scale=3.0))),
                           ("stripbin", lambda: _ocr_bin(strip, "pv2.png", thr=170, scale=2.0)),
                           ("val4", lambda: " ".join(b[4] for b in _ocr_boxes(val, "pv3.png", scale=4.0))),
                           ("sheet", lambda: _ocr_sheet([strip, val], "pv4.png", thr=170)[1])):
                try:
                    t = fn()
                except Exception as e:
                    t = f"err {e!r}"
                tries.append(f"{nm}={t!r}")
                if re.search(r"\d{3}", t.split("Points")[-1]):
                    log("    value OCR: " + "; ".join(tries)[:200])
                    return t.split("Points")[-1]
            log("    value OCR failed: " + "; ".join(tries)[:200])
            return ""
        def upfix(t):
            return " ".join(wd.replace("l", "L") if sum(c.isupper() for c in wd) >= len(wd) - 2 else wd for wd in t.split())
        for i, ln in enumerate(lines):
            low = ln.lower().replace(" ", "")
            if i == 1 or (i > 0 and lines[i - 1].lower()[:3] in ("gov", "gmo", "gme", "gav")):
                if "name" not in prof:
                    nm = re.sub(r"^[^\w\[]+", "", ln).split("(")[0].strip()
                    if nm:
                        prof["name"] = nm
            if low.startswith("civ"):
                prof["civ"] = ln.split(" ", 1)[1].strip() if " " in ln else ""
            elif low.startswith("all"):
                al = ln.split(" ", 1)[1].strip() if " " in ln else ""
                m = re.match(r"\[\s*([0-9A-Za-z]{2,4}?)\s*[\]Il1|]\s*(.+)", al)
                if m:
                    prof["tag"], prof["alliance"] = m.group(1), upfix(m.group(2).strip())
                else:
                    prof["tag"], prof["alliance"] = "", upfix(al)
            elif low.startswith("po") and "power" not in prof:
                prof["power"] = num(ln) or num(val_at(i))
            elif low.startswith("kil") or low.startswith("ki11"):
                prof["kp"] = num(ln) or _kp_popup(g, sleep)
            if "gid" not in prof:
                m = re.search(r"(\d{7,})", ln)
                if m and i == 0:
                    prof["gid"] = m.group(1)
        try:                                             # UX-01: action points "cur / max" for the dashboard AP card
            apv = _read_ap_ratio(img)
            if apv:
                control.CITY["ap"] = {"cur": apv[0], "max": apv[1], "read_at": prof["read_at"]}
                log(f"    action points: {apv[0]}/{apv[1]}")
        except Exception as e:
            log(f"    action points OCR failed: {e!r}")
        ap = img[int(0.02 * h):int(0.15 * h), int(0.095 * w):int(0.19 * w)]
        ok, buf = cv2.imencode(".jpg", cv2.resize(ap, (96, 96)), [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            prof["avatar"] = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
        if vip:
            prof["vip"] = vip
        old = control.CITY.get("profile") or {}
        for k in ("ch", "conduct", "vip", "kp", "power"):
            if old.get(k) and not prof.get(k):
                prof[k] = old[k]
        control.CITY["profile"] = prof
        _persist_save()
        log(f"  read_profile: {prof.get('name', '?')} [{prof.get('tag', '')}] power {prof.get('power')} KP {prof.get('kp')} VIP {vip}")
    finally:
        g.click_rel(0.271, 0.019); sleep(2)                  # profile X
        recover_screen(g)
    return True


SMART["read_profile"] = read_profile


# ---------------- v130: armies out (marches) for the dashboard ----------------
MARCH_Y0, MARCH_DY = 0.158, 0.0537          # right army column on the map (zoomed-in view)


def _march_status(img, k):
    import cv2
    h, w = img.shape[:2]
    cy = MARCH_Y0 + MARCH_DY * k
    box = cv2.cvtColor(img[int((cy + 0.010) * h):int((cy + 0.036) * h), int(0.974 * w):int(0.993 * w)], cv2.COLOR_BGR2HSV)
    cnt = lambda lo, hi: cv2.countNonZero(cv2.inRange(box, lo, hi))
    c = {"gather": cnt((40, 110, 110), (85, 255, 255)), "standby": cnt((92, 120, 120), (128, 255, 255)),
         "return": cnt((12, 120, 150), (32, 255, 255)),
         "attack": cnt((0, 140, 120), (8, 255, 255)) + cnt((170, 140, 120), (180, 255, 255))}
    k2 = max(c, key=c.get)
    return k2 if c[k2] > 12 else "march"


def _march_count(img):
    import re
    h, w = img.shape[:2]
    crop = img[int(0.100 * h):int(0.130 * h), int(0.930 * w):int(0.995 * w)]
    t = _ocr_words(crop, "march_n.png", light=True, thr=170)
    if not re.search(r"\d\s*/\s*\d", t):
        t = _ocr_sheet([crop], "march_n2.png", thr=170)[0]
    log(f"    marches counter OCR: {t!r}")
    m = re.search(r"(\d)\s*/\s*(\d)", t)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _ocr_words(crop, name, light=True, thr=None):
    """Windows OCR drops some tokens like '423,088/945,000' or 'Y:608' inside a line. Split the line into words
    (by blank columns), put every word on its own row of a big white sheet and OCR that. Returns words joined."""
    import cv2, numpy as np
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if light:
        m = g > (thr or 170)
    else:
        m = g < (np.percentile(g, 80) - (thr or 45))
    cols = m.sum(0)
    rows = np.nonzero(m.sum(1) > 0)[0]
    if not len(rows):
        return ""
    H = rows[-1] - rows[0] + 1
    segs, x, gap = [], 0, max(2, int(0.35 * H))
    while x < len(cols):
        if cols[x] > 0:
            x0, last = x, x
            while x < len(cols) and (cols[x] > 0 or x - last <= gap):
                if cols[x] > 0:
                    last = x
                x += 1
            segs.append((max(0, x0 - 2), min(len(cols), last + 3)))
        x += 1
    y0, y1 = max(0, rows[0] - 3), min(g.shape[0], rows[-1] + 4)
    parts = []
    for a, b in segs:
        if b - a < 3:
            continue
        pg = g[y0:y1, a:b].astype(np.float32)
        if light:
            pg = 255 - pg
        lo, hi = np.percentile(pg, 3), np.percentile(pg, 97)
        pp = np.clip((pg - lo) * 255 / max(1.0, hi - lo), 0, 255).astype(np.uint8)
        f = 60.0 / pp.shape[0]
        parts.append(cv2.resize(pp, (max(1, int(pp.shape[1] * f)), 60), interpolation=cv2.INTER_CUBIC))
    if not parts:
        return ""
    W = max(p.shape[1] for p in parts) + 120
    sheet = np.full((len(parts) * 110 + 40, W), 255, np.uint8)
    for i, p in enumerate(parts):
        sheet[30 + i * 110:90 + i * 110, 60:60 + p.shape[1]] = p
    boxes = _ocr_boxes(cv2.cvtColor(sheet, cv2.COLOR_GRAY2BGR), name, scale=1.0)
    txt = [""] * len(parts)
    for b in sorted(boxes, key=lambda b: b[0]):
        k = int((((b[1] + b[3]) / 2) - 30) // 110)
        if 0 <= k < len(txt):
            txt[k] += b[4]
    return " ".join(t for t in txt if t)


def _xy_parts(text):
    """'x.\x07644 Y\x07.S20' -> (644, 520): tolerant X / Y reader (S->5, O->0, l/I->1)."""
    import re
    t = text.replace("\x07", " ")
    fix = str.maketrans({"S": "6", "s": "6", "O": "0", "o": "0", "l": "1", "I": "1", "|": "1", "B": "8"})
    out = [None, None]
    for i, key in enumerate("XY"):
        m = re.search(key + r"[\W_]{0,3}([0-9SsOolIB|]{3,4})", t, re.I)
        if m:
            v = m.group(1).translate(fix)
            if v.isdigit() and 0 < int(v) <= 1200:
                out[i] = int(v)
    return out


def read_marches(g, sleep):
    """Map view: every army card in the right column -> status icon, commander portrait, then click it:
    a resource tile popup gives the tile, coordinates and gathering quantity; an army on the move/standing gives
    its troop count (label above it) and coordinates (top bar = camera centre). Result -> control.CITY['marches']."""
    import cv2, base64, re, control, numpy as np, time as _t
    recover_screen(g); sleep(1)
    if _queue_cards(g):
        _barb_close(g, sleep)
    if not goto_map(g, sleep, "read_marches"):
        return True
    img = g.screenshot(); h, w = img.shape[:2]
    n, mx = _march_count(img)
    if n is None:
        # count the cards by their status icons
        n = 0
        while n < 5 and _march_status(img, n) != "march":
            n += 1
    out = []
    for k in range(int(n or 0)):
        img = g.screenshot()
        cy = MARCH_Y0 + MARCH_DY * k
        st = _march_status(img, k)
        por = img[int((cy - 0.026) * h):int((cy + 0.026) * h), int(0.945 * w):int(0.99 * w)]
        av = ""
        if por.size:
            ok, buf = cv2.imencode(".jpg", cv2.resize(por, (56, 56)), [cv2.IMWRITE_JPEG_QUALITY, 75])
            av = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode() if ok else ""
        g.click_rel(0.966, cy); sleep(2.5)
        img2 = g.screenshot()
        _barb_shot(g, "march_%d.png" % k)
        a = {"slot": k + 1, "status": st, "avatar": av}
        topc = img2[int(0.004 * h):int(0.032 * h), int(0.14 * w):int(0.25 * w)]
        top = " ".join(b[4] for b in _ocr_boxes(topc, "march_xy.png", scale=4.0))
        if not re.search(r"Y\s*[:;.]?\s*\d", top):
            top += " " + _ocr_sheet([topc], "march_xy2.png", thr=150)[0]
        m = re.search(r"X\s*[:;.]?\s*(\d{1,4})\D{0,4}Y\s*[:;.]?\s*(\d{1,4})", top.replace(" ", ""))
        if m:
            a["x"], a["y"] = int(m.group(1)), int(m.group(2))
        pop = img2[int(0.36 * h):int(0.62 * h), int(0.53 * w):int(0.81 * w)]
        pb = _ocr_boxes(pop, "march_pop.png", scale=2.0)
        ptxt = [b[4] for b in sorted(pb, key=lambda b: (b[1], b[0]))]
        joined = " | ".join(ptxt)
        log(f"    march {k + 1}: top={top!r} popup={joined[:160]!r}")
        for src in (top, joined):
            px, py = _xy_parts(src)
            if px and "x" not in a:
                a["x"] = px
            if py and "y" not in a:
                a["y"] = py
        if re.search(r"deposit|farm|lumber|quarry|mine|cropland|field|gem", joined, re.I):
            qc = img2[int(0.522 * h):int(0.556 * h), int(0.555 * w):int(0.79 * w)]
            q = _ocr_words(qc, "march_q.png", light=True, thr=200)
            if not re.search(r"\d+\s*/\s*\d", q):
                q += " " + _ocr_sheet([qc], "march_q2.png", thr=200)[0]
            mq = re.search(r"([\d][\d,\.]{2,})\s*/\s*([\d][\d,\.]{2,})", q.replace(" ", ""))
            if "x" not in a or "y" not in a:
                pc = img2[int(0.370 * h):int(0.392 * h), int(0.62 * w):int(0.70 * w)]
                pt = _ocr_words(pc, "march_pxy.png", light=False)
                px, py = _xy_parts(pt)
                if px and "x" not in a:
                    a["x"] = px
                if py and "y" not in a:
                    a["y"] = py
                if "x" not in a or "y" not in a:
                    log(f"    march {k + 1}: popup xy OCR {pt!r}")
            if mq:
                a["got"], a["cap"] = int(re.sub(r"\D", "", mq.group(1))), int(re.sub(r"\D", "", mq.group(2)))
            else:
                log(f"    march {k + 1}: quantity OCR {q!r}")
            try:
                bar = cv2.cvtColor(qc, cv2.COLOR_BGR2HSV)
                gm = cv2.inRange(bar, (40, 120, 120), (85, 255, 255))
                colsg = np.nonzero(gm.sum(0) > gm.shape[0] * 0.3 * 255)[0]
                if len(colsg):
                    a["pct"] = max(0, min(100, int(round((colsg[-1] - int(0.03 * w)) / max(1, qc.shape[1] - int(0.05 * w)) * 100))))
            except Exception:
                pass
            for t in ptxt:
                if re.search(r"level\s*\d", t, re.I):
                    a["target"] = t.strip()
                mq = re.search(r"([\d,\.]{3,})\s*/\s*([\d,\.]{3,})", t)
                if mq and "quantity" in joined.lower():
                    a["got"] = int(re.sub(r"\D", "", mq.group(1)))
                    a["cap"] = int(re.sub(r"\D", "", mq.group(2)))
                mxy = re.search(r"X\W{0,3}(\d{2,4})\D{1,4}Y\W{0,3}(\d{2,4})", t)
                if mxy:
                    a["x"], a["y"] = int(mxy.group(1)), int(mxy.group(2))
            a["status"] = "gather"
            a["mission"] = "gather"                                # UX-03
            kind = next((k for k, rx in (("food", r"farm|cropland|field"), ("wood", r"lumber|wood"), ("stone", r"quarry|stone"),
                                        ("gold", r"gold|mine"), ("gems", r"gem")) if re.search(rx, joined, re.I)), "")
            if kind:
                a["kind"] = kind
        else:
            labc = img2[int(0.428 * h):int(0.454 * h), int(0.47 * w):int(0.56 * w)]
            lab = _ocr_words(labc, "march_lab.png", light=True, thr=170)
            if not re.search(r"\d{3}", lab):
                lab += " " + _ocr_sheet([labc], "march_lab2.png", thr=190)[0]
            mt = re.findall(r"\d{1,3}(?:[,\.]\d{3})+|\d{4,}", lab)
            log(f"    march {k + 1}: label {lab!r}")
            if mt:
                a["troops"] = int(re.sub(r"\D", "", mt[-1]))
            # UX-03: mission type and troop health when the popup shows them
            if re.search(r"rally", joined, re.I):
                a["mission"] = "rally"
            elif re.search(r"barbarian|fort", joined + " " + a.get("target", ""), re.I) or st == "attack":
                a["mission"] = "barbarians"
            mh = re.search(r"(\d{1,3})\s*%", joined)
            if mh and 0 <= int(mh.group(1)) <= 100:
                a["health"] = int(mh.group(1))
        # UX-03: commander names - read from the popup when shown, else the dashboard preset for that task
        names = []
        low = joined.lower().replace(" ", "")
        for cn in COMMANDER_NAMES:
            if len(cn) > 3 and cn.lower().replace(" ", "") in low and cn not in names:
                names.append(cn)
        if names:
            a["commanders"] = names[:2]
        else:
            task = ("gathering_" + a["kind"]) if a.get("kind") in ("food", "wood", "stone", "gold") else \
                   ("rallies" if a.get("mission") == "rally" else "barbarians" if a.get("mission") == "barbarians" else "")
            c1, c2 = _preset(task) if task else ("", "")
            if c1:
                a["commanders"] = [c for c in (c1, c2) if c]
                a["commanders_from"] = "preset"
        out.append(a)
        recover_screen(g); sleep(1)
    control.CITY["marches"] = out
    control.CITY["marches_at"] = _t.strftime("%Y-%m-%d %H:%M")
    if mx:
        control.CITY["marches_max"] = mx
    _persist_save()
    log(f"  read_marches: {len(out)} army(ies): " + "; ".join(
        f"{a['slot']}:{a['status']} {a.get('target', '')} {a.get('pct', '')}% {a.get('troops', '')} ({a.get('x', '?')},{a.get('y', '?')})" for a in out))
    return True


SMART["read_marches"] = read_marches

# ---------------- v129: keep profile / characters / marches across restarts ----------------
PERSIST_KEYS = ("profile", "characters", "characters_at", "marches", "marches_at", "commanders", "commanders_at", "ap", "shield")


def _persist_save():
    import json, control
    from common import BASE
    try:
        d = {k: control.CITY[k] for k in PERSIST_KEYS if k in control.CITY}
        json.dump(d, open(os.path.join(BASE, "persist_city.json"), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        log(f"  ! persist save: {e!r}")


def _persist_load():
    import json, control
    from common import BASE
    try:
        d = json.load(open(os.path.join(BASE, "persist_city.json"), encoding="utf-8"))
        for k, v in d.items():
            control.CITY.setdefault(k, v)
    except Exception:
        pass


try:
    _persist_load()
except Exception:
    pass


try:
    _stats_save(_stats_load())          # v105: dashboard gets history + notifications right after start
except Exception:
    pass


def march_probe(g, sleep):
    """Test: map view -> screenshot the right army column, click the first army card, screenshot."""
    recover_screen(g); sleep(1)
    if not _on_map(g):
        press_key("space"); sleep(6)
    _barb_shot(g, "mp0.png")
    g.click_rel(0.966, 0.3155); sleep(2.5)
    _barb_shot(g, "mp1.png")
    g.click_rel(0.966, 0.3155 + 0.0852); sleep(2.5)
    _barb_shot(g, "mp2.png")
    recover_screen(g)
    return True


SMART["march_probe"] = march_probe
