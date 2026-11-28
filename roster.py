"""v340: the commander roster in the bot's brain - every Rise of Kingdoms commander with rarity, troop / role and the
other spellings it goes by (commanders_roster.json, same data as kingbot-ui/commanders/roster.json).

- fold(text): one comparable form for any spelling ("Æthelflæd" / "Aethelflaed" -> "aethelflaed").
- canonical(name): the roster name for any alias ("Lu Bu" -> "Lü Bu", "YSG" -> "Yi Seong-Gye").
- variants(name): every folded spelling of that commander, for matching OCR text in the game.
- info(name): {"name", "rarity", "role", "aliases"} or None.
- known(): {folded spelling: canonical name} for reading the commander list.
"""
import json
import os
import re
import unicodedata

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = {"list": None, "by": None}
_ROMAN = re.compile(r"\s+(?:i|ii|iii|iv|v|vi|vii)$", re.I)


def fold(text):
    t = str(text or "").replace("Æ", "AE").replace("æ", "ae").replace("Œ", "OE").replace("œ", "oe")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", t.lower())


def _load():
    if _DATA["list"] is None:
        try:
            with open(os.path.join(_HERE, "commanders_roster.json"), encoding="utf-8") as f:
                _DATA["list"] = json.load(f).get("commanders") or []
        except Exception:
            _DATA["list"] = []
        by = {}
        for c in _DATA["list"]:
            for n in [c["name"]] + list(c.get("aliases") or []):
                for form in (n, _ROMAN.sub("", n.strip())):
                    k = fold(form)
                    if len(k) >= 3:
                        by.setdefault(k, c)
        _DATA["by"] = by
    return _DATA["list"], _DATA["by"]


def info(name):
    return _load()[1].get(fold(name)) or _load()[1].get(fold(_ROMAN.sub("", str(name or "").strip())))


def canonical(name):
    c = info(name)
    return c["name"] if c else str(name or "").strip()


def variants(name):
    c = info(name)
    names = [c["name"]] + list(c.get("aliases") or []) if c else [str(name or "")]
    out = []
    for n in names:
        for form in (n, _ROMAN.sub("", n.strip())):
            k = fold(form)
            if len(k) >= 3 and k not in out:
                out.append(k)
    return out


def known():
    return {k: c["name"] for k, c in _load()[1].items()}


def all_names():
    return [c["name"] for c in _load()[0]]
