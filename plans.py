"""PLAN-01..04: subscription tiers and the activities each one may run.

The admin sets a slot's tier in kingbot-syn  servers/<id>/control.json  "plan"
(solo | leader | solo_leader_bundle | group).  No tier = full access (the owner's own servers).
Leader activities are the routines named leader_*; everything else a round runs is a Solo activity.
System steps (reading the screen, probes, sign-in/out, character restore) always run.
"""
TIERS = {
    "solo": {"name": "Solo", "price": 25, "groups": {"solo"}},
    "leader": {"name": "Leader", "price": 25, "groups": {"leader"}},
    "solo_leader_bundle": {"name": "Solo + Leader", "price": 45, "groups": {"solo", "leader"}},
    "group": {"name": "Group", "price": None, "groups": {"solo", "leader"}},
    # v312: light plan - only these routines (gathering, barbarians, alliance flags, free chests + daily rewards)
    "farms": {"name": "Farms", "name_ar": "باقة المزارع", "price": None, "groups": {"solo"},
              "only": {"gather", "collect_city", "attack_barbarians", "alliance_flag",
                       "tavern", "tavern_legendary", "daily_objectives", "daily_rewards", "vip_chests"}},
}
ALIASES = {"bundle": "solo_leader_bundle", "solo+leader": "solo_leader_bundle", "solo_leader": "solo_leader_bundle",
           "multi": "group", "groups": "group", "farm": "farms", "المزارع": "farms", "باقة_المزارع": "farms"}
LEADER_ROUTINES = {
    "leader_resource_point": "Resource Point", "leader_daily_credit": "Daily Credit", "leader_members": "Members",
    "leader_mobilization": "Alliance Mobilization Event", "leader_rally_mgmt": "Rally Management",
    "leader_titles": "Title Management", "leader_city_finder": "City Finder", "leader_scan_kingdom": "Scan Kingdom Data",
}
SYSTEM_PREFIX = ("read_", "restore_character", "sign_out", "probe")


def tier_of(data):
    """The slot's tier from the control data, or None (= no plan set: everything allowed)."""
    t = str((data or {}).get("plan") or "").strip().lower().replace(" ", "_")
    t = ALIASES.get(t, t)
    return t if t in TIERS else None


def group_of(routine):
    r = str(routine or "")
    if r in LEADER_ROUTINES or r.startswith("leader_"):
        return "leader"
    if r.startswith(SYSTEM_PREFIX) or r.endswith("_probe"):
        return "system"
    return "solo"


def allowed(routine, data):
    """(ok, reason) - reason is a short Arabic line for the log / dashboard when the plan excludes it."""
    tier = tier_of(data)
    g = group_of(routine)
    if tier is None or g == "system":
        return True, ""
    only = TIERS[tier].get("only")
    if only is not None:
        if routine in only:
            return True, ""
        return False, f"{routine}: غير مشمول في {TIERS[tier].get('name_ar') or TIERS[tier]['name']} (جمع المزارع، البرابرة، أعلام التحالف، المكافآت فقط)"
    if g in TIERS[tier]["groups"]:
        return True, ""
    if g == "leader":
        return False, f"{routine}: أوامر القائد غير مشمولة في باقة {TIERS[tier]['name']} - رقِّ إلى Leader أو Solo + Leader"
    return False, f"{routine}: أنشطة اللاعب غير مشمولة في باقة {TIERS[tier]['name']} - رقِّ إلى Solo أو Solo + Leader"


def info(data):
    tier = tier_of(data)
    out = {"tier": tier or "", "name": TIERS[tier]["name"] if tier else "", "groups": sorted(TIERS[tier]["groups"]) if tier else ["leader", "solo"]}
    if tier and TIERS[tier].get("only") is not None:
        out["only"] = sorted(TIERS[tier]["only"])
    return out


if __name__ == "__main__":
    for t in (None, "solo", "leader", "bundle", "group", "farms"):
        d = {"plan": t}
        print(t, [allowed(r, d)[0] for r in ("gather", "leader_members", "read_marches", "sunset_canyon")])
