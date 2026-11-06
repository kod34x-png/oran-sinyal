"""Sinyal motoru: oran geçmişinden güçlü/zayıf sinyal üretir."""
import config as C
from markets import market_label, pick_label

PIN_MARKETS = ("MS", "AU1.5", "AU2.5", "AU3.5")


def _series_stats(series, until_ts, now_ts):
    """series=[[ts, odd],...] -> dict veya None. until_ts'ten sonrası yok sayılır."""
    pts = [p for p in series if p[0] <= until_ts]
    if len(pts) < 1:
        return None
    o, c = pts[0][1], pts[-1][1]
    drop = (o - c) / o if o else 0.0
    ref_ts = now_ts - C.LATE_MOVE_HOURS * 3600
    before = [p for p in pts if p[0] <= ref_ts]
    base_recent = before[-1][1] if before else o
    recent_drop = (base_recent - c) / base_recent if base_recent else 0.0
    return {"open": o, "cur": c, "drop": round(drop, 4),
            "recent_drop": round(recent_drop, 4), "n": len(pts),
            "first_ts": pts[0][0]}


def _level_iddaa_only(d):
    for lvl in ("cok_guclu", "guclu", "zayif"):
        if d >= C.THRESHOLDS_IDDAA_ONLY[lvl]:
            return lvl
    return None


def _level_with_pin(pin_d, id_d):
    T = C.THRESHOLDS_WITH_PIN
    if pin_d >= T["cok_guclu"]["pin"] and id_d >= T["cok_guclu"]["iddaa"]:
        return "cok_guclu"
    if (pin_d >= T["guclu"]["pin"] and id_d >= T["guclu"]["iddaa"]) or pin_d >= T["cok_guclu"]["pin"]:
        return "guclu"
    if pin_d >= T["zayif"]["pin"]:
        return "zayif"
    # Pinnacle kıpırdamadıysa iddaa tek başına en fazla "zayıf" verir
    if _level_iddaa_only(id_d) in ("cok_guclu", "guclu"):
        return "zayif"
    return None


def _downgrade(lvl):
    i = C.LEVELS.index(lvl)
    return C.LEVELS[max(0, i - 1)]


def compute(match, now_ts, until_ts=None, news_hits=None):
    until_ts = until_ts or now_ts
    id_src = match.get("src", {}).get("iddaa", {})
    pin_src = match.get("src", {}).get("pin", {})
    by_market = {}
    for key, series in id_src.items():
        mkey, outc = key.split("|", 1)
        s = _series_stats(series, until_ts, now_ts)
        if not s or s["cur"] < C.MIN_ODD:
            continue
        p = _series_stats(pin_src[key], until_ts, now_ts) if key in pin_src else None
        use_pin = p is not None and mkey in PIN_MARKETS and p["n"] >= 2
        lvl = _level_with_pin(p["drop"], s["drop"]) if use_pin else _level_iddaa_only(s["drop"])
        if not lvl:
            continue
        strength = max(s["drop"], p["drop"] if use_pin else 0)
        cand = {
            "market": mkey, "market_label": market_label(mkey),
            "pick": outc, "pick_label": pick_label(mkey, outc),
            "level": lvl, "raw_level": lvl,
            "iddaa": {"open": s["open"], "cur": s["cur"], "drop": s["drop"]},
            "pin": ({"open": p["open"], "cur": p["cur"], "drop": p["drop"]} if use_pin else None),
            "late": (s["drop"] > 0 and s["recent_drop"] / s["drop"] >= 0.6)
                    or (use_pin and p["drop"] > 0 and p["recent_drop"] / p["drop"] >= 0.6),
            "spark": [x[1] for x in series if x[0] <= until_ts][-40:],
            "_strength": strength,
        }
        if mkey not in by_market or strength > by_market[mkey]["_strength"]:
            by_market[mkey] = cand

    out = []
    for c in by_market.values():
        c.pop("_strength", None)
        if news_hits:
            c["news"] = news_hits
            c["level"] = _downgrade(c["level"])
        else:
            c["news"] = []
        c["level_label"] = C.LEVEL_LABEL[c["level"]]
        out.append(c)
    out.sort(key=lambda x: (-C.LEVELS.index(x["level"]), -x["iddaa"]["drop"]))
    return out
