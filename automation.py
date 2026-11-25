"""Roadmap v18 - TASK-15 (If-This-Then-That rules), GUIDE-18 (Smart Scheduler run ranges), TASK-16 (daily stats file).

Everything here only changes WHICH activities run and WHEN. It never buys, never uses gems, never presses INSTANT.
"""
import datetime
import hashlib
import json
import os
import random
import time

from common import BASE, log

# ---------------------------------------------------------------- TASK-15: rules engine
METRICS = ("ap", "ap_percent", "hospital_fill_percent", "free_marches", "gems_today",
           "food", "wood", "stone", "gold", "hour_utc")
OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
       ">=": lambda a, b: a >= b, "=": lambda a, b: a == b, "!=": lambda a, b: a != b}
ACTIONS = ("disable_task", "enable_task", "skip_round")
RULE_LAST = {}          # rule id -> last state (True = matched), so the log shows changes only


def _num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None


def metrics():
    """Current values the bot already knows (None = not read yet - a rule on it does nothing)."""
    import control
    c, r = control.CITY, control.RESOURCES
    out = {k: None for k in METRICS}
    ap = c.get("ap") or {}
    if isinstance(ap, dict) and _num(ap.get("cur")) is not None:
        out["ap"] = _num(ap.get("cur"))
        mx = _num(ap.get("max"))
        if mx:
            out["ap_percent"] = round(100.0 * out["ap"] / mx, 1)
    h = str(c.get("hospital") or "")
    if "/" in h:
        a, b = (_num(x) for x in h.split("/", 1))
        if a is not None and b:
            out["hospital_fill_percent"] = round(100.0 * a / b, 1)
    mx = _num(c.get("marches_max"))
    if mx and isinstance(c.get("marches"), list):
        out["free_marches"] = max(0, mx - len(c["marches"]))
    if _num(c.get("gems_today")) is not None:
        out["gems_today"] = _num(c.get("gems_today"))
    for k in ("food", "wood", "stone", "gold"):
        if _num(r.get(k)) is not None:
            out[k] = _num(r.get(k))
    out["hour_utc"] = datetime.datetime.utcnow().hour
    return out


def clean_rules(lst):
    rules = []
    for x in (lst or [])[:20]:
        if not isinstance(x, dict):
            continue
        m, op, act = x.get("condition_metric"), x.get("operator"), x.get("action_type")
        thr = _num(x.get("threshold"))
        if m not in METRICS or op not in OPS or act not in ACTIONS or thr is None:
            continue
        if act != "skip_round" and not str(x.get("target_task") or "").strip():
            continue
        rules.append({"id": str(x.get("id") or f"r{len(rules) + 1}")[:24], "enabled": bool(x.get("enabled", True)),
                      "condition_metric": m, "operator": op, "threshold": thr, "action_type": act,
                      "target_task": str(x.get("target_task") or "")[:40]})
    return rules


def apply_rules(settings):
    """Return (settings for this round, skip_round). The user's saved settings are never changed: a rule only
    switches a task on/off for the current round, and the next round checks again."""
    import control
    rules = [r for r in clean_rules(settings.get("automation_rules")) if r["enabled"]]
    if not rules:
        control.CITY.pop("rules", None)
        return settings, False
    vals = metrics()
    tasks = [dict(t) for t in (settings.get("tasks") or [])]
    skip, fired = False, []
    for r in rules:
        v = vals.get(r["condition_metric"])
        hit = v is not None and OPS[r["operator"]](v, r["threshold"])
        if RULE_LAST.get(r["id"]) != hit:
            RULE_LAST[r["id"]] = hit
            what = f"{r['condition_metric']} {r['operator']} {r['threshold']:g} -> {r['action_type']} {r['target_task']}".strip()
            log(f"Rule {r['id']}: {'TRIGGERED' if hit else 'no longer true'} ({what}; value now {v})")
        if not hit:
            continue
        fired.append(r["id"])
        if r["action_type"] == "skip_round":
            skip = True
        for t in tasks:
            if t.get("routine") == r["target_task"]:
                t["enabled"] = r["action_type"] == "enable_task"
    control.CITY["rules"] = {"fired": fired, "values": {k: v for k, v in vals.items() if v is not None},
                             "at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"}
    if not fired:
        return settings, False
    eff = dict(settings)
    eff["tasks"] = tasks
    return eff, skip


# ---------------------------------------------------------------- GUIDE-18: Smart Scheduler run ranges (UTC)
RANGE_STARTED = [None]   # key of the range this bot started in (so a <15 min rest only blocks a NEW start)


def _hm(t):
    try:
        h, m = str(t).strip().split(":")[:2]
        return max(0, min(int(h), 24)) * 60 + max(0, min(int(m), 59))
    except Exception:
        return None


def _offset(day, i, which, mx):
    """A random shift (minutes) that is fixed for one day and one range edge, so restarts don't change it."""
    if mx <= 0:
        return 0
    h = hashlib.sha256(f"{day}|{i}|{which}".encode()).digest()
    return int(h[0] / 255.0 * 2 * mx) - mx


