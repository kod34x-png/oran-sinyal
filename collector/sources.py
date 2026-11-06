"""Veri kaynakları: iddaa.com, Pinnacle (PinnWire), ESPN skorlar, Google Haberler."""
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import config as C
from util import http_json, http_get, parse_iso, now_ts
from markets import family_of, canon_outcome, market_key


# ---------------- iddaa ----------------
def iddaa_market_config():
    try:
        data = http_json(f"{C.IDDAA_BASE}/get_market_config")["data"]["m"]
    except Exception as e:
        print(f"[iddaa] market config alınamadı: {e}")
        return {}
    out = {}
    for k, v in data.items():
        if isinstance(v, dict):
            out[str(k)] = v.get("n") or ""
    return out


def iddaa_league_map():
    """iddaa yarışma id -> lig key. Adla çözülür, bulunamazsa yedek ci."""
    by_name = {}
    try:
        comps = http_json(f"{C.IDDAA_BASE}/competitions").get("data", [])
        for c in comps:
            if str(c.get("si")) == "1":
                by_name[(c.get("n") or "").strip()] = c.get("i")
    except Exception as e:
        print(f"[iddaa] yarışma listesi alınamadı: {e}")
    out = {}
    for lg in C.LEAGUES:
        ci = by_name.get(lg["iddaa"], lg["ci"])
        if ci is None:
            print(f"[iddaa] UYARI: '{lg['iddaa']}' bulunamadı")
            continue
        out[int(ci)] = lg["key"]
    return out


def iddaa_events(catalog):
    """Takip edilen liglerin maçları + pazar oranları.
    catalog: state'teki pazar kataloğu (yerinde güncellenir)."""
    names = iddaa_market_config()
    leagues = iddaa_league_map()
    raw = http_json(f"{C.IDDAA_BASE}/events", {"st": 1, "type": 0, "version": 0})
    events = raw.get("data", {}).get("events", [])
    out = []
    for ev in events:
        try:
            lkey = leagues.get(int(ev.get("ci")))
        except (TypeError, ValueError):
            lkey = None
        if not lkey:
            continue
        odds = {}
        for m in ev.get("m", []) or []:
            t, st, sov = m.get("t"), m.get("st"), m.get("sov")
            outs = m.get("o") or []
            oname = [o.get("n", "") for o in outs]
            cfg_name = names.get(f"{t}_{st}", "")
            ck = f"{t}_{st}"
            if ck not in catalog:
                catalog[ck] = {"name": cfg_name, "outcomes": oname, "sov": sov}
            fam = family_of(t, st, sov, cfg_name, oname)
            if not fam:
                continue
            mk = market_key(*fam)
            if fam[0] == "AU" and not (0.5 <= fam[1] <= 4.5):
                continue
            for o in outs:
                odd = o.get("odd")
                if not odd or odd <= 1.0:
                    continue
                odds[f"{mk}|{canon_outcome(fam[0], o.get('n', ''))}"] = round(float(odd), 2)
        out.append({
            "league": lkey,
            "iddaa_id": ev.get("i"),
            "home": ev.get("hn"),
            "away": ev.get("an"),
            "kickoff": int(ev.get("d") or 0),
            "live": bool(ev.get("il")),
            "odds": odds,
        })
    return out


