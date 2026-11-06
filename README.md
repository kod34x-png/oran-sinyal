# Oran Sinyal · Süper Lig

Süper Lig maçlarında oranı belirgin düşen tercihleri bulur, güce göre (Çok güçlü / Güçlü / Zayıf) sınıflar ve her sinyalin sonucunu **Karne**'ye işler.

## Nasıl çalışır
- `collector/` — GitHub Actions yarım saatte bir çalıştırır (`.github/workflows/collect.yml`).
  - **iddaa.com** resmi bülten (Süper Lig, ci=584): MS, İY, Çifte Şans, KG, Alt/Üst 0.5–4.5
  - **Pinnacle** (PinnWire, isteğe bağlı): `PINNWIRE_KEY` repo secret'ı eklenince devreye girer
  - **Google Haberler**: son 36 saatte sakatlık/ceza/kadro dışı haberi varsa sinyal 1 kademe düşer
  - **ESPN**: biten maçların skoru → karne
- `state/` — oran geçmişi (site göstermez)
- `web/` — Vercel'de yayınlanan site, `web/data/*.json` okur

## Eşikler
`collector/config.py` içinde. Başlangıç tahminidir; karne biriktikçe ayarlanır.

## Test
`python3 tests/test_pipeline.py` (ağ gerektirmez)

Bu araç bilgi amaçlıdır, kazanç garantisi vermez.
