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

import util, sources, main, markets

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
assert markets.settle("AU2.5", "Üst", (2, 1)) is True
assert markets.settle("CS", "X2", (1, 1)) is True
assert markets.settle("KG", "Var", (1, 0)) is False
assert util.team_sim("Başakşehir FK", "Istanbul Basaksehir") >= 0.9
assert util.team_sim("Fenerbahçe", "Fenerbahce") == 1.0


def fake_iddaa(odds):
    return lambda catalog: [{"iddaa_id": 111, "home": "Fenerbahçe", "away": "Başakşehir FK",
                             "kickoff": KO, "live": False, "odds": odds}]


def fake_pin(odds):
    return lambda: [{"pin_id": 9, "home": "Fenerbahce", "away": "Istanbul Basaksehir",
                     "kickoff": KO + 60, "odds": odds}]


sources.team_news = lambda team: []
sources.espn_results = lambda a, b: [{"home": "Fenerbahçe", "away": "Başakşehir",
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
    sources.iddaa_events = fake_iddaa(io)
    sources.pinnacle_events = fake_pin(po)
    assert main.main() == 0

sig = json.loads((C.WEB_DATA / "signals.json").read_text())
print(json.dumps(sig["matches"][0]["signals"], ensure_ascii=False, indent=1)[:1500])
ms = {s["market"]: s for s in sig["matches"][0]["signals"]}
assert ms["MS"]["pick"] == "2" and ms["MS"]["level"] == "cok_guclu", ms["MS"]
assert ms["KG"]["pick"] == "Var"

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
print("TÜM TESTLER GEÇTİ")
shutil.rmtree(tmp)
