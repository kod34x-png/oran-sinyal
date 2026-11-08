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

import gzip
for code in ("tur.1", "tur.2"):
    for d in ("20261106", "20261107", "20261108"):
        st, b = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={d}")
        if st != 200: print("ESPN", code, d, st); continue
        evs = json.loads(b).get("events", [])
        print("ESPN", code, d, "events", len(evs))
        for ev in evs:
            c = ev["competitions"][0]; t = {x["homeAway"]: x for x in c["competitors"]}
            print("   ", t["home"]["team"]["displayName"], t["home"].get("score"), "-", t["away"].get("score"), t["away"]["team"]["displayName"], c["status"]["type"]["name"])
T = "https://www.thesportsdb.com/api/v1/json/123"
st, b = get(T + "/search_all_leagues.php?c=Turkey&s=Soccer")
print("TSDB leagues", st, b[:120] if st != 200 else "")
if st == 200:
    for l in (json.loads(b).get("countries") or json.loads(b).get("leagues") or []): print("  ", l.get("idLeague"), l.get("strLeague"))
for d in ("2026-11-07",):
    st, b = get(T + f"/eventsday.php?d={d}&s=Soccer")
    print("TSDB day", d, st, b[:150] if st != 200 else "")
    if st == 200:
        evs = json.loads(b).get("events") or []
        tr = [e for e in evs if any(k in (e.get("strLeague") or "") for k in ("Turk", "Süper", "Lig"))]
        print("  toplam", len(evs), "türk", len(tr))
        for e in tr[:15]: print("   ", e.get("idLeague"), e.get("strLeague"), e.get("strHomeTeam"), e.get("intHomeScore"), "-", e.get("intAwayScore"), e.get("strAwayTeam"), e.get("strStatus"))
