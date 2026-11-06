"""Her çalıştırmada: oranları çek -> geçmişe ekle -> sinyal üret -> başlamış maçları kilitle
-> biten maçları karneye işle -> web/data dosyalarını yaz."""
import sys
import traceback
from datetime import datetime, timezone, timedelta

import config as C
import sources
import signals
from markets import settle
from util import now_ts, iso, load_json, save_json, match_pair

HIST = C.STATE_DIR / "history.json"
PENDING = C.STATE_DIR / "pending.json"
CATALOG = C.STATE_DIR / "market_catalog.json"
NEWS = C.STATE_DIR / "news_cache.json"
KARNE = C.WEB_DATA / "karne.json"
SIGNALS = C.WEB_DATA / "signals.json"


def append_point(series_map, key, ts, odd):
    s = series_map.setdefault(key, [])
    if not s or abs(s[-1][1] - odd) > 1e-9:
        s.append([ts, odd])


def get_news(cache, team, status):
    ent = cache.get(team)
    if ent and now_ts() - ent["ts"] < C.NEWS_CACHE_HOURS * 3600:
        return ent["hits"]
    try:
        hits = sources.team_news(team)
        cache[team] = {"ts": now_ts(), "hits": hits}
        return hits
    except Exception as e:
        status["news"] = f"hata: {str(e)[:120]}"
        return ent["hits"] if ent else []


def main():
    ts = now_ts()
    hist = load_json(HIST, {"matches": {}})
    pending = load_json(PENDING, [])
    catalog = load_json(CATALOG, {})
    news_cache = load_json(NEWS, {})
    karne = load_json(KARNE, {"entries": []})
    status = {"iddaa": "ok", "pinnacle": "anahtar yok" if not C.PINNWIRE_KEY else "ok",
              "news": "ok", "results": "ok"}

    # 1) iddaa
    try:
        id_events = sources.iddaa_events(catalog)
    except Exception as e:
        id_events = []
        status["iddaa"] = f"hata: {str(e)[:160]}"
    print(f"[iddaa] {len(id_events)} Süper Lig maçı")

    # 2) Pinnacle
    pin_events = []
    if C.PINNWIRE_KEY:
        try:
            pin_events = sources.pinnacle_events() or []
            print(f"[pinnacle] {len(pin_events)} maç")
            if not pin_events:
                status["pinnacle"] = "Süper Lig maçı bulunamadı"
        except Exception as e:
            status["pinnacle"] = f"hata: {str(e)[:160]}"

    pin_cands = [(p, p["home"], p["away"], p["kickoff"]) for p in pin_events]

    # 3) geçmişe ekle
    for ev in id_events:
        if ev["kickoff"] <= ts:   # not: "il" alanı canlı oynanabilirlik bayrağı, canlı maç değil
            continue
        mid = str(ev["iddaa_id"])
        m = hist["matches"].setdefault(mid, {
            "home": ev["home"], "away": ev["away"], "kickoff": ev["kickoff"],
            "first_seen": ts, "src": {"iddaa": {}, "pin": {}}})
        m["kickoff"] = ev["kickoff"]
        for k, odd in ev["odds"].items():
            append_point(m["src"]["iddaa"], k, ts, odd)
        p = match_pair(ev["home"], ev["away"], ev["kickoff"], pin_cands)
        if p:
            m["pin_id"] = p["pin_id"]
            for k, odd in p["odds"].items():
                append_point(m["src"]["pin"], k, ts, odd)

    # 4) sinyaller (yaklaşan maçlar) + kilitleme
    upcoming = []
    for mid, m in list(hist["matches"].items()):
        lock_ts = m["kickoff"] - 5 * 60
        if ts >= lock_ts:
            if not m.get("locked"):
                news = (m.get("news_at_lock") or [])
                sigs = signals.compute(m, lock_ts, until_ts=lock_ts, news_hits=news)
                pending.append({"id": mid, "home": m["home"], "away": m["away"],
                                "kickoff": m["kickoff"], "signals": sigs, "tries": 0})
                m["locked"] = True
            continue
        hours_left = (m["kickoff"] - ts) / 3600
        news = []
        if hours_left <= 48:
            news = get_news(news_cache, m["home"], status) + get_news(news_cache, m["away"], status)
            m["news_at_lock"] = news
        sigs = signals.compute(m, ts, news_hits=news)
        upcoming.append({"id": mid, "home": m["home"], "away": m["away"],
                         "kickoff": m["kickoff"], "kickoff_iso": iso(m["kickoff"]),
                         "tracking_since": iso(m["first_seen"]),
                         "pinnacle": bool(m.get("pin_id")),
                         "signals": [{k: v for k, v in s.items() if k != "raw_level"} for s in sigs]})

    # 5) sonuçlar -> karne
    due = [p for p in pending if ts > p["kickoff"] + int(2.5 * 3600)]
    if due:
        d0 = datetime.fromtimestamp(min(p["kickoff"] for p in due), tz=timezone.utc) - timedelta(days=1)
        d1 = datetime.fromtimestamp(max(p["kickoff"] for p in due), tz=timezone.utc) + timedelta(days=1)
        try:
            res = sources.espn_results(d0.strftime("%Y%m%d"), d1.strftime("%Y%m%d"))
            cands = [(r, r["home"], r["away"], r["kickoff"]) for r in res]
            keep = []
            for p in pending:
                if p not in due:
                    keep.append(p)
                    continue
                r = match_pair(p["home"], p["away"], p["kickoff"], cands, window_h=30)
                if r and r["done"] and r["ft"]:
                    for s in p["signals"]:
                        ok = settle(s["market"], s["pick"], r["ft"], r["ht"])
                        karne["entries"].append({
                            "id": p["id"], "home": p["home"], "away": p["away"],
                            "kickoff": iso(p["kickoff"]), "score": f"{r['ft'][0]}-{r['ft'][1]}",
                            "ht": f"{r['ht'][0]}-{r['ht'][1]}" if r["ht"] else None,
                            "market": s["market"], "pick_label": s["pick_label"],
                            "level": s["level"], "raw_level": s.get("raw_level", s["level"]),
                            "odd": s["iddaa"]["cur"], "pin_odd": (s["pin"] or {}).get("cur"),
                            "news": bool(s.get("news")), "late": s.get("late", False),
                            "result": "iade" if ok is None else ("tuttu" if ok else "tutmadı"),
                        })
                    hist["matches"].pop(p["id"], None)
                else:
                    p["tries"] += 1
                    if p["tries"] < 72:          # ~3 gün dene
                        keep.append(p)
                    else:
                        hist["matches"].pop(p["id"], None)
            pending = keep
        except Exception as e:
            status["results"] = f"hata: {str(e)[:160]}"

    # 6) yaz
    upcoming.sort(key=lambda x: x["kickoff"])
    with_sig = [u for u in upcoming if u["signals"]]
    save_json(SIGNALS, {
        "updated": iso(ts), "status": status,
        "tracked_matches": len(upcoming), "matches": with_sig,
        "quiet_matches": [{"home": u["home"], "away": u["away"], "kickoff_iso": u["kickoff_iso"]}
                          for u in upcoming if not u["signals"]],
    })
    karne["updated"] = iso(ts)
    save_json(KARNE, karne)
    save_json(HIST, hist)
    save_json(PENDING, pending)
    save_json(CATALOG, catalog, pretty=True)
    save_json(NEWS, news_cache)
    print("[durum]", status)
    print(f"[sinyal] {len(with_sig)} maçta sinyal, {len(upcoming)} maç takipte, {len(pending)} sonuç bekliyor")
    return 0 if status["iddaa"] == "ok" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
