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
    {"key": "TR1", "name": "Süper Lig", "op": 52, "pm": "10292", "fd": None,      "iddaa": "Türkiye Süper Lig",     "ci": 584,  "pin": "Turkey - Super League",   "espn": "tur.1", "lang": "tr"},
    {"key": "TR2", "name": "1. Lig", "op": 98, "pm": None, "fd": None, "tsdb": 4676,         "iddaa": "Türkiye 1. Lig",        "ci": 1980, "pin": "Turkey - 1st League",     "espn": "tur.2", "lang": "tr"},
    {"key": "ENG", "name": "Premier Lig", "op": 17, "pm": "10188", "fd": "PL",    "iddaa": "İngiltere Premier Lig", "ci": 43,   "pin": "England - Premier League", "espn": "eng.1", "lang": "en"},
    {"key": "ESP", "name": "La Liga", "op": 8, "pm": "10193", "fd": "PD",        "iddaa": "İspanya La Liga",       "ci": 129,  "pin": "Spain - La Liga",         "espn": "esp.1", "lang": "en"},
    {"key": "ITA", "name": "Serie A", "op": 23, "pm": "10203", "fd": "SA",        "iddaa": "İtalya Serie A",        "ci": None, "pin": "Italy - Serie A",         "espn": "ita.1", "lang": "en"},
    {"key": "GER", "name": "Bundesliga", "op": 35, "pm": "10194", "fd": "BL1",     "iddaa": "Almanya Bundesliga",    "ci": 45,   "pin": "Germany - Bundesliga",    "espn": "ger.1", "lang": "en"},
    {"key": "FRA", "name": "Ligue 1", "op": 34, "pm": "10195", "fd": "FL1",        "iddaa": "Fransa Ligue 1",        "ci": 381,  "pin": "France - Ligue 1",        "espn": "fra.1", "lang": "en"},
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

# Sinyal kuralları (sıkı sürüm, 6 Kasım 2026). Düşüşler açılışa göre oran olarak (0.10 = %10).
MIN_ODD = 1.25                 # bunun altındaki oranlar sinyal sayılmaz
MIN_POINTS = 3                 # en az 3 farklı oran ölçümü
MIN_SPAN_H = 6                 # ve en az 6 saatlik takip
REBOUND_MAX = 0.30             # düşüşün %30'undan fazlası geri döndüyse sinyal yok
PIN_BASE, ID_BASE = 0.08, 0.04 # temel şart: Pinnacle >= %8 VE iddaa >= %4 aynı yönde
PIN_GUCLU, PIN_CG = 0.10, 0.12
PIN_ALONE_GUCLU = 0.15         # onay yoksa "güçlü" için Pinnacle en az %15
NOPIN_ZAYIF = 0.15             # Pinnacle'ın olmadığı pazarlar (İY, ÇŞ, KG): iddaa >= %15, en fazla "zayıf"
LATE_MOVE_HOURS = 12           # düşüşün çoğu son 12 saatteyse "geç hareket"
LEVELS = ["zayif", "guclu", "cok_guclu"]
LEVEL_LABEL = {"cok_guclu": "Çok güçlü", "guclu": "Güçlü", "zayif": "Zayıf"}

# --- Ek kaynaklar ---
ODDSPAPI_KEY = os.environ.get("ODDSPAPI_KEY", "").strip()
ODDSPAPI_BASE = "https://api.oddspapi.io/v4"
ODDSPAPI_MONTHLY_CAP = 230        # ücretsiz plan 250; 20 pay
ODDSPAPI_DAILY_HIST = 6           # günde en fazla bu kadar maç geçmişi
ODDSPAPI_HIST_WINDOW_H = 8        # maça bu kadar saat kala güçlü+ sinyaller için sorgu
ODDSPAPI_FIXTURE_REFRESH_H = 72
ASIA_BOOKS = ("singbet", "sbobet")
ASIA_CONFIRM_DROP = 0.05          # Asya keskin şirketlerde en az %5 aynı yönde düşüş

POLYMARKET_BASE = "https://gamma-api.polymarket.com"
PM_CONFIRM_PRICE = 0.03           # olasılık en az 3 puan artmış
PM_CONFIRM_SHARE = 0.5            # son 24 saatteki yeni hacmin en az yarısı bu tarafa
PM_MIN_NEW_VOLUME = 5000          # ve en az 5.000 $ yeni hacim

FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "").strip()
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

TSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"   # ücretsiz test anahtarı
