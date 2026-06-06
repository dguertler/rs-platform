# Instagram-Generator — AI Alpha Selections

Erzeugt automatisiert Slides (PNG) + Caption für Instagram aus den
vorhandenen Repo-Daten. **Lädt nichts hoch** — du prüfst alles und postest
manuell. Faceless, markenkonsistent, mit Pflicht-Disclaimer.

## Installation

```bash
pip install -r instagram/requirements.txt
```

## Nutzung

**Wochenmodus (Hauptweg)** — aus den gespeicherten Daten (`instagram/data/`):

```bash
# 1) aktuellen Zertifikatswert der KW speichern
python3 -m instagram.add_week --kw 22 --value 145.30
# 2) Wochenpost erzeugen (Carousel 4:5 + Reel 9:16)
python3 -m instagram.generate --kw 22
```

Erzeugt Hook, Performance vs. NASDAQ, Kennzahlen, Wochen-Historie,
Stärkste Positionen, **Aktie der Woche** (rotierend) und CTA + `caption.txt`.
NASDAQ/Alpha/Historie werden automatisch berechnet.
→ Ablauf, Regeln & Datenpflege: **`instagram/PROMPT.md`**.

**Analyse-Post** — aus einer fertigen KI-Analyse (`analyses/TICKER.md`):

```bash
# Firmenlogo einmalig ablegen: instagram/assets/logos/<TICKER>.png (transparent)
python3 -m instagram.generate --analysis AMD
```

Erzeugt ein Carousel (Cover mit Firmenlogo + Verdict, Gesamteinschätzung,
Szenarien 12–18 M mit Wahrscheinlichkeiten, Langfrist 3–5 J, Geschäftsmodell,
Szenarien erklärt, Profi-Fazit) + SEO-Caption. **Ohne** aktuellen Kurs und
**ohne** GWS-Ampel/Breakout. Details: **`instagram/PROMPT.md`** (Abschnitt
„Zweiter Post-Typ: AKTIEN-ANALYSE").

**Alternativ** — vollständig manueller Wochenreport ohne Stores:

```bash
python3 -m instagram.generate --report instagram/reports/KW21.example.json
```

Output: `out/instagram/<DATUM>_KW<NN>/{carousel,reel}/NN_*.png` + `caption.txt`.

> ⚖️ **wikifolio-Regeln** (Trennung Musterdepot/Zertifikat, keine ISIN, kein
> wikifolio-Logo, Pflicht-Disclaimer) sind in `PROMPT.md` dokumentiert und im
> Generator umgesetzt.

## Wikifolio-Performance

Die echte Equity-Kurve liegt **nicht** im Repo. Zwei Wege:

1. **Automatisch** (lokal, offenes Netz):
   ```bash
   python3 -m instagram.fetch_wikifolio --symbol DEIN_SYMBOL
   ```
   → schreibt `data/wikifolio_performance.json`.
   *In der Claude-Cloud blockt wikifolio.com (403), daher dort nicht testbar.*

2. **Manuell**: `data/wikifolio_performance.example.json` nach
   `data/wikifolio_performance.json` kopieren und Werte eintragen.

Fehlt die Datei, rendert der Generator mit klar markierten **BEISPIELDATEN**.
Die NASDAQ-100-Vergleichslinie kommt real aus `data/rs_full.json` (QQQ).

## Aufbau

| Datei | Zweck |
|---|---|
| `theme.py` | Farben, Fonts, Canvas-Größen, Disclaimer-Texte |
| `data.py` | Lädt Signale, RS/OHLCV, Benchmark, Performance |
| `render.py` | Zeichnet die einzelnen Slides (matplotlib) |
| `generate.py` | CLI: baut Slide-Set + Caption |
| `fetch_wikifolio.py` | Holt die Equity-Kurve (best effort) |

## Slide-Reihenfolge

1. Hook (große Performance-Zahl)
2. Performance vs. NASDAQ-100
3. Kennzahlen (Rendite, Outperformance, Signale, Titel)
4…n. Einzelne Trade-Signale (Chart + Marker)
letzte. CTA + Risikohinweis

## Anpassen

- **Design**: Farben/Fonts in `theme.py`.
- **Mehr/weniger Signale**: `--signals N`.
- **Reel-Video**: die 9:16-Frames lassen sich später mit ffmpeg zu einem
  animierten Reel zusammensetzen (separater Schritt).
