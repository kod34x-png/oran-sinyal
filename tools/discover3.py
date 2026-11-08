import json, urllib.request, urllib.parse, urllib.error
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return "ERR", repr(e)[:300]


T = "https://www.thesportsdb.com/api/v1/json/123"
for path in ("/eventspastleague.php?id=4676", "/eventsround.php?id=4676&r=12&s=2026-2027", "/eventsseason.php?id=4676&s=2026-2027"):
    st, b = get(T + path)
    print("TSDB", path, st, b[:120] if st != 200 else "")
    if st == 200:
        evs = json.loads(b).get("events") or []
        print("  adet", len(evs))
        for e in evs[-10:]: print("   ", e.get("dateEvent"), e.get("strTime"), e.get("strHomeTeam"), e.get("intHomeScore"), "-", e.get("intAwayScore"), e.get("strAwayTeam"), e.get("strStatus"), e.get("intRound"))
