"""Her çalıştırmada: oranları çek -> geçmişe ekle -> sinyal üret -> başlamış maçları kilitle
-> biten maçları karneye işle -> web/data dosyalarını yaz."""
import sys
import traceback
from datetime import datetime, timezone, timedelta

import time
import config as C
import sources
import signals
import enrich
from markets import settle
from util import now_ts, iso, load_json, save_json, match_pair

HIST = C.STATE_DIR / "history.json"
PENDING = C.STATE_DIR / "pending.json"
CATALOG = C.STATE_DIR / "market_catalog.json"
NEWS = C.STATE_DIR / "news_cache.json"
OPFIX = C.STATE_DIR / "op_fixtures.json"
KARNE = C.WEB_DATA / "karne.json"
SIGNALS = C.WEB_DATA / "signals.json"


def append_point(series_map, key, ts, odd):
    s = series_map.setdefault(key, [])
    if not s or abs(s[-1][1] - odd) > 1e-9:
        s.append([ts, odd])


LEAGUE = {lg["key"]: lg for lg in C.LEAGUES}


def get_news(cache, team, lang, status):
    ent = cache.get(team)
    if ent and now_ts() - ent["ts"] < C.NEWS_CACHE_HOURS * 3600:
        return ent["hits"]
    try:
        time.sleep(0.4)
        hits = sources.team_news(team, lang)
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
              "polymarket": "ok", "asya": "anahtar yok" if not C.ODDSPAPI_KEY else "ok",
              "news": "ok", "results": "ok"}

    # 1) iddaa
    try:
        id_events = sources.iddaa_events(catalog)
    except Exception as e:
        id_events = []
        status["iddaa"] = f"hata: {str(e)[:160]}"
    from collections import Counter
    print(f"[iddaa] {len(id_events)} maç", dict(Counter(e["league"] for e in id_events)))

    # 2) Pinnacle
    pin_events = []
    if C.PINNWIRE_KEY:
        try:
            pin_events = sources.pinnacle_events() or []
            print(f"[pinnacle] {len(pin_events)} maç", dict(Counter(e["league"] for e in pin_events)))
            if not pin_events:
                status["pinnacle"] = "maç bulunamadı"
        except Exception as e:
            status["pinnacle"] = f"hata: {str(e)[:160]}"

    pin_cands = {}
    for p in pin_events:
        pin_cands.setdefault(p["league"], []).append((p, p["home"], p["away"], p["kickoff"]))

    # 3) geçmişe ekle
    for ev in id_events:
        if ev["kickoff"] <= ts:   # not: "il" alanı canlı oynanabilirlik bayrağı, canlı maç değil
            continue
        mid = str(ev["iddaa_id"])
        m = hist["matches"].setdefault(mid, {
            "home": ev["home"], "away": ev["away"], "kickoff": ev["kickoff"],
            "first_seen": ts, "src": {"iddaa": {}, "pin": {}}})
        m["kickoff"] = ev["kickoff"]
        m["league"] = ev["league"]
        for k, odd in ev["odds"].items():
            append_point(m["src"]["iddaa"], k, ts, odd)
        p = match_pair(ev["home"], ev["away"], ev["kickoff"], pin_cands.get(ev["league"], []))
        if p:
            m["pin_id"] = p["pin_id"]
            for k, odd in p["odds"].items():
                append_point(m["src"]["pin"], k, ts, odd)

    # 3b) Polymarket hacmi
    pm_n, pm_err = 0, []
    for lg in C.LEAGUES:
        if not lg.get("pm"):
            continue
        try:
            pms = sources.polymarket_matches(lg["pm"])
        except Exception as e:
            pm_err.append(f"{lg['key']}: {str(e)[:60]}")
            continue
        cands = [(x, x["home"], x["away"], x["kickoff"]) for x in pms]
        for m in hist["matches"].values():
            if m.get("league") != lg["key"] or m.get("locked") or m["kickoff"] <= ts:
                continue
            x = match_pair(m["home"], m["away"], m["kickoff"], cands, window_h=3)
            if x:
                enrich.pm_append(m, x, ts)
                pm_n += 1
    if pm_err:
        status["polymarket"] = "hata: " + "; ".join(pm_err)[:160]
    print(f"[polymarket] {pm_n} maç eşleşti", pm_err or "")

    # 4) sinyaller (yaklaşan maçlar) + kilitleme
    upcoming, live_sigs = [], []
    for mid, m in list(hist["matches"].items()):
        lock_ts = m["kickoff"] - 5 * 60
        if ts >= lock_ts:
            if not m.get("locked"):
                news = (m.get("news_at_lock") or [])
                sigs = signals.compute(m, lock_ts, until_ts=lock_ts, news_hits=news)
                for s_ in sigs:
                    key = f"{s_['market']}|{s_['pick']}"
                    s_["pm"] = enrich.pm_info(m, key, lock_ts)
                    s_["asia"] = enrich.asia_info(m, key)
                    s_["clv"] = enrich.clv(m, s_)
                    signals.finalize(s_)
                    s_.pop("spark", None)
                pending.append({"id": mid, "league": m.get("league", "TR1"), "home": m["home"], "away": m["away"],
                                "kickoff": m["kickoff"], "signals": sigs, "tries": 0})
                m["locked"] = True
            continue
        hours_left = (m["kickoff"] - ts) / 3600
        news = []
        if hours_left <= 48:
            lang = LEAGUE.get(m.get("league", "TR1"), {}).get("lang", "tr")
            news = get_news(news_cache, m["home"], lang, status) + get_news(news_cache, m["away"], lang, status)
            m["news_at_lock"] = news
        sigs = signals.compute(m, ts, news_hits=news)
        enrich.remember_first(m, sigs, ts)
        live_sigs.append((mid, m, sigs))

    # 4b) OddsPapi: güçlü+ maç sonucu sinyallerinde Asya keskin şirketleri + gerçek açılış
    if C.ODDSPAPI_KEY:
        q = enrich.quota_load()
        opfix = load_json(OPFIX, {})
        cands = []
        for mid, m, sigs in live_sigs:
            if (m.get("op") or {}).get("hist") is not None:
                continue
            if (m["kickoff"] - ts) / 3600 > C.ODDSPAPI_HIST_WINDOW_H:
                continue
            strong = [s_ for s_ in sigs if s_["market"] == "MS" and s_["raw_level"] in ("guclu", "cok_guclu")]
            if strong:
                cands.append((max(s_["iddaa"]["drop"] for s_ in strong), m))
        cands.sort(key=lambda x: -x[0])
        fetched = 0
        for _, m in cands:
            lg = LEAGUE.get(m.get("league"))
            if not lg or not lg.get("op") or not enrich.quota_ok(q, hist=True):
                continue
            ent = opfix.get(m["league"])
            if not ent or ts - ent["ts"] > C.ODDSPAPI_FIXTURE_REFRESH_H * 3600:
                if not enrich.quota_ok(q):
                    break
                try:
                    enrich.quota_use(q)
                    opfix[m["league"]] = ent = {"ts": ts, "list": sources.oddspapi_fixtures(lg["op"])}
                except Exception as e:
                    status["asya"] = f"hata: {str(e)[:120]}"
                    continue
            fc = [(f, f["home"], f["away"], f["kickoff"]) for f in ent["list"]]
            f = match_pair(m["home"], m["away"], m["kickoff"], fc, window_h=3)
            if not f:
                m["op"] = {"fid": None, "fetched": ts, "hist": {}}
                continue
            try:
                enrich.quota_use(q, hist=True)
                m["op"] = {"fid": f["fid"], "fetched": ts, "hist": sources.oddspapi_history(f["fid"])}
                fetched += 1
            except Exception as e:
                status["asya"] = f"hata: {str(e)[:120]}"
        enrich.quota_save(q)
        save_json(OPFIX, opfix)
        print(f"[oddspapi] {fetched} maç geçmişi alındı; ay: {q['used']}/{C.ODDSPAPI_MONTHLY_CAP}, bugün: {q['hist_today']}/{C.ODDSPAPI_DAILY_HIST}")
        status["asya_kota"] = f"{q['used']}/{C.ODDSPAPI_MONTHLY_CAP}"

    for mid, m, sigs in live_sigs:
        for s_ in sigs:
            key = f"{s_['market']}|{s_['pick']}"
            s_["pm"] = enrich.pm_info(m, key, ts)
            s_["asia"] = enrich.asia_info(m, key)
            signals.finalize(s_)
            lh = m.setdefault("lvl_hist", {}).setdefault(key, [])
            if not lh or lh[-1][1] != s_["level"]:
                lh.append([ts, s_["level"]])
            s_["history"] = [[iso(t), l] for t, l in lh[-4:]]
        sigs.sort(key=signals.sort_key)
        lk = m.get("league", "TR1")
        upcoming.append({"id": mid, "league": lk, "league_name": LEAGUE.get(lk, {}).get("name", lk),
                         "home": m["home"], "away": m["away"],
                         "kickoff": m["kickoff"], "kickoff_iso": iso(m["kickoff"]),
                         "tracking_since": iso(m["first_seen"]),
                         "pinnacle": bool(m.get("pin_id")),
                         "pm_volume": round(m.get("pm_total") or 0),
                         "signals": sigs})

    # 5) sonuçlar -> karne (lig lig)
    due = [p for p in pending if ts > p["kickoff"] + int(2.5 * 3600)]
    settled_ids, failed = set(), []
    for lk in sorted({p.get("league", "TR1") for p in due}):
        group = [p for p in due if p.get("league", "TR1") == lk]
        d0 = datetime.fromtimestamp(min(p["kickoff"] for p in group), tz=timezone.utc) - timedelta(days=1)
        d1 = datetime.fromtimestamp(max(p["kickoff"] for p in group), tz=timezone.utc) + timedelta(days=1)
        res = []
        try:
            res += sources.espn_results(LEAGUE[lk]["espn"], d0.strftime("%Y%m%d"), d1.strftime("%Y%m%d"))
        except Exception as e:
            failed.append(f"{lk} ESPN: {str(e)[:60]}")
        if C.FOOTBALL_DATA_KEY and LEAGUE[lk].get("fd"):
            try:
                res += sources.football_data_results(LEAGUE[lk]["fd"], d0.strftime("%Y-%m-%d"), d1.strftime("%Y-%m-%d"))
            except Exception as e:
                failed.append(f"{lk} FD: {str(e)[:60]}")
        if LEAGUE[lk].get("tsdb"):
            try:
                res += sources.tsdb_results(LEAGUE[lk]["tsdb"])
            except Exception as e:
                failed.append(f"{lk} TSDB: {str(e)[:60]}")
        res = [r for r in res if r["done"] and r["ft"]]
        cands = [(r, r["home"], r["away"], r["kickoff"]) for r in res]
        for p in group:
            r = match_pair(p["home"], p["away"], p["kickoff"], cands, window_h=30)
            if not (r and r["done"] and r["ft"]):
                continue
            for s_ in p["signals"]:
                ok = settle(s_["market"], s_["pick"], r["ft"], r["ht"])
                unknown = s_["market"] == "IY" and r["ht"] is None
                karne["entries"].append({
                    "id": p["id"], "league": lk, "home": p["home"], "away": p["away"],
                    "kickoff": iso(p["kickoff"]), "score": f"{r['ft'][0]}-{r['ft'][1]}",
                    "ht": f"{r['ht'][0]}-{r['ht'][1]}" if r["ht"] else None,
                    "market": s_["market"], "pick_label": s_["pick_label"],
                    "level": s_["level"], "raw_level": s_.get("raw_level", s_["level"]), "confirmed": s_.get("confirmed"),
                    "odd": s_["iddaa"]["cur"], "pin_odd": (s_["pin"] or {}).get("cur"),
                    "news": bool(s_.get("news")), "late": s_.get("late", False),
                    "pm": (s_.get("pm") or {}).get("confirm"), "asia": (s_.get("asia") or {}).get("confirm"),
                    "clv": (s_.get("clv") or {}).get("clv"), "clv_src": (s_.get("clv") or {}).get("src"),
                    "result": "bilinmiyor" if unknown else ("iade" if ok is None else ("tuttu" if ok else "tutmadı")),
                })
            settled_ids.add(p["id"])
    if failed:
        status["results"] = "hata: " + "; ".join(failed)[:200]
    keep = []
    for p in pending:
        if p["id"] in settled_ids:
            hist["matches"].pop(p["id"], None)
            continue
        if p in due:
            p["tries"] += 1
            if p["tries"] >= 72:                 # ~3 gün denendi, bırak
                hist["matches"].pop(p["id"], None)
                continue
        keep.append(p)
    pending = keep

    # 6) yaz
    upcoming.sort(key=lambda x: x["kickoff"])
    with_sig = [u for u in upcoming if u["signals"]]
    save_json(SIGNALS, {
        "updated": iso(ts), "status": status,
        "tracked_matches": len(upcoming), "matches": with_sig,
        "leagues": [{"key": lg["key"], "name": lg["name"]} for lg in C.LEAGUES],
        "quiet_matches": [{"league": u["league"], "home": u["home"], "away": u["away"], "kickoff_iso": u["kickoff_iso"]}
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
