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
E = "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"
for q in ("?dates=20261106-20261108&limit=300", "?dates=20261106-20261108&limit=200", "?dates=20261106-20261108", "?dates=20261107"):
    st, b = get(E + q)
    n = len(json.loads(b).get("events", [])) if st == 200 else None
    print("ESPN", q, st, "events:", n, "" if st == 200 else b[:200])
st, b = get(E + "?dates=20261106-20261108")
if st == 200:
    for ev in json.loads(b)["events"]:
        c = ev["competitions"][0]; t = {x["homeAway"]: x for x in c["competitors"]}
        print("  ", ev["date"], t["home"]["team"]["displayName"], t["home"].get("score"), "-", t["away"].get("score"), t["away"]["team"]["displayName"], c["status"]["type"]["name"])
st, b = get("https://site.api.espn.com/apis/site/v2/sports/soccer/tur.2/scoreboard?dates=20261106-20261108")
print("ESPN tur.2", st, (len(json.loads(b).get("events", [])) if st == 200 else b[:200]))
T = "https://www.thesportsdb.com/api/v1/json/3"
st, b = get(T + "/search_all_leagues.php?c=Turkey&s=Soccer")
print("TSDB leagues", st)
if st == 200:
    for l in (json.loads(b).get("countries") or []): print("  ", l.get("idLeague"), l.get("strLeague"))
for d in ("2026-11-06", "2026-11-07", "2026-11-08"):
    st, b = get(T + f"/eventsday.php?d={d}&s=Soccer")
    if st == 200:
        evs = json.loads(b).get("events") or []
        tr = [e for e in evs if "Turk" in (e.get("strLeague") or "") or "Süper" in (e.get("strLeague") or "") or "1. Lig" in (e.get("strLeague") or "")]
        print("TSDB day", d, "toplam", len(evs), "türk", len(tr))
        for e in tr[:12]: print("   ", e.get("idLeague"), e.get("strLeague"), e.get("strHomeTeam"), e.get("intHomeScore"), "-", e.get("intAwayScore"), e.get("strAwayTeam"), e.get("strStatus"), e.get("strTimestamp"))
    else: print("TSDB day", d, st, b[:150])
