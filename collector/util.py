import json
import time
import unicodedata
import re
import urllib.request
import urllib.parse
from difflib import SequenceMatcher
from datetime import datetime, timezone

from config import UA

TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")
STOP = {"fk", "sk", "as", "a", "s", "jk", "kulubu", "spor", "futbol", "fc",
        "afc", "ac", "istanbul", "club", "kulub"}


def now_ts() -> int:
    return int(time.time())


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(s: str) -> int:
    s = s.replace("Z", "+00:00")
    if len(s) == 22 and s[16] == "+":     # "2026-10-30T17:00+00:00"
        s = s[:16] + ":00" + s[16:]
    return int(datetime.fromisoformat(s).timestamp())


def http_get(url, params=None, headers=None, timeout=25, retries=2):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
         "Accept-Language": "tr-TR,tr;q=0.9"}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET başarısız: {url.split('?')[0]} -> {last}")


def http_json(url, params=None, headers=None):
    return json.loads(http_get(url, params, headers))


def norm_team(name: str) -> str:
    s = unicodedata.normalize("NFKC", name or "").translate(TR_MAP).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    toks = [t for t in s.split() if t not in STOP]
    return " ".join(toks) or s.strip()


def team_sim(a: str, b: str) -> float:
    a, b = norm_team(a), norm_team(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    contain = 0.9 if (ta <= tb or tb <= ta) else 0.0
    return max(contain, SequenceMatcher(None, a, b).ratio())


def match_pair(home, away, kickoff, candidates, window_h=6, min_score=1.4):
    """candidates: [(obj, home, away, kickoff_ts)] -> en iyi eşleşen obj veya None"""
    best, best_s = None, 0.0
    for obj, h, a, k in candidates:
        if abs((k or kickoff) - kickoff) > window_h * 3600:
            continue
        s = team_sim(home, h) + team_sim(away, a)
        if s > best_s:
            best, best_s = obj, s
    return best if best_s >= min_score else None


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data, pretty=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(data, ensure_ascii=False, indent=1 if pretty else None,
                     separators=None if pretty else (",", ":"), sort_keys=False)
    path.write_text(txt, encoding="utf-8")
