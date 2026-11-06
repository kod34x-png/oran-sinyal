import json, os, sys
sys.path.insert(0, "tools")
from discover import get, show, shape
from datetime import datetime, timezone
OK = os.environ.get("ODDSPAPI_KEY", "")
G = "https://gamma-api.polymarket.com"
s, _ = get(f"{G}/sports")
soc = [x for x in s if x.get("sport") in ("epl","lal","sea","bun","fl1","tur","tsl","ucl","bl2","efl")]
show("polymarket futbol ligleri", [{k: x.get(k) for k in ("sport","name","tags","primaryTagId","series")} for x in soc], 3000)
print("tüm sport kodları:", sorted(x.get("sport") for x in s)[:400])
for x in soc[:6]:
    for params in ({"series_id": x["series"], "closed": "false", "limit": 4}, {"tag_id": x["primaryTagId"], "closed": "false", "limit": 4}):
        e, _ = get(f"{G}/events", params)
        if isinstance(e, list) and e:
            print(f"\n--- {x['sport']} {list(params)[0]}: başlıklar", [ev.get("title") for ev in e])
            ev = e[0]
            show("etkinlik", {k: ev.get(k) for k in ("title","slug","startDate","endDate","startTime","gameId","volume","volume24hr","liquidity")})
            for mk in (ev.get("markets") or [])[:3]:
                show("market", {k: mk.get(k) for k in ("question","outcomes","outcomePrices","volumeNum","volume24hr","groupItemTitle","sportsMarketType","gameStartTime")}, 700)
        else: print(x["sport"], list(params)[0], "->", str(e)[:150])
if OK:
    B = "https://api.oddspapi.io/v4"
    f, _ = get(f"{B}/fixtures", {"tournamentId": 17, "apiKey": OK})
    now = datetime.now(timezone.utc).isoformat()
    up = [x for x in f if x.get("startTime", "") > now][:3] if isinstance(f, list) else []
    show("yaklaşan PL fixture", [{k: x.get(k) for k in ("fixtureId","startTime","participant1Name","participant2Name","hasOdds","statusId")} for x in up])
    if up:
        h, hd = get(f"{B}/historical-odds", {"fixtureId": up[0]["fixtureId"], "bookmakers": "pinnacle,singbet,sbobet", "apiKey": OK})
        print("başlıklar:", hd); show("historical şekil", shape(h), 3000)
        try:
            for bk, v in h["bookmakers"].items():
                m = v.get("markets", {}); print("bk", bk, "pazarlar:", list(m)[:30])
                o = m.get("101", {}).get("outcomes", {})
                for oid, ov in o.items():
                    pl = ov.get("players", {}).get("0", [])
                    print("  101", oid, "nokta", len(pl), "ilk", pl[:1], "son", pl[-1:])
        except Exception as e: print("parse", e, str(h)[:300])