def sched_cfg(settings):
    c = (settings or {}).get("sched_ranges") or {}
    rows = []
    for x in (c.get("ranges") or [])[:8]:
        if isinstance(x, dict) and x.get("on", True) is not False:
            a, b = _hm(x.get("from")), _hm(x.get("to"))
            if a is not None and b is not None and a != b:
                rows.append({"from": a, "to": b, "profile": str(x.get("profile") or "")[:40]})
    try:
        mx = max(0, min(int(c.get("offset_max") or 0), 30))
    except Exception:
        mx = 0
    return {"enabled": bool(c.get("enabled")) and bool(rows), "ranges": rows, "offset_max": mx,
            "override": c.get("override") if isinstance(c.get("override"), dict) else None}


def _windows(cfg, now):
    """Real start/end datetimes of every range for yesterday, today and tomorrow (offsets applied)."""
    out = []
    for dd in (-1, 0, 1):
        d0 = (now + datetime.timedelta(days=dd)).replace(hour=0, minute=0, second=0, microsecond=0)
        day = d0.strftime("%Y-%m-%d")
        for i, r in enumerate(cfg["ranges"]):
            a, b = r["from"], r["to"] if r["to"] > r["from"] else r["to"] + 1440
            s = d0 + datetime.timedelta(minutes=a + _offset(day, i, "s", cfg["offset_max"]))
            e = d0 + datetime.timedelta(minutes=b + _offset(day, i, "e", cfg["offset_max"]))
            if e - s >= datetime.timedelta(minutes=30):
                out.append((s, e, r, f"{day}#{i}"))
    return sorted(out, key=lambda w: w[0])


def sched_gate(settings, now=None):
    """(run?, seconds to wait, profile name, text). Off -> always (True, 0, '', '')."""
    import control
    cfg = sched_cfg(settings)
    if not cfg["enabled"]:
        control.CITY.pop("sched_ranges", None)
        return True, 0, "", ""
    now = now or datetime.datetime.utcnow()
    wins = _windows(cfg, now)
    cur = next((w for w in wins if w[0] <= now < w[1]), None)
    edges = [t for w in wins for t in (w[0], w[1]) if t <= now]
    last_edge = max(edges) if edges else now - datetime.timedelta(days=2)
    nxt = min([w[0] for w in wins if w[0] > now] + [now + datetime.timedelta(hours=24)])
    run, why = cur is not None, ""
    if cur is not None:
        left = (cur[1] - now).total_seconds()
        if RANGE_STARTED[0] != cur[3] and left < 15 * 60:
            run, why = False, "less than 15 minutes left in this range - waiting for the next one"
    ov = cfg["override"]
    if ov and ov.get("mode") in ("start", "stop"):          # manual START/STOP holds until the next boundary
        try:
            at = datetime.datetime.fromisoformat(str(ov.get("at")).replace("Z", "")[:19])
            if at >= last_edge:
                run, why = ov["mode"] == "start", "manual " + ov["mode"].upper() + " until the next scheduled boundary"
        except Exception:
            pass
    if run:
        RANGE_STARTED[0] = cur[3] if cur is not None else "manual"
    else:
        RANGE_STARTED[0] = None
    control.CITY["sched_ranges"] = {"state": "run" if run else "off", "why": why,
                                    "range": [cur[0].strftime("%H:%M"), cur[1].strftime("%H:%M")] if cur else None,
                                    "next": nxt.strftime("%Y-%m-%d %H:%M"), "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    if run:
        return True, 0, (cur[2]["profile"] if cur else ""), why
    wait = max(60, min(300, (nxt - now).total_seconds()))
    return False, wait, "", why or f"outside the run ranges - next start {nxt:%H:%M} UTC"


def apply_range_profile(settings, name):
    p = (settings.get("presets") or {}).get(name) if name else None
    if not p:
        return settings
    eff = dict(settings)
    eff["tasks"] = p.get("tasks") or settings.get("tasks", [])
    eff["loop_minutes"] = p.get("loop_minutes") or settings.get("loop_minutes", 60)
    return eff


# ---------------------------------------------------------------- TASK-16: daily stats file in kingbot-syn
DS_LAST = [0.0]


def daily_stats_payload():
    import smart
    d = smart._stats_load()
    days = d.get("days") or {}
    keep = sorted(days)[-30:]
    return {"updated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "days": {k: days[k] for k in keep},
            "by_char": {w: {k: v for k, v in (bc or {}).items() if k in keep} for w, bc in (d.get("by_char") or {}).items()}}


def publish_daily_stats(force=False):
    """Once an hour: history/<server id>/daily_stats.json (sealed like the status when encryption is on)."""
    if not force and time.time() - DS_LAST[0] < 3600:
        return
    DS_LAST[0] = time.time()
    try:
        import control, server_config
        body = control._seal_json(daily_stats_payload())
        path = f"history/{server_config.server_id()}/daily_stats.json"
        control._gh_put_bytes(path, json.dumps(body, ensure_ascii=False).encode("utf-8"), "bot: daily stats")
    except Exception as e:
        log(f"  ! daily stats upload failed: {e!r}")
