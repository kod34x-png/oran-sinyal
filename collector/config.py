"""Ayarlar. Eşikler tahmindir; karne verisi biriktikçe güncellenecek."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
WEB_DATA = ROOT / "web" / "data"

# iddaa.com resmi bülten
IDDAA_BASE = "https://sportsbookv2.iddaa.com/sportsbook"
# Ligler: iddaa adı (ci çalışırken bulunur, yedek ci), Pinnacle adı, ESPN kodu, haber dili
LEAGUES = [
    {"key": "TR1", "name": "Süper Lig",      "iddaa": "Türkiye Süper Lig",     "ci": 584,  "pin": "Turkey - Super League",   "espn": "tur.1", "lang": "tr"},
    {"key": "TR2", "name": "1. Lig",         "iddaa": "Türkiye 1. Lig",        "ci": 1980, "pin": "Turkey - 1st League",     "espn": "tur.2", "lang": "tr"},
    {"key": "ENG", "name": "Premier Lig",    "iddaa": "İngiltere Premier Lig", "ci": 43,   "pin": "England - Premier League", "espn": "eng.1", "lang": "en"},
    {"key": "ESP", "name": "La Liga",        "iddaa": "İspanya La Liga",       "ci": 129,  "pin": "Spain - La Liga",         "espn": "esp.1", "lang": "en"},
    {"key": "ITA", "name": "Serie A",        "iddaa": "İtalya Serie A",        "ci": None, "pin": "Italy - Serie A",         "espn": "ita.1", "lang": "en"},
    {"key": "GER", "name": "Bundesliga",     "iddaa": "Almanya Bundesliga",    "ci": 45,   "pin": "Germany - Bundesliga",    "espn": "ger.1", "lang": "en"},
    {"key": "FRA", "name": "Ligue 1",        "iddaa": "Fransa Ligue 1",        "ci": 381,  "pin": "France - Ligue 1",        "espn": "fra.1", "lang": "en"},
]

# Pinnacle (PinnWire). Anahtar yoksa bu kaynak atlanır.
PINNWIRE_KEY = os.environ.get("PINNWIRE_KEY", "").strip()
PINNWIRE_BASE = "https://pinnwire.com"

# Skorlar (karne için)
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard"

# Haber filtresi
NEWS_RSS = "https://news.google.com/rss/search"
NEWS_WINDOW_HOURS = 36
NEWS_CACHE_HOURS = 6
NEWS_QUERY = {
    "tr": ("sakat", "cezalı", "kadro dışı", "oynamayacak"),
    "en": ("injury", "injured", "suspended", "ruled out"),
}
NEWS_LOCALE = {"tr": {"hl": "tr", "gl": "TR", "ceid": "TR:tr"},
               "en": {"hl": "en-GB", "gl": "GB", "ceid": "GB:en"}}
NEWS_KEYWORDS = (
    "injur", "suspend", "ruled out", "doubt", "sidelined", "sacked", "red card",
    "sakat", "sakatlık", "cezalı", "kadro dışı", "forma giyemeyecek",
    "oynayamayacak", "oynamayacak", "kart cezası", "ameliyat", "kırmızı kart",
    "teknik direktör", "istifa", "görevden", "kriz",
)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# Sinyal eşikleri (oran düşüşü, açılışa göre, oran olarak 0.15 = %15)
MIN_ODD = 1.15                 # bunun altındaki oranlar sinyal sayılmaz
THRESHOLDS_WITH_PIN = {        # Pinnacle verisi varken
    "cok_guclu": {"pin": 0.15, "iddaa": 0.05},
    "guclu":     {"pin": 0.10, "iddaa": 0.03},
    "zayif":     {"pin": 0.05},
}
THRESHOLDS_IDDAA_ONLY = {      # sadece iddaa varken
    "cok_guclu": 0.20,
    "guclu": 0.12,
    "zayif": 0.06,
}
LATE_MOVE_HOURS = 12           # düşüşün çoğu son 12 saatteyse "geç hareket"
LEVELS = ["zayif", "guclu", "cok_guclu"]
LEVEL_LABEL = {"cok_guclu": "Çok güçlü", "guclu": "Güçlü", "zayif": "Zayıf"}