# ---------------- Pinnacle ----------------
def pinnacle_events():
    if not C.PINNWIRE_KEY:
        return None
    raw = http_json(f"{C.PINNWIRE_BASE}/kit/v1/prematch/fixtures", {"sport_id": 1},
                    headers={"x-api-key": C.PINNWIRE_KEY})
    items = raw if isinstance(raw, list) else (raw.get("events") or raw.get("data") or raw.get("fixtures") or [])
    if isinstance(items, dict):
        items = items.get("events") or items.get("fixtures") or list(items.values())
    leagues = sorted({str(e.get("league_name")) for e in items if isinstance(e, dict)})
    print(f"[pinnacle] yanıt: {type(raw).__name__} anahtarlar={list(raw)[:8] if isinstance(raw, dict) else '-'} "
          f"etkinlik={len(items)} lig={len(leagues)}")
    want = {lg["pin"].lower(): lg["key"] for lg in C.LEAGUES}
    missing = [n for n in want if n not in {l.lower() for l in leagues}]
    if missing:
        print("[pinnacle] UYARI: bulunamayan ligler:", missing,
              "| benzerleri:", [l for l in leagues if any(w.split(" - ")[0] in l.lower() for w in missing)][:15])
    out = []
    for ev in items:
        lkey = want.get((ev.get("league_name") or "").lower())
        if not lkey:
            continue
        p0 = (ev.get("periods") or {}).get("num_0") or {}
        odds = {}
        ml = p0.get("money_line") or {}
        for side, oc in (("home", "1"), ("draw", "X"), ("away", "2")):
            if ml.get(side):
                odds[f"MS|{oc}"] = round(float(ml[side]), 3)
        for pts, tot in (p0.get("totals") or {}).items():
            try:
                line = float(tot.get("points", pts))
            except (TypeError, ValueError):
                continue
            if line not in (1.5, 2.5, 3.5):
                continue
            if tot.get("over"):
                odds[f"AU{line:g}|Üst"] = round(float(tot["over"]), 3)
            if tot.get("under"):
                odds[f"AU{line:g}|Alt"] = round(float(tot["under"]), 3)
        try:
            k = parse_iso(ev["starts"])
        except Exception:
            continue
        out.append({"league": lkey, "pin_id": ev.get("event_id"), "home": ev.get("home"),
                    "away": ev.get("away"), "kickoff": k, "odds": odds})
    return out


# ---------------- ESPN skorlar ----------------
def espn_results(code, date_from, date_to):
    """date_* = 'YYYYMMDD'. -> [{home, away, kickoff, ft:(h,a), ht:(h,a)|None, done}]"""
    raw = http_json(C.ESPN_SCOREBOARD.format(code=code), {"dates": f"{date_from}-{date_to}", "limit": 300})
    out = []
    for ev in raw.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        st = (comp.get("status") or {}).get("type") or {}
        teams = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        if "home" not in teams or "away" not in teams:
            continue
        h, a = teams["home"], teams["away"]

        def score(c):
            try:
                return int(float(c.get("score")))
            except (TypeError, ValueError):
                return None

        ft = (score(h), score(a))
        ht = None
        try:
            lh, la = h.get("linescores") or [], a.get("linescores") or []
            if lh and la:
                ht = (int(float(lh[0]["value"])), int(float(la[0]["value"])))
        except Exception:
            ht = None
        out.append({
            "home": h["team"].get("displayName"), "away": a["team"].get("displayName"),
            "kickoff": parse_iso(ev["date"]),
            "ft": ft if None not in ft else None, "ht": ht,
            "done": bool(st.get("completed")),
            "status": st.get("name"),
        })
    return out


# ---------------- Haberler ----------------
def team_news(team, lang="tr"):
    """Takımla ilgili son NEWS_WINDOW_HOURS içindeki kritik haber başlıkları."""
    kw = " OR ".join(f'"{k}"' for k in C.NEWS_QUERY[lang])
    q = f'"{team}" ({kw}) when:2d'
    txt = http_get(C.NEWS_RSS, {"q": q, **C.NEWS_LOCALE[lang]},
                   headers={"Accept": "application/rss+xml, application/xml"}, retries=1)
    root = ET.fromstring(txt)
    cutoff = now_ts() - C.NEWS_WINDOW_HOURS * 3600
    words = [w for w in re.sub(r"[^\w ]", " ", team.lower()).split() if len(w) >= 4 and w not in ("united", "city", "club", "spor")]
    tname = max(words, key=len) if words else team.lower()
    hits = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        tl = title.lower()
        try:
            ts = int(parsedate_to_datetime(it.findtext("pubDate")).timestamp())
        except Exception:
            continue
        if ts < cutoff or tname not in tl:
            continue
        if any(k in tl for k in C.NEWS_KEYWORDS):
            hits.append({"title": re.sub(r"\s+", " ", title)[:160],
                         "link": it.findtext("link"), "ts": ts})
    return hits[:5]


