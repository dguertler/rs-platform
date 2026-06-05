# RS-Platform — Claude Code Anweisungen

## Git-Regeln

- Alle Änderungen direkt auf `master` pushen (kein Feature-Branch, kein PR, außer explizit gewünscht)
- **Bei jedem Commit den Git-Hash im Chat ausgeben**, z.B.: `[a3f92c1] Commit-Nachricht`
- Commit-Messages auf Deutsch oder Englisch, klar und beschreibend

## Analyse-Workflow

Wenn der Nutzer schreibt `Analysiere TICKER`:

1. **Fundamentaldaten laden** aus `data/fundamentals.json`:
   ```python
   import json
   fund = json.load(open('data/fundamentals.json'))['tickers']['TICKER']
   ```

2. **RS-Daten laden** aus dem passenden RS-JSON:
   ```python
   # NASDAQ-100 → data/rs_full.json
   # DAX-40    → data/rs_dax.json
   # S&P 500   → data/rs_sp500.json
   rs = next(e for e in json.load(open('data/rs_full.json'))['data'] if e['ticker']=='TICKER')
   ```

3. **`analyses/PROMPT.md` lesen** — dort stehen Analyse-Struktur, Prompt und alle Formatregeln

4. **`analyses/sndk.md` als Format-Referenz** für den Aufbau der Ausgabe nutzen

5. **Analyse generieren** — Claude Code ist das LLM, kein externer API-Call

6. **Dateien schreiben** via `write_rating()` aus `generate_rating.py`:
   ```python
   import sys; sys.path.insert(0, '.')
   from generate_rating import write_rating
   write_rating(ticker, analysis_text, rs_score, windows, gws)
   ```
   Schreibt automatisch:
   - `analyses/TICKER.md` — Markdown-Analyse
   - `data/ratings/TICKER.html` — HTML für das Frontend
   - `data/ratings/index.json` — Index-Eintrag

7. **Committen und pushen**:
   ```bash
   git add analyses/TICKER.md data/ratings/TICKER.html data/ratings/index.json
   git commit -m "Analyse: TICKER — Verdict (Score X/100)"
   git push origin master
   ```
   → Git-Hash danach im Chat ausgeben

## Datenquellen

| Datei | Inhalt | Aktualisierung |
|---|---|---|
| `data/fundamentals.json` | yfinance-Fundamentals (476+ Ticker) | Jeden Montag automatisch |
| `data/rs_full.json` | NASDAQ-100 RS-Scores + OHLCV | Täglich automatisch |
| `data/rs_dax.json` | DAX-40 RS-Scores + OHLCV | Täglich automatisch |
| `data/rs_sp500.json` | S&P 500 RS-Scores + OHLCV | Täglich automatisch |
| `analyses/PROMPT.md` | Vollständiger System-Prompt | Manuell gepflegt |

## Batch-Empfehlung

Max. **5 Ticker pro Session** für optimale Kontext-Qualität.
Beispiel: `Analysiere MU ARM AMD MRVL ON`

## Instagram-Workflow (@aialphaselections)

Wenn der Nutzer einen wikifolio-Wochenreport einfügt oder schreibt
`Instagram KW<NN>` / `Erstelle Instagram-Post`:

1. **`instagram/CONTEXT.md` lesen** — zentrale Wissensdatei mit komplettem
   Projektstand (Stammdaten, Regeln, Daten-Snapshot, offene Punkte). Danach
   `instagram/PROMPT.md` für den detaillierten Ablauf und die **zwingenden
   wikifolio-Regeln** (Trennung Depot/Zertifikat, keine ISIN, kein wikifolio-Logo,
   Pflicht-Disclaimer).
2. Aus dem Feed `instagram/reports/KW<NN>.json` füllen (Schema siehe PROMPT.md).
3. Generieren: `python3 -m instagram.generate --report instagram/reports/KW<NN>.json`
4. Slides aus `out/` dem Nutzer zeigen — **kein Auto-Upload**, manueller Post.

Hauptformat **Carousel (4:5)**; Reel-Frames (9:16) entstehen parallel.
Stories erst später (bei genügend Followern) — siehe Roadmap in PROMPT.md.

**Großer Verkauf der Woche:** Wird eine Position mit |Rendite| ≥ 25 % realisiert,
ersetzt deren Kauf-/Verkauf-Chart (Kauf- **und** Verkaufskurs eingezeichnet, inkl.
realisierter Rendite) die „Aktie der Woche"; die „Weitere Positionen"-Slide entfällt
dann automatisch. Dafür den Trade in `trades.json` mit
`ticker/kw/buy_date/sell_date/buy_price_eur/sell_price_eur` anreichern.

## wikifolio News-Feed (Wochenreport-Text)

Getrennt vom Instagram-Post: der **Text-Wochenreport** für den wikifolio-News-Feed.
Wenn der Nutzer `Wochenfeed KW<NN>` / „erstelle den wikifolio-Wochenbericht" schreibt:

1. **`instagram/wikifolio_feed/FORMAT.md` lesen** — verbindliche Struktur, Ton und
   wikifolio-Regeln. Referenz-Beispiele: `KW21.md`, `KW22.md`.
2. Zahlen aus `instagram/data/` bzw. `store.compute(kw, …)` ziehen — **müssen mit den
   Instagram-Slides übereinstimmen** (gleiche Quelle, gleicher NASDAQ-Stand).
3. `instagram/wikifolio_feed/KW<NN>.md` exakt nach Schema schreiben.
4. Dem Nutzer zeigen — **kein Auto-Post**, manuelles Einstellen im wikifolio-Feed.

**NASDAQ-Korrektur:** Ist der NDX-Tageswert in der RS-JSON noch nicht enthalten oder
soll überschrieben werden, `"nasdaq_value": <NDX-Stand>` in den KW-Eintrag von
`wikifolio_history.json` setzen — greift für Wochen- **und** Gesamt-/Alpha-Rechnung.
