"""Ayarlar. Eşikler tahmindir; karne verisi biriktikçe güncellenecek."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
WEB_DATA = ROOT / "web" / "data"

# iddaa.com resmi bülten
IDDAA_BASE = "https://sportsbookv2.iddaa.com/sportsbook"
IDDAA_SUPER_LIG_CI = 584          # "Türkiye Süper Lig"

# Pinnacle (PinnWire). Anahtar yoksa bu kaynak atlanır.
PINNWIRE_KEY = os.environ.get("PINNWIRE_KEY", "").strip()
PINNWIRE_BASE = "https://pinnwire.com"
PINNACLE_LEAGUE_HINTS = ("turkey", "super lig")   # league_name içinde aranır

# Skorlar (karne için)
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/summary"

# Haber filtresi
NEWS_RSS = "https://news.google.com/rss/search"
NEWS_WINDOW_HOURS = 36
NEWS_CACHE_HOURS = 6
NEWS_KEYWORDS = (
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