# ---------------- Polymarket (maç başı gerçek para hacmi) ----------------
def polymarket_matches(series_id):
    """-> [{home, away, kickoff, prices:{1,X,2}, volumes:{1,X,2}, total_volume}]"""
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    from util import team_sim
    now = now_ts()
    raw = http_json(f"{C.POLYMARKET_BASE}/events",
                    {"series_id": series_id, "closed": "false", "limit": 200,
                     "end_date_min": _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    out = []
    for ev in raw if isinstance(raw, list) else []:
        title = ev.get("title") or ""
        if " - " in title or " vs. " not in title:
            continue                                  # yan piyasalar (korner, skor vb.)
        try:
            k = parse_iso((ev.get("startTime") or ev.get("endDate")).replace(" ", "T"))
        except Exception:
            continue
        if not (now - 3600 < k < now + 8 * 86400):
            continue
        home, away = [x.strip() for x in title.split(" vs. ", 1)]
        prices, vols = {}, {}
        for mk in ev.get("markets") or []:
            if mk.get("sportsMarketType") != "moneyline":
                continue
            git = mk.get("groupItemTitle") or ""
            if git.lower().startswith("draw"):
                oc = "X"
            elif team_sim(git, home) >= team_sim(git, away):
                oc = "1"
            else:
                oc = "2"
            try:
                p = float(_json.loads(mk.get("outcomePrices") or "[]")[0])
            except Exception:
                continue
            prices[oc] = round(p, 4)
            vols[oc] = round(float(mk.get("volumeNum") or 0), 2)
        if len(prices) == 3:
            out.append({"home": home, "away": away, "kickoff": k, "prices": prices,
                        "volumes": vols, "total_volume": round(sum(vols.values()), 2)})
    return out


# ---------------- OddsPapi (Asya keskin şirketleri + gerçek açılış) ----------------
def oddspapi_fixtures(tournament_id):
    from datetime import datetime as _dt, timezone as _tz
    raw = http_json(f"{C.ODDSPAPI_BASE}/fixtures", {"tournamentId": tournament_id, "apiKey": C.ODDSPAPI_KEY})
    now = now_ts()
    out = []
    for f in raw if isinstance(raw, list) else []:
        try:
            k = parse_iso(f["startTime"].replace(".000Z", "Z"))
        except Exception:
            continue
        if now - 6 * 3600 < k < now + 10 * 86400:
            out.append({"fid": f["fixtureId"], "home": f.get("participant1Name"),
                        "away": f.get("participant2Name"), "kickoff": k})
    return out


OP_OUTCOME = {"101": "1", "102": "X", "103": "2"}


def oddspapi_history(fixture_id):
    """-> {bookmaker: {"1": [[ts, price],...], "X": ..., "2": ...}} (1X2 pazarı)"""
    from util import parse_iso as _p
    raw = http_json(f"{C.ODDSPAPI_BASE}/historical-odds",
                    {"fixtureId": fixture_id, "bookmakers": "pinnacle," + ",".join(C.ASIA_BOOKS),
                     "apiKey": C.ODDSPAPI_KEY})
    out = {}
    for bk, v in (raw.get("bookmakers") or {}).items():
        m = (v.get("markets") or {}).get("101") or {}
        series = {}
        for oid, ov in (m.get("outcomes") or {}).items():
            oc = OP_OUTCOME.get(str(oid))
            pts = ((ov.get("players") or {}).get("0")) or []
            s = []
            for pnt in pts:
                if not pnt.get("active", True) or not pnt.get("price"):
                    continue
                try:
                    s.append([_p(pnt["createdAt"].replace(".000Z", "Z")[:19] + "Z"), float(pnt["price"])])
                except Exception:
                    continue
            if oc and s:
                s.sort()
                series[oc] = s
        if series:
            out[bk] = series
    return out


# ---------------- football-data.org (yedek skor) ----------------
def football_data_results(code, date_from, date_to):
    """date_* = 'YYYY-MM-DD'"""
    raw = http_json(f"{C.FOOTBALL_DATA_BASE}/competitions/{code}/matches",
                    {"dateFrom": date_from, "dateTo": date_to},
                    headers={"X-Auth-Token": C.FOOTBALL_DATA_KEY})
    out = []
    for m in raw.get("matches", []):
        ft = (m.get("score") or {}).get("fullTime") or {}
        ht = (m.get("score") or {}).get("halfTime") or {}
        done = m.get("status") == "FINISHED" and ft.get("home") is not None
        out.append({"home": m["homeTeam"].get("name"), "away": m["awayTeam"].get("name"),
                    "kickoff": parse_iso(m["utcDate"]),
                    "ft": (ft["home"], ft["away"]) if done else None,
                    "ht": (ht["home"], ht["away"]) if done and ht.get("home") is not None else None,
                    "done": done, "status": m.get("status")})
    return out
