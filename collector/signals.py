"""Sinyal motoru (sıkı sürüm).

Ham seviye oran hareketinden gelir; son seviye bağımsız onaylarla belirlenir:
  Çok güçlü = Pinnacle >= %12 + iddaa >= %4 + (Asya VEYA Polymarket onayı) + haber yok
  Güçlü     = Pinnacle >= %10 + iddaa >= %4 + (onay VEYA Pinnacle >= %15) + haber yok
  Zayıf     = Pinnacle >= %8 + iddaa >= %4, ya da onaysız/haberli güçlü hareketler,
              ya da Pinnacle'ın olmadığı pazarlarda iddaa >= %15
Her durumda: en az 3 ölçüm, en az 6 saat takip, düşüşün %30'undan fazlası geri dönmemiş olmalı.
"""
import config as C
from markets import market_label, pick_label

PIN_MARKETS = ("MS", "AU1.5", "AU2.5", "AU3.5")


def _series_stats(series, until_ts, now_ts):
    pts = [p for p in series if p[0] <= until_ts]
    if not pts:
        return None
    o, c = pts[0][1], pts[-1][1]
    low = min(p[1] for p in pts)
    drop = (o - c) / o if o else 0.0
    max_drop = (o - low) / o if o else 0.0
    rebound = ((max_drop - drop) / max_drop) if max_drop > 0 else 0.0
    ref_ts = now_ts - C.LATE_MOVE_HOURS * 3600
    before = [p for p in pts if p[0] <= ref_ts]
    base_recent = before[-1][1] if before else o
    recent_drop = (base_recent - c) / base_recent if base_recent else 0.0
    return {"open": o, "cur": c, "drop": round(drop, 4), "rebound": round(rebound, 3),
            "recent_drop": round(recent_drop, 4), "n": len(pts),
            "span_h": (pts[-1][0] - pts[0][0]) / 3600}


def _solid(s):
    return s["n"] >= C.MIN_POINTS and s["span_h"] >= C.MIN_SPAN_H and s["rebound"] <= C.REBOUND_MAX


def _raw_level(mkey, s, p):
    if p is not None:
        if not (_solid(p) and s["drop"] >= C.ID_BASE and p["drop"] >= C.PIN_BASE and s["rebound"] <= C.REBOUND_MAX):
            return None
        if p["drop"] >= C.PIN_CG:
            return "cok_guclu"
        if p["drop"] >= C.PIN_GUCLU:
            return "guclu"
        return "zayif"
    if mkey in PIN_MARKETS:
        return None                      # Pinnacle verisi gereken pazarda Pinnacle yok
    if _solid(s) and s["drop"] >= C.NOPIN_ZAYIF:
        return "zayif"
    return None


def compute(match, now_ts, until_ts=None, news_hits=None):
    """Ham adaylar (onaysız). Son seviyeyi finalize() verir."""
    until_ts = until_ts or now_ts
    id_src = match.get("src", {}).get("iddaa", {})
    pin_src = match.get("src", {}).get("pin", {})
    by_market = {}
    for key, series in id_src.items():
        mkey, outc = key.split("|", 1)
        s = _series_stats(series, until_ts, now_ts)
        if not s or s["cur"] < C.MIN_ODD:
            continue
        p = _series_stats(pin_src[key], until_ts, now_ts) if (key in pin_src and mkey in PIN_MARKETS) else None
        lvl = _raw_level(mkey, s, p)
        if not lvl:
            continue
        strength = p["drop"] if p else s["drop"] / 2
        cand = {
            "market": mkey, "market_label": market_label(mkey),
            "pick": outc, "pick_label": pick_label(mkey, outc),
            "raw_level": lvl, "level": lvl,
            "iddaa": {"open": s["open"], "cur": s["cur"], "drop": s["drop"]},
            "pin": ({"open": p["open"], "cur": p["cur"], "drop": p["drop"]} if p else None),
            "late": (s["drop"] > 0 and s["recent_drop"] / s["drop"] >= 0.6)
                    or (p is not None and p["drop"] > 0 and p["recent_drop"] / p["drop"] >= 0.6),
            "spark": [x[1] for x in series if x[0] <= until_ts][-40:],
            "news": news_hits or [],
            "_strength": strength,
        }
        if mkey not in by_market or strength > by_market[mkey]["_strength"]:
            by_market[mkey] = cand
    out = list(by_market.values())
    for c in out:
        c.pop("_strength", None)
    return out


def finalize(sig):
    """Onaylara (sig['asia'], sig['pm']) ve habere göre son seviye."""
    raw = sig["raw_level"]
    conf = bool((sig.get("asia") or {}).get("confirm")) or bool((sig.get("pm") or {}).get("confirm"))
    pin_drop = (sig.get("pin") or {}).get("drop", 0)
    reasons = []
    if sig.get("news"):
        lvl = "zayif"
        if raw != "zayif":
            reasons.append("haber var, hareket açıklanabilir")
    elif raw == "cok_guclu":
        lvl = "cok_guclu" if conf else "guclu"
        if not conf:
            reasons.append("onay yok")
    elif raw == "guclu":
        lvl = "guclu" if (conf or pin_drop >= C.PIN_ALONE_GUCLU) else "zayif"
        if lvl == "zayif":
            reasons.append("onay yok")
    else:
        lvl = "zayif"
    sig["level"] = lvl
    sig["confirmed"] = conf
    sig["why_lower"] = reasons
    sig["level_label"] = C.LEVEL_LABEL[lvl]
    return sig


def sort_key(s):
    return (-C.LEVELS.index(s["level"]), -((s.get("pin") or {}).get("drop") or s["iddaa"]["drop"]))
