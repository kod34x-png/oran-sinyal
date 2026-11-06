"""Ağsız uçtan uca test: sahte kaynaklarla 3 çalıştırma simüle eder."""
import sys, shutil, tempfile, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collector"))

import config as C
tmp = Path(tempfile.mkdtemp())
C.STATE_DIR = tmp / "state"
C.WEB_DATA = tmp / "data"
C.PINNWIRE_KEY = "x"

import util, sources, main, markets, enrich
C.ODDSPAPI_KEY = "y"; C.FOOTBALL_DATA_KEY = ""

T0 = 1_800_000_000
clock = {"t": T0}
util.now_ts = lambda: clock["t"]
main.now_ts = lambda: clock["t"]
KO = T0 + 30 * 3600

# family detection sanity
assert markets.family_of(1, 1, None, "", ["1", "0", "2"]) == ("MS", None)
assert markets.family_of(2, 101, "2.5", "", ["Alt", "Üst"]) == ("AU", 2.5)
assert markets.family_of(2, 89, None, "", ["Var", "Yok"]) == ("KG", None)
assert markets.family_of(2, 92, None, "", ["1 ve 0", "1 ve 2", "0 ve 2"]) == ("CS", None)
assert markets.family_of(2, 100, "1", "", ["1", "0", "2"]) is None
assert markets.family_of(2, 88, None, "1st Half Result", ["1", "0", "2"]) == ("IY", None)
assert markets.family_of(2, 603, "0.5", "1st half totals", ["Alt", "Üst"]) is None
REAL = {"1_1":("Maç Sonucu",["1","0","2"],None,("MS",None)),"2_88":("1. Yarı Sonucu",["1","0","2"],None,("IY",None)),
 "2_36":("2. Yarı Sonucu",["1","0","2"],None,None),"2_100":("Handikaplı Maç Sonucu {h}",["1","0","2"],"1",None),
 "2_89":("Karşılıklı Gol",["Var","Yok"],None,("KG",None)),"2_720":("1. Yarı Karşılıklı Gol",["Var","Yok"],None,None),
 "2_92":("Çifte Şans",["1 ve 0","1 ve 2","0 ve 2"],None,("CS",None)),"2_77":("1. Yarı Çifte Şans",["1 ve 0","1 ve 2","0 ve 2"],None,None),
 "2_101":("Alt/Üst {0}",["Alt","Üst"],"2.5",("AU",2.5)),"2_60":("1. Yarı Alt/Üst {0}",["Alt","Üst"],"0.5",None),
 "2_603":("Ev Sahibi Alt/Üst {0}",["Alt","Üst"],"1.5",None),"2_48":("Toplam Korner Sayısı Alt/Üst {0}",["Alt","Üst"],"8.5",None),
 "2_722":("Ev Sahibi 1. Yarı Altı/Üstü {0}",["Alt","Üst"],"0.5",None)}
for k,(n,o,sov,exp) in REAL.items():
    t,st=map(int,k.split("_")); got=markets.family_of(t,st,sov,n,o)
    assert got==exp,(k,n,got,exp)
assert markets.settle("AU2.5", "Üst", (2, 1)) is True
assert markets.settle("CS", "X2", (1, 1)) is True
assert markets.settle("KG", "Var", (1, 0)) is False
assert util.team_sim("Başakşehir FK", "Istanbul Basaksehir") >= 0.9
assert util.team_sim("Fenerbahçe", "Fenerbahce") == 1.0


def fake_iddaa(odds):
    return lambda catalog: [{"league": "TR1", "iddaa_id": 111, "home": "Fenerbahçe", "away": "Başakşehir FK",
                             "kickoff": KO, "live": False, "odds": odds}]


def fake_pin(odds):
    return lambda: [{"league": "TR1", "pin_id": 9, "home": "Fenerbahce", "away": "Istanbul Basaksehir",
                     "kickoff": KO + 60, "odds": odds}]


sources.team_news = lambda team, lang="tr": []
PM = {"i": 0}
def fake_pm(series_id):
    if series_id != "10292": return []
    i = PM["i"]
    return [{"home": "Fenerbahçe SK", "away": "Rams Başakşehir FK", "kickoff": KO, "prices": {"1": 0.55 - .05*i, "X": .25, "2": .20 + .05*i},
             "volumes": {"1": 50000, "X": 10000, "2": 20000 + 15000*i}, "total_volume": 80000 + 15000*i}]
