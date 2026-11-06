"""Tek seferlik keşif: yeni kaynakların gerçek yanıt yapısını loglar (anahtarları yazdırmaz)."""
import json, os, sys, urllib.request, urllib.parse
UA = "Mozilla/5.0 oran-sinyal"
def get(url, params=None, headers=None):
    if params: url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    h = {"User-Agent": UA, "Accept": "application/json"}; h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            hdr = {k: v for k, v in r.headers.items() if any(x in k.lower() for x in ("remain", "limit", "quota", "request"))}
            return json.loads(r.read().decode()), hdr
    except urllib.error.HTTPError as e:
        return {"HTTP": e.code, "body": e.read().decode()[:400]}, {}
    except Exception as e:
        return {"ERR": str(e)[:300]}, {}
def show(t, obj, n=1500): print(f"\n===== {t} =====\n" + json.dumps(obj, ensure_ascii=False)[:n])
def shape(o, d=0):
    if d > 4: return "…"
    if isinstance(o, dict): return {k: shape(v, d+1) for k, v in list(o.items())[:14]}
    if isinstance(o, list): return [shape(o[0], d+1), f"len={len(o)}"] if o else []
    return type(o).__name__ + ":" + str(o)[:30]

def main():
    OK = os.environ.get("ODDSPAPI_KEY", ""); FK = os.environ.get("FOOTBALL_DATA_KEY", "")
    print("anahtarlar:", {"ODDSPAPI": bool(OK), "FOOTBALL_DATA": bool(FK)})

    # --- OddsPapi (≈3 sorgu) ---
    if OK:
        B = "https://api.oddspapi.io/v4"
        t, h = get(f"{B}/tournaments", {"sportId": 10, "apiKey": OK}); print("kota başlıkları:", h)
        if isinstance(t, list):
            keys = ("premier league", "laliga", "la liga", "serie a", "bundesliga", "ligue 1", "super lig", "süper lig", "1. lig", "1 lig", "tff")
            hits = [x for x in t if any(k in json.dumps(x, ensure_ascii=False).lower() for k in keys)]
            show("oddspapi turnuva örnek", t[:1]); show("oddspapi eşleşen turnuvalar", hits, 4000)
        else: show("oddspapi tournaments", t)
        f, h = get(f"{B}/fixtures", {"tournamentId": 17, "apiKey": OK}); print("kota:", h)
        show("oddspapi fixtures şekil", shape(f), 2500)
        fid = None
        if isinstance(f, list) and f:
            fid = f[0].get("fixtureId"); show("oddspapi fixture[0]", f[0], 1200)
        if fid:
            hist, h = get(f"{B}/historical-odds", {"fixtureId": fid, "bookmakers": "pinnacle,singbet,sbobet", "apiKey": OK}); print("kota:", h)
            show("oddspapi historical şekil", shape(hist), 3000)
            try:
                for bk, v in hist["bookmakers"].items():
                    m = v["markets"]; print("bookmaker", bk, "pazarlar:", list(m)[:25])
            except Exception as e: print("hist parse:", e)

    # --- football-data ---
    if FK:
        d, h = get("https://api.football-data.org/v4/competitions/PL/matches", {"dateFrom": "2026-11-01", "dateTo": "2026-11-05"}, {"X-Auth-Token": FK}); print("fd başlık:", h)
        show("football-data şekil", shape(d), 2500)
        if isinstance(d, dict) and d.get("matches"): show("football-data maç[0]", d["matches"][0], 1500)

    # --- Polymarket ---
    G = "https://gamma-api.polymarket.com"
    s, _ = get(f"{G}/sports")
    if isinstance(s, list):
        show("polymarket sports (futbol olanlar)", [x for x in s if any(k in json.dumps(x).lower() for k in ("epl", "lal", "sea", "bun", "fl1", "lig", "tur", "ucl"))], 3000)
    for tag in (82, 306, 100639, 100350):
        e, _ = get(f"{G}/events", {"tag_id": tag, "closed": "false", "limit": 3})
        if isinstance(e, list) and e:
            print(f"\n--- tag {tag}: {len(e)} etkinlik; başlıklar:", [x.get("title") for x in e])
            ev = e[0]
            show(f"polymarket tag {tag} etkinlik alanları", {k: ev.get(k) for k in ("title","slug","startDate","endDate","volume","volume24hr","liquidity","gameId","seriesSlug","eventDate","startTime")})
            mk = (ev.get("markets") or [{}])[0]
            show("polymarket market alanları", {k: mk.get(k) for k in ("question","outcomes","outcomePrices","volume","volumeNum","volume24hr","groupItemTitle","sportsMarketType","gameStartTime","lastTradePrice","oneDayPriceChange")})
        else: print(f"tag {tag}:", str(e)[:200])

if __name__ == "__main__":
    main()
