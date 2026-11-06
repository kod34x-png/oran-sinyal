"""Sinyal onayları ve kapanış testi.

- Polymarket: maç başı gerçek para hacmi. Son 24 saatte yeni paranın çoğu bu tarafa mı gitti?
- Asya (Singbet/SBOBet, OddsPapi üzerinden): keskin Asya şirketleri de aynı yönde düştü mü?
  Ayrıca Pinnacle'ın GERÇEK açılış oranı.
- Kapanış testi (CLV): sinyal ilk çıktığındaki oran, kapanışa kadar düşmeye devam etti mi?

Onaylar sinyal gücünü otomatik değiştirmez; karne hangi onayın işe yaradığını ölçer.
"""
from datetime import datetime, timezone

import config as C
from util import now_ts, load_json, save_json

QUOTA = C.STATE_DIR / "quota.json"


# ---------------- Polymarket ----------------
def pm_append(m, pm, ts):
    src = m.setdefault("src", {})
    pr, vo = src.setdefault("pm", {}), src.setdefault("pmv", {})
    for oc in ("1", "X", "2"):
        k = f"MS|{oc}"
        for store, val in ((pr, pm["prices"].get(oc)), (vo, pm["volumes"].get(oc))):
            if val is None:
                continue
            s = store.setdefault(k, [])
            if not s or s[-1][1] != val:
                s.append([ts, val])
    m["pm_total"] = pm["total_volume"]


def _at(series, ts):
    before = [p for p in series if p[0] <= ts]
    return before[-1][1] if before else (series[0][1] if series else None)


def pm_info(m, key, now):
    if not key.startswith("MS|"):
        return None
    pr = (m.get("src", {}).get("pm") or {}).get(key)
    vols = m.get("src", {}).get("pmv") or {}
    if not pr or not vols:
        return None
    ref = now - 24 * 3600
    new = {k: (s[-1][1] - (_at(s, ref) or 0)) for k, s in vols.items() if s}
    tot_new = sum(max(v, 0) for v in new.values())
    mine = max(new.get(key, 0), 0)
    share = (mine / tot_new) if tot_new > 0 else 0.0
    p0, p1 = pr[0][1], pr[-1][1]
    confirm = tot_new >= C.PM_MIN_NEW_VOLUME and share >= C.PM_CONFIRM_SHARE and (p1 - p0) >= 0
    if (p1 - p0) >= C.PM_CONFIRM_PRICE and share >= C.PM_CONFIRM_SHARE:
        confirm = True
    return {"p_from": round(p0, 3), "p_to": round(p1, 3), "new_vol": round(mine),
            "new_total": round(tot_new), "share": round(share, 2),
            "total_vol": round(m.get("pm_total") or 0), "confirm": bool(confirm)}


# ---------------- OddsPapi bütçesi ----------------
def quota_load():
    q = load_json(QUOTA, {})
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if q.get("month") != month:
        q = {"month": month, "used": 0}
    if q.get("day") != day:
        q["day"], q["hist_today"] = day, 0
    return q


def quota_ok(q, hist=False):
    if q["used"] >= C.ODDSPAPI_MONTHLY_CAP:
        return False
    if hist and q["hist_today"] >= C.ODDSPAPI_DAILY_HIST:
        return False
    return True


def quota_use(q, hist=False):
    q["used"] += 1
    if hist:
        q["hist_today"] += 1


def quota_save(q):
    save_json(QUOTA, q, pretty=True)


# ---------------- Asya onayı ----------------
def asia_info(m, key):
    op = m.get("op") or {}
    hist = op.get("hist")
    if not hist or not key.startswith("MS|"):
        return None
    oc = key.split("|")[1]
    books = {}
    for bk in ("pinnacle",) + tuple(C.ASIA_BOOKS):
        s = (hist.get(bk) or {}).get(oc)
        if s and len(s) >= 1:
            o, c = s[0][1], s[-1][1]
            books[bk] = {"open": o, "cur": c, "drop": round((o - c) / o, 4) if o else 0}
    if not books:
        return None
    asia = [books[b]["drop"] for b in C.ASIA_BOOKS if b in books]
    return {"books": books, "fetched": op.get("fetched"),
            "confirm": bool(asia) and max(asia) >= C.ASIA_CONFIRM_DROP}


# ---------------- Kapanış testi ----------------
def remember_first(m, sigs, ts):
    fs = m.setdefault("first_sig", {})
    for s in sigs:
        k = f"{s['market']}|{s['pick']}"
        if k not in fs:
            fs[k] = {"ts": ts, "iddaa": s["iddaa"]["cur"],
                     "pin": (s.get("pin") or {}).get("cur"), "level": s["level"]}


def clv(m, s):
    fs = (m.get("first_sig") or {}).get(f"{s['market']}|{s['pick']}")
    if not fs:
        return None
    if fs.get("pin") and s.get("pin"):
        a, b, src = fs["pin"], s["pin"]["cur"], "Pinnacle"
    else:
        a, b, src = fs["iddaa"], s["iddaa"]["cur"], "iddaa"
    if not a or not b:
        return None
    return {"src": src, "sig_odd": a, "close_odd": b, "clv": round(a / b - 1, 4)}