sources.polymarket_matches = fake_pm
sources.oddspapi_fixtures = lambda tid: [{"fid": "F1", "home": "Fenerbahce", "away": "Basaksehir", "kickoff": KO}]
OPCALLS = {"n": 0}
def fake_hist(fid):
    OPCALLS["n"] += 1
    return {"pinnacle": {"2": [[T0-86400*10, 6.0], [T0, 4.1]]}, "singbet": {"2": [[T0-86400*9, 5.8], [T0, 4.0]]}}
sources.oddspapi_history = fake_hist
sources.espn_results = lambda code, a, b: [{"home": "Fenerbahçe", "away": "Başakşehir",
                                      "kickoff": KO, "ft": (0, 2), "ht": (0, 1), "done": True}]

runs = [
    ({"MS|1": 1.60, "MS|X": 4.00, "MS|2": 5.50, "AU2.5|Üst": 1.70, "AU2.5|Alt": 2.05, "KG|Var": 1.80, "KG|Yok": 1.90},
     {"MS|1": 1.65, "MS|X": 4.10, "MS|2": 5.80, "AU2.5|Üst": 1.75, "AU2.5|Alt": 2.10}),
    ({"MS|1": 1.75, "MS|X": 3.90, "MS|2": 4.60, "AU2.5|Üst": 1.68, "AU2.5|Alt": 2.08, "KG|Var": 1.55, "KG|Yok": 2.25},
     {"MS|1": 1.85, "MS|X": 4.00, "MS|2": 4.40, "AU2.5|Üst": 1.74, "AU2.5|Alt": 2.12}),
    ({"MS|1": 1.90, "MS|X": 3.80, "MS|2": 4.20, "AU2.5|Üst": 1.66, "AU2.5|Alt": 2.10, "KG|Var": 1.50, "KG|Yok": 2.35},
     {"MS|1": 2.00, "MS|X": 3.95, "MS|2": 4.05, "AU2.5|Üst": 1.73, "AU2.5|Alt": 2.13}),
]
for i, (io, po) in enumerate(runs):
    clock["t"] = T0 + i * 10 * 3600
    PM["i"] = i
    sources.iddaa_events = fake_iddaa(io)
    sources.pinnacle_events = fake_pin(po)
    assert main.main() == 0
clock["t"] = KO - 6 * 3600          # 6 saat kala: OddsPapi devreye girer
assert main.main() == 0

sig = json.loads((C.WEB_DATA / "signals.json").read_text())
print(json.dumps(sig["matches"][0]["signals"], ensure_ascii=False, indent=1)[:1500])
ms = {s["market"]: s for s in sig["matches"][0]["signals"]}
assert ms["MS"]["pick"] == "2" and ms["MS"]["level"] == "cok_guclu", ms["MS"]
assert ms["KG"]["pick"] == "Var"
assert ms["MS"]["pm"]["confirm"] is True, ms["MS"]["pm"]
assert ms["MS"]["asia"]["confirm"] is True and OPCALLS["n"] == 1, (ms["MS"].get("asia"), OPCALLS)
q = json.loads((C.STATE_DIR / "quota.json").read_text()); assert q["used"] == 2, q

# maç sonrası
clock["t"] = KO + 4 * 3600
sources.iddaa_events = fake_iddaa({})
main.main()   # kilitler
clock["t"] = KO + 5 * 3600
main.main()   # sonuçlandırır
k = json.loads((C.WEB_DATA / "karne.json").read_text())
print(json.dumps(k["entries"], ensure_ascii=False, indent=1))
res = {e["market"]: e["result"] for e in k["entries"]}
assert res["MS"] == "tuttu" and res["KG"] == "tutmadı", res
e = [x for x in k["entries"] if x["market"] == "MS"][0]
assert e["pm"] is True and e["asia"] is True and e["clv"] is not None and e["clv"] > 0, e
print("TÜM TESTLER GEÇTİ")
shutil.rmtree(tmp)
