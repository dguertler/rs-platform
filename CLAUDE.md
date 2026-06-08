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
2. **PFLICHT — gelieferte Werte zuerst abspeichern** (automatisch, ohne
   Rückfrage), bevor generiert wird:
   - Zertifikatswert → `instagram/data/wikifolio_history.json`
     (`python3 -m instagram.add_week --kw <NN> --value <WERT> --date YYYY-MM-DD`)
   - Käufe → Position in `instagram/data/holdings.json` ergänzen
   - Verkäufe → Position aus `holdings.json` entfernen **und** abgeschlossenen
     Trade in `instagram/data/trades.json` (`closed`: `name` + `ret` als Dezimal)
3. Generieren (Hauptweg, dynamische Felder texten):
   `python3 -m instagram.generate --kw <NN> --hook "…" --why "…" --frage "…"`
   (Slide-Datum = Samstag der KW automatisch; ohne Flags greifen Fallbacks.)
4. Slides aus `out/` dem Nutzer zeigen — **kein Auto-Upload**, manueller Post.
5. Datendateien committen (die `out/`-Slides sind gitignored).

Hauptformat **Carousel (4:5)**; Reel-Frames (9:16) entstehen parallel.
Stories erst später (bei genügend Followern) — siehe Roadmap in PROMPT.md.

### Instagram-Analyse-Post (Einzelaktie)

Wenn der Nutzer schreibt `Instagram-Analyse TICKER` / `Analyse-Post TICKER`
(macht aus einer fertigen `analyses/TICKER.md` ein Carousel + Reel-Teaser):

1. `instagram/CONTEXT.md` (Abschnitt 11) + `PROMPT.md` (Abschnitt „Zweiter
   Post-Typ: AKTIEN-ANALYSE") lesen.
2. Generieren — am besten mit individueller Hook-Frage:
   ```bash
   python3 -m instagram.generate --analysis TICKER --headline "<Frage/These>"
   ```
3. Output `out/instagram/<DATUM>_ANALYSE_<TICKER>/`: `carousel/` (10 PNG),
   `reel/` (4 PNG), `reel.mp4`, `caption.txt`, `reel_script.txt` zeigen —
   **kein Auto-Upload**. Firmenlogo unter `instagram/assets/logos/TICKER.png`.
   Kein aktueller Kurs, keine GWS-Ampel/Breakout auf den Slides.

### Instagram-Earnings-Analyse (Quartalszahlen mit Beat)

Wenn der Nutzer schreibt `Earnings-Analyse TICKER für Insta` / `Earnings-Analyse
TICKER` (eigenständiger Post mit Fokus auf einen Earnings-Termin mit übertroffenen
Prognosen — z. B. Kandidaten aus der `check_earnings.py`-Mail: ≥ 5 % Kurssprung +
≥ 10 % EPS-Surprise + Umsatz YoY ≥ 0):

1. `instagram/CONTEXT.md` (Abschnitt 11b) + `PROMPT.md` (Abschnitt „Dritter
   Post-Typ: EARNINGS-ANALYSE") lesen.
2. **Basis-Analyse sicherstellen:** `analyses/TICKER.md` muss existieren (neues
   11-Abschnitte-Schema). Fehlt sie → zuerst „Analysiere TICKER". Älter als der
   Earnings-Termin → vorher neu generieren; danach unverändert nutzen.
3. **Earnings-Zahlen aus dem Web** holen und in `instagram/data/earnings/TICKER.json`
   schreiben (Schema in `PROMPT.md`; Pflicht: ticker, quarter, report_date, source,
   eps_actual/_estimate/_surprise_pct). Der Kurssprung wird automatisch aus
   `data/rs_*.json` berechnet — nicht eintragen.
4. Generieren — am besten mit individueller Beat-Hook:
   ```bash
   python3 -m instagram.generate --earnings TICKER --headline "<Beat/Turnaround-These>"
   ```
5. Output `out/instagram/<DATUM>_EARNINGS_<TICKER>/`: `carousel/` (≈9 PNG),
   `reel/` (4 PNG), `caption.txt` zeigen — **kein Auto-Upload**. Danach die
   `instagram/data/earnings/TICKER.json` committen (out/-Slides sind gitignored).

## Monetarisierung / Controlling

Geschäfts-/Umsatz-Ebene (5 Säulen, Content-Pipeline, KPI-Funnel) liegt in
**`controlling/`** — bei Fragen zu Umsatz, Telegram-SaaS (39 €/Monat), Affiliate,
Newsletter, Sponsoring oder Conversion-KPIs dort starten (`controlling/README.md`).
KPI-Rechner: `python3 controlling/kpi_model.py`.
