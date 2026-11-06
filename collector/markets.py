"""Pazar aileleri: hangi iddaa pazarını takip ettiğimiz ve nasıl sonuçlandığı.

Aileler: MS (maç sonucu), IY (ilk yarı sonucu), CS (çifte şans),
KG (karşılıklı gol), AU (alt/üst, maç sonu, sov = çizgi).
Bilinmeyen pazarlar takip edilmez; collector bunları state/market_catalog.json'a
yazar ki sonradan eklenebilsin.
"""

FAMILY_LABEL = {"MS": "Maç Sonucu", "IY": "İlk Yarı", "CS": "Çifte Şans",
                "KG": "Karşılıklı Gol", "AU": "Alt/Üst"}

HALF_HINTS = ("half", "yarı", "yari", "1st", "2nd", "ikinci", "ilk")
EXCLUDE_HINTS = ("handicap", "handikap", "corner", "korner", "card", "kart",
                 "team", "takım", "takim", "home", "away", "ev sahibi",
                 "deplasman", "player", "oyuncu", "exact", "skor", "range",
                 "aralık", "odd", "even", "tek", "çift", "minute", "dakika")


def _has(name, words):
    return any(w in name for w in words)


def family_of(t, st, sov, name, outcomes):
    """-> (family, line) veya None"""
    n = (name or "").lower()
    outs = {o.strip().lower() for o in outcomes}
    first_half = _has(n, ("1. yarı", "1.yarı", "1st half", "first half", "ilk yarı", "ilk yari", "half time", "half-time", "ht "))
    excluded = _has(n, EXCLUDE_HINTS)

    if outs == {"1", "0", "2"}:
        if sov not in (None, "", "0"):
            return None                              # handikaplı
        if st == 1:
            return ("MS", None)
        if n and first_half and not excluded:
            return ("IY", None)
        if n and not _has(n, HALF_HINTS) and not excluded and _has(n, ("result", "sonuc", "sonuç", "1x2", "match")):
            return ("MS", None)
        return None

    if outs == {"var", "yok"}:
        if n and _has(n, ("both", "karşılıklı", "karsilikli", "btts", "gg")) and not _has(n, HALF_HINTS) and not excluded:
            return ("KG", None)
        if not n and st == 89:
            return ("KG", None)
        return None

    if outs == {"alt", "üst"}:
        try:
            line = float(str(sov).replace(",", "."))
        except (TypeError, ValueError):
            return None
        if n:
            if _has(n, ("total", "alt/üst", "alt / üst", "toplam", "gol")) and not _has(n, HALF_HINTS) and not excluded:
                return ("AU", line)
            return None
        if st in (60, 101):
            return ("AU", line)
        return None

    if len(outs) == 3 and all(" ve " in o or "-" in o for o in outs):
        if n and _has(n, ("double", "çifte", "cifte")) and not _has(n, HALF_HINTS):
            return ("CS", None)
        if not n and st == 92:
            return ("CS", None)
        return None
    return None


def canon_outcome(family, outcome_name):
    o = outcome_name.strip().lower().replace(" ve ", "-")
    if family == "CS":
        return {"1-0": "1X", "0-1": "1X", "1-2": "12", "2-1": "12",
                "0-2": "X2", "2-0": "X2"}.get(o, o.upper())
    if family in ("MS", "IY"):
        return {"0": "X"}.get(o, o)
    if family == "AU":
        return "Üst" if o.startswith("ü") else "Alt"
    if family == "KG":
        return "Var" if o == "var" else "Yok"
    return o


def market_key(family, line):
    return f"AU{line:g}" if family == "AU" else family


def market_label(mkey):
    if mkey.startswith("AU"):
        return f"Alt/Üst {mkey[2:]}"
    return FAMILY_LABEL.get(mkey, mkey)


def pick_label(mkey, outcome):
    if mkey in ("MS", "IY"):
        return f"{'İY' if mkey == 'IY' else 'MS'} {outcome}"
    if mkey == "CS":
        return f"ÇŞ {outcome}"
    if mkey == "KG":
        return f"KG {outcome}"
    if mkey.startswith("AU"):
        return f"{mkey[2:]} {outcome}"
    return f"{mkey} {outcome}"


def settle(mkey, outcome, ft, ht=None):
    """ft=(ev, dep). -> True/False, None = sonuçlandırılamaz (ör. İY skoru yok)."""
    if ft is None:
        return None
    h, a = ft
    res = "1" if h > a else ("2" if a > h else "X")
    if mkey == "MS":
        return outcome == res
    if mkey == "IY":
        if ht is None:
            return None
        hh, ha = ht
        r = "1" if hh > ha else ("2" if ha > hh else "X")
        return outcome == r
    if mkey == "CS":
        return res in {"1X": "1X", "12": "12", "X2": "X2"}.get(outcome, "")
    if mkey == "KG":
        both = h > 0 and a > 0
        return both if outcome == "Var" else not both
    if mkey.startswith("AU"):
        line = float(mkey[2:])
        tot = h + a
        if tot == line:
            return None                          # tam çizgi: iade
        return (tot > line) if outcome == "Üst" else (tot < line)
    return None
