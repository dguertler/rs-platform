# RS-Platform — Claude Code Anweisungen

## Git-Regeln

- Alle Änderungen direkt auf `master` pushen (kein Feature-Branch, kein PR, außer explizit gewünscht)
- **Cloud-/Web-Sessions mit vorgegebenem Arbeits-Branch** (z. B. `claude/...`):
  auf den Arbeits-Branch **und zusätzlich direkt auf `master`** pushen (Fast-Forward,
  kein PR nötig) — beide Refs bleiben synchron
- **Bei jedem Commit den Git-Hash im Chat ausgeben**, z.B.: `[a3f92c1] Commit-Nachricht`
- Commit-Messages auf Deutsch oder Englisch, klar und beschreibend

## Doku-Pflege-Regeln (gilt für ALLE MD-Dateien im Repo)

- Neue Vorgaben des Nutzers sofort in der zuständigen MD-Datei festhalten —
  dabei die veraltete Aussage **ersetzen**, nicht als neue „Runde"/Notiz anhängen
- Jede Regel lebt an genau **einer** Stelle (Single Source of Truth):
  - Analyse-Prompt → `analyses/PROMPT.md` (keine Kopie im Code)
  - Instagram-Workflow & -Regeln → `instagram/PROMPT.md`
  - Instagram-Projektstand, Daten-Snapshot, Code-Karte → `instagram/CONTEXT.md`
- **Keine manuell gepflegten Zähler/Stände** in der Doku (z. B. „X von Y
  Analysen") — solche Werte bei Bedarf per Skript/grep frisch ermitteln
- Zahlen in Doku-Snapshots stammen immer aus den JSON-Dateien
  (`instagram/data/*.json`) — die JSONs sind führend, nie umgekehrt

## Analyse-Workflow

Wenn der Nutzer schreibt `Analysiere TICKER`:

1. **Fundamentaldaten laden** aus `data/fundamentals.json`:
   ```python
   import json
   fund = json.load(open('data/fundamentals.json'))['tickers']['TICKER']
   ```

   **Earnings-Check (PFLICHT, autark vor jeder Analyse):** Prüfen, ob TICKER
   in den letzten 7 Tagen einen Earnings-Termin hatte (z. B. via
   `yfinance.Ticker(TICKER).calendar` oder bekanntes Berichtsdatum). Falls ja:
   Wochen-Cache aus `data/fundamentals.json` NICHT unverändert verwenden.
   - **Bevorzugt:** `fetch_fundamentals(TICKER)` aus `generate_rating.py` für
     einen erzwungenen Live-Fetch dieses einen Tickers aufrufen.
   - **Fallback, falls yfinance/Yahoo Finance netzwerkseitig blockiert ist**
     (z. B. 403 auf Proxy-Ebene in Cloud-Sessions): Per WebSearch die
     Earnings-Kennzahlen recherchieren (EPS actual/estimate/surprise,
     Umsatz YoY, Guidance) und diese **Key Facts zuerst im Chat ausgeben**,
     bevor die Aktienanalyse folgt. Die recherchierten Werte fließen
     qualitativ in die Analyse ein (Cache-Fundamentaldaten gelten dafür als
     ggf. veraltet).
   Grund: Der automatische 5 %-Preis-Gap-Trigger in `load_fundamentals()`
   greift nur bei starker Kursreaktion — ein Earnings-Beat/-Miss kann
   Fundamentaldaten (Revenue, Margen, EPS) spürbar verändern, ohne dass der
   Kurs um mehr als 5 % reagiert.

2. **RS-Daten laden** aus dem passenden RS-JSON:
   ```python
   # NASDAQ-100 → data/rs_full.json
   # S&P 500   → data/rs_sp500.json
   # Smallcap  → data/rs_smallcap.json
   rs = next(e for e in json.load(open('data/rs_full.json'))['data'] if e['ticker']=='TICKER')
   rs_score  = rs['score']        # Feldname ist 'score', NICHT 'rs_score'
   rs_rank   = rs['prev_rank']    # Feldname ist 'prev_rank', NICHT 'rank'
   windows   = rs['windows']
   gws       = rs.get('gws')      # None bei Smallcaps — dann gws_smallcap-Dict übergeben:
   # gws = gws or {"weekly": False, "daily": False, "h4": False, "points": 0, "signal_type": "Smallcap"}
   ```

   **Zombie-Stock-Filter (PFLICHT vor jeder Analyse):**
   ```python
   fund = json.load(open('data/fundamentals.json'))['tickers']['TICKER']
   market_cap = fund.get('marketCap') or 0
   if market_cap < 5_000_000:
       print(f"ZOMBIE-STOCK: {TICKER} MCap ${market_cap:,.0f} — keine Analyse, kein write_rating().")
       # Stattdessen nur kurze Chat-Ausgabe: "TICKER — AVOID (Zombie-Stock, MCap < $5M)"
       # STOP — nicht weiter analysieren
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

8. **Chat-Ausgabe:** Nur die Zusammenfassungs-Tabelle ausgeben — KEINE vollständige Analyse im Chat. Format:

   | Ticker | Name | Kurs | RS | Verdict | Ratings | Handlungsempfehlung |
   |--------|------|------|-----|---------|---------|----------------------|
   | TICKER | Name | $X | Score (Rank) | **VERDICT** | Q· G· V· K· · EV ±X% | **Empfehlung** |

   **Handlungsempfehlung (PFLICHT bei jeder Analyse-Ausgabe im Chat)** — klare
   Kauf-/Nicht-Kauf-Aussage, mechanisch aus `verdict` und `funnel_veto.decision`
   (`data/ratings/index.json`) abgeleitet, nicht neu interpretiert:
   - `funnel_veto.decision == "VETO"` → **Nicht kaufen**
   - `verdict == "AVOID"` → **Nicht kaufen**
   - `verdict == "WATCH"` → **Nicht kaufen (nur beobachten)**
   - `verdict == "HOLD"` → **Halten, kein Neukauf**
   - `verdict == "BUY"` und `funnel_veto.decision == "REDUCE"` → **Kaufen (reduzierte Position)**
   - `verdict == "BUY"` und `funnel_veto.decision` in (`"PASS"`, fehlt) → **Kaufen (volle Position)**

   Bei REDUCE/VETO den Grund aus `funnel_veto.reason` in einem Halbsatz
   ergänzen (z. B. „wegen Kundenkonzentration"). Gilt für Einzelanalysen
   genauso wie für Batch-Ausgaben (siehe „Batch-Empfehlung" unten).

### Automatik-Modus: `aktienanalyse` ohne Ticker

Schreibt der Nutzer nur `aktienanalyse` (ohne Ticker-Liste), werden die zu
analysierenden Ticker automatisch aus dem zuletzt per Mail/Telegram
versendeten Breakout-Alert ermittelt statt manuell übergeben:

1. **Letzten Alert-Batch laden** aus `data/last_breakout_alerts.json`
   (`sent_at`, `alerts`-Liste mit `ticker`/`source`; wird von
   `stock_alerts.yml` — Breakout-Alarm 2→3 Punkte, Di–Sa 02:00 UTC via
   `check_alerts.py` — bei jedem Lauf überschrieben und enthält daher immer
   nur die zuletzt an Mail+Telegram verschickte Charge, keinen Verlauf).
2. **Letzten Scan-Zeitpunkt** aus `analyses/.last_stock_alert_scan` lesen
   (ISO-Timestamp). Fehlt die Datei (erster Lauf): den aktuellen Batch trotzdem
   verarbeiten.
3. `sent_at` des Batches <= gespeichertem Scan-Zeitpunkt → kurze Chat-Meldung
   „Keine neuen Breakout-Alerts seit TIMESTAMP." und STOP, kein
   Dateizugriff/Commit.
4. Ticker aus `alerts` extrahieren (Feld `ticker`), nach Ticker
   deduplizieren. Feld `source` gibt direkt die passende RS-Quelle vor
   (`QQQ`→`data/rs_full.json`, `SPX`→`data/rs_sp500.json` — siehe
   Schritt 2 oben).
5. **Für jeden Ticker automatisch, ohne Rückfrage, direkt im selben Lauf**
   den vollständigen Analyse-Workflow oben (Schritte 1–8: Fundamentaldaten,
   Earnings-Check, RS-Daten, Zombie-Stock-Filter, Prompt, Analyse
   generieren, `write_rating()`, committen) durchführen — inkl.
   Git-Hash-Ausgabe je Ticker.
6. `analyses/.last_stock_alert_scan` mit dem `sent_at` des verarbeiteten
   Batches überschreiben, committen und auf `master` pushen.
7. **Am Ende** die Zusammenfassungstabelle (Schritt 8 oben) für alle Ticker
   des Batches zusammen ausgeben, plus die EV/Risiko-Tabelle wie im
   Abschnitt „Batch-Empfehlung" unten beschrieben (gilt automatisch, sobald
   mehr als ein Ticker im Batch war).

## Datenquellen

| Datei | Inhalt | Aktualisierung |
|---|---|---|
| `data/fundamentals.json` | yfinance-Fundamentals (476+ Ticker) | Jeden Montag automatisch |
| `data/rs_full.json` | NASDAQ-100 RS-Scores + OHLCV | Täglich automatisch |
| `data/rs_sp500.json` | S&P 500 RS-Scores + OHLCV | Täglich automatisch |
| `data/earnings_alerts_log.json` | Event-Log gesendeter Earnings-Alerts (Global-Scan + Live-Premarket), je Eintrag mit `trigger` (`eps-beat` / `kursreaktion`) und `eps_distorted` — Basis für den `earning`/`earningsanalyse`-Automatik-Modus | Laufend automatisch (bei jedem Alert) |
| `data/last_breakout_alerts.json` | Zuletzt per Mail+Telegram versendete Breakout-Alert-Charge (2→3 Punkte) — Basis für den `aktienanalyse`-Automatik-Modus, wird bei jedem Lauf überschrieben (kein Verlauf) | Di–Sa 02:00 UTC automatisch (`stock_alerts.yml`) |
| `data/watchlist.json` | Beobachtete Ticker — Grundlage der Verkaufssignale. Führende Quelle; die Watchlist-Seite liest sie beim Laden und schreibt Änderungen direkt zurück (GitHub-Contents-API, Token pro Gerät im localStorage). Ohne Token bleibt die Liste lokal und lässt sich über „exportieren" als Datei ablegen | Laufend über `frontend/watchlist.html` |
| `data/open_signals.json` | Offene 4H-Breakout-Signale der Watchlist-Titel inkl. Einstieg und Stopp, plus bereits abgeschlossene Signale | Di–Sa 02:30 UTC automatisch (`check_exits.yml`) |
| `data/backtest_history/ndx_membership.json` | Tagesgenaue NASDAQ-100-Zusammensetzung ab 01.02.2007 (Quelle: github.com/jmccarrell/n100tickers, MIT) — Grundlage des historischen Backtests | Bei jedem Lauf von `backtest_history.yml` |
| `data/backtest_history/ndx_results.json` | Historischer Backtest NASDAQ-100 ab 2007 (Grundsystem W+D ohne 4H, Top 20 point-in-time), je Jahr inkl. NASDAQ-Performance, Varianten inkl./exkl. nicht mehr gehandelter Aktien, plus Abgleich W+D gegen 4H auf den Live-Daten — Anzeige in `frontend/backtest_history.html` | Manuell über `backtest_history.yml` (Yahoo ist aus Cloud-Sessions gesperrt); Abgleich lokal via `node backtest_history/run_backtest.js --calibration-only` |
| `analyses/PROMPT.md` | Vollständiger System-Prompt | Manuell gepflegt |

## Batch-Empfehlung

Beispiel: `Analysiere MU ARM AMD MRVL ON`

Nach einem Analyse-Batch (mehrere Ticker in einem Rutsch) zusätzlich zur
Zusammenfassungs-Tabelle (Schritt 8 oben, inkl. Handlungsempfehlung-Spalte)
eine **EV/Risiko-Tabelle** ausgeben — exakt dieselben Werte, die danach auch
in den Index-Tabellen der Platform (`frontend/index.html`, `sp500.html`,
`smallcap.html`) erscheinen:

```
| Ticker | EV      | Risiko |
|--------|---------|--------|
| TICKER | ±X%     | Y%     |
```

Werte aus `data/ratings/index.json` nach dem Schreiben aller Analysen des
Batches auslesen (`ev_upside_pct`, `verdict`, `funnel_veto.decision`) —
**nicht** aus dem selbst geschriebenen Analysetext neu berechnen, da
`write_rating()` den EV mechanisch aus den Bull/Base/Bear-Mittelpunkten
ermittelt (einfacher Durchschnitt, nicht wahrscheinlichkeitsgewichtet) und
das die im Frontend tatsächlich angezeigte Zahl ist.

Risiko-Staffel identisch zur Frontend-Logik (`frontend/index.html`,
Abschnitt "Risiko-Staffel"): max. Verlust je Trade in % des Invests.
- `funnel_veto.decision == "VETO"` oder `verdict == "AVOID"` → **0%**
- `funnel_veto.decision == "REDUCE"` → **5%**
- `ev_upside_pct < -20` → **5%**
- `ev_upside_pct > 20` und (`funnel_veto.decision == "PASS"` oder `verdict == "BUY"`) → **15%**
- sonst → **10%**

Am Ende zusätzlich die Ø EV-Upside über alle Batch-Ticker ausgeben (wie die
"Ø EV-Upside"-Kennzahl oben in der Platform-Tabelle).

## Earnings-Kandidaten-Check (Turnaround & Momentum-Beat)

Wenn der Nutzer schreibt `Earningsanalyse TICKER1 TICKER2 ...` (Screening
nach frischen Quartalszahlen, VOR einer vollständigen `Analysiere TICKER`):
Kein `write_rating()`, keine 11-Abschnitte-Analyse — nur die Kennzahlen-
Recherche plus eine Einstufung je Ticker.

**Zwei sich gegenseitig ausschließende Kandidaten-Typen** (Kriterien in
Schritt 3 unten):

- **Turnaround** — Verlust/Krise kippt in Erholung (Referenzmuster CNC)
- **Momentum-Beat** — gesundes, stark wachsendes Geschäft übertrifft die
  Erwartungen deutlich (Referenzmuster PLTR/MSFT/AMZN Q2 2026)

Beide lösen automatisch die Vollanalyse aus. **Ein Momentum-Beat wird
niemals als Turnaround ausgewiesen** — weder in der Tabelle, noch in der
Begründung, noch in der Analyse selbst. Die Kategorien gehören in getrennte
Zeilen der Einstufungsspalte; „Turnaround" bleibt dem Verlust→Gewinn-Muster
vorbehalten.

### Automatik-Modus: `earning` / `earningsanalyse` ohne Ticker

Schreibt der Nutzer nur `earning` oder `earningsanalyse` (ohne Ticker-Liste),
werden die Ticker automatisch ermittelt statt manuell übergeben:

1. **Ticker-Pool ermitteln** aus `data/earnings_alerts_log.json`
   (`alerts`-Liste; wird laufend von `earnings_alert_global.yml` und
   `earnings_alert_premarket.yml` befüllt — der frühere RS-Morgen-Digest
   `earnings_alert.yml` läuft seit 08.08.2026 nicht mehr automatisch und
   schreibt hier nicht rein, siehe „Datenquellen"). Enthält RS-getrackte
   Ticker (Live-Vorbörse **und** Global-Scan — der schließt RS-Titel seit
   08.09.2026 nicht mehr aus, sondern dedupliziert nur noch gegen den Log)
   ebenso wie Ticker aus dem breiten Global-Universum (US/EU).
2. **Letzten Scan-Zeitpunkt** aus `analyses/earnings_screening/.last_scan`
   lesen (ISO-Timestamp UTC). Fehlt die Datei (erster Lauf): stattdessen alle
   Log-Einträge der letzten 7 Tage verwenden.
3. Nur `alerts`-Einträge mit `detected_at` > letztem Scan-Zeitpunkt nehmen,
   nach Ticker deduplizieren (ein Ticker kann mehrfach auftauchen, z. B.
   Live-Alert + späterer Global-Scan-Treffer). Keine neuen Einträge → kurze
   Chat-Meldung „Keine neuen Earnings-Meldungen seit TIMESTAMP." und STOP,
   kein Dateizugriff/Commit.
4. Für jeden gefundenen Ticker die Schritte 1–4 des manuellen Modus unten
   durchführen (Kennzahlen, RS-Score, Turnaround-/Momentum-Beat-Kriterien,
   Einstufung). Das Feld `trigger` des Log-Eintrags mitlesen:
   `"kursreaktion"` heißt, der Alert kam über die Marktreaktion und nicht über
   die EPS-Surprise — die Surprise ist dann als Signal wertlos, die
   Einstufung stützt sich auf Umsatz, Guidance und Kursreaktion.
   `eps_distorted: true` heißt, die gemeldete EPS enthält einen bilanziellen
   Einmaleffekt und darf nicht als operativer Beat zitiert werden.
5. **Ergebnis abspeichern statt nur im Chat zeigen:** Einstufungstabelle +
   Begründungen als Markdown nach `analyses/earnings_screening/<DATUM>.md`
   schreiben (DATUM = heutiges Datum, `YYYY-MM-DD`). Davor: alle Dateien in
   `analyses/earnings_screening/` löschen, deren Datum im Dateinamen älter
   als 7 Tage ist (Aufbewahrungsfrist — ältere Screenings werden automatisch
   entfernt, keine manuelle Pflege nötig).
6. `analyses/earnings_screening/.last_scan` mit dem aktuellen UTC-Zeitstempel
   überschreiben.
7. `analyses/earnings_screening/` committen und auf `master` pushen,
   Git-Hash im Chat ausgeben.
8. **Für jeden bestätigten Kandidaten ("Turnaround" oder "Momentum-Beat")
   automatisch, ohne Rückfrage, direkt im selben Lauf mit `Analysiere TICKER`
   in die volle 11-Abschnitte-Analyse inkl. `write_rating()` übergehen** —
   keine Bestätigung durch den Nutzer abwarten. "Grenzfall"/"Nein" lösen
   keine automatische Vollanalyse aus.

**Referenzmuster Turnaround: CNC Q1 2026** (`analyses/cnc.md`,
`instagram/data/earnings/CNC.json`) — Verlustquartale (Q4 25 EPS −1,16 $)
kippen in einen Blowout-Beat (Q1 26 EPS 3,37 $, +62 % Surprise), die
Kern-Kennzahl der Krise (Health Benefits Ratio) normalisiert sich sichtbar,
und das Management hebt die Jahresprognose an statt sie erneut zu kappen.
Genau diese Kombination — nicht der Beat allein — macht einen echten
Turnaround-Kandidaten aus.

**Referenzmuster Momentum-Beat: PLTR/MSFT/AMZN Q2 2026** — kerngesunde,
stark wachsende Geschäfte (Umsatz +93 % / +18 % / +20 % YoY) übertreffen die
Erwartungen und werden vom Markt mit +29,5 % / +15,5 % / +15,3 % quittiert.
Kein Verlustquartal, keine Krisen-Kennzahl, die sich normalisiert — also
ausdrücklich **kein** Turnaround, aber ein Analyse-Anlass. AMZN zeigt
zusätzlich, warum die EPS-Surprise hier nicht das Maß sein kann: bereinigt
nur +6 % (Mega-Caps steuern ihre Guidance eng), GAAP +200 % durch die
Anthropic-Neubewertung — beide Zahlen taugen nicht als Signal, die
Kursreaktion schon.

1. **Je Ticker Earnings-Kennzahlen ermitteln** — gleiche Quelle/Fallback wie
   im Earnings-Check des Analyse-Workflows (Schritt 1 oben): bevorzugt
   `fetch_fundamentals(TICKER)`, sonst WebSearch. Ermitteln: EPS
   actual/estimate/surprise %, Revenue YoY, Guidance-Richtung (angehoben /
   bestätigt / gesenkt), Kursreaktion, sowie — falls vorhanden — die
   Kern-Kennzahl, die eine vorherige Krise erklärt hätte (Marge, Quote,
   Segment-Kennzahl).
2. **RS-Score/Momentum** aus dem passenden RS-JSON ziehen (siehe Schritt 2
   des Analyse-Workflows). Ist der Ticker in keinem RS-JSON getrackt (z. B.
   Micro-Cap-Bank), das explizit als "RS-Daten nicht verfügbar" ausweisen —
   nicht schätzen oder auslassen.
3. **Einstufung prüfen** — zuerst Turnaround, dann Momentum-Beat. Ein Ticker
   kann nur eines von beidem sein: Kriterium 1 der Turnaround-Prüfung und
   Kriterium 1 der Momentum-Beat-Prüfung schließen sich gegenseitig aus.

   **A) Turnaround** (alle vier nötig):
   - Klares Verlust→Gewinn- oder Krisen→Erholungs-Muster in der jüngsten
     Historie (mind. 1 Verlust-/Krisenquartal in den letzten 12 Monaten) —
     ein Beat bei einem bereits gesunden, stetig wachsenden Geschäft erfüllt
     dies NICHT, unabhängig von der Surprise-Höhe (→ Momentum-Beat prüfen)
   - Eine identifizierbare Kern-Kennzahl normalisiert sich sichtbar
     (analog MCR bei CNC) — sonst als "kein klarer Normalisierungs-Beleg"
     kennzeichnen
   - Guidance wird angehoben statt (wie in Vorperioden) gesenkt
   - EPS-Surprise ≥ 10 % (Schwelle analog `earnings_gate.py`,
     `MIN_EPS_SURPRISE`)

   **B) Momentum-Beat** (alle vier nötig, nur wenn A) an Kriterium 1
   scheitert):
   - **Kein** Verlust-/Krisenquartal in den letzten 12 Monaten — das
     Geschäft war schon vorher gesund
   - Umsatzwachstum ≥ 15 % YoY im gemeldeten Quartal
   - Guidance wird angehoben (bloße Bestätigung reicht nicht)
   - Marktbestätigung: EPS-Surprise ≥ 10 % **oder** Kursreaktion ≥ 8 % am
     ersten Handelstag nach der Meldung (Schwelle `MIN_REACTION_JUMP` in
     `earnings_gate.py`). Bei Mega-Caps ist die Kursreaktion das belastbarere
     Signal — eine bereinigte Surprise von +6 % bei +15 % Kursreaktion (AMZN)
     ist ein Treffer, kein Fehlschlag.

   Zusätzlich für B): Der Ticker muss in einem RS-JSON getrackt sein — ohne
   RS-Score fehlt der Momentum-Beleg, dann höchstens "Grenzfall".

4. **Einstufung ausgeben** — kurze Tabelle, keine Volltext-Analyse:

   ```
   | Ticker | EPS Surprise | Kursreaktion | Guidance | Kern-Kennzahl / Wachstum | Einstufung |
   |--------|--------------|--------------|----------|--------------------------|------------|
   | TICKER | +X %         | +Y %         | ↑/→/↓    | Kurzbefund               | Turnaround / Momentum-Beat / Grenzfall / Nein |
   ```

   Danach je Ticker 1–2 Sätze Begründung, mit explizitem Verweis, welches
   Kriterium fehlt (falls "Nein"/"Grenzfall"). Bei "Momentum-Beat" den
   Begriff "Turnaround" nicht verwenden — auch nicht abschwächend
   ("Turnaround-artig", "kleiner Turnaround"). Ist die EPS-Surprise als
   `eps_distorted` markiert oder kam der Alert über `trigger: "kursreaktion"`,
   das in der Begründung benennen statt die Surprise-Zahl zu zitieren.
5. **Für jeden bestätigten Kandidaten ("Turnaround" oder "Momentum-Beat")
   automatisch, ohne Rückfrage, direkt im selben Lauf** mit
   `Analysiere TICKER` in die volle 11-Abschnitte-Analyse inkl.
   `write_rating()` übergehen — keine Bestätigung durch den Nutzer abwarten.
   "Grenzfall"/"Nein" lösen keine automatische Vollanalyse aus.

## Wikifolio Wochenrückblick (Feed-Post)

Wenn der Nutzer schreibt `Wochenrückblick KW<NN>` oder `Feed-Post KW<NN>`:

### Datenabruf und Berechnung

```python
import json

hist   = json.load(open('instagram/data/wikifolio_history.json'))['weekly']
trades = json.load(open('instagram/data/trades.json'))['closed']
holds  = json.load(open('instagram/data/holdings.json'))['positions']
ndx    = json.load(open('data/rs_full.json'))['ndx_ohlcv']

# Konstanten
START_VALUE = 98.48          # EUR, 30.03.2026
NDX_START   = 22953.38       # NDX-Close 30.03.2026

# Wochenwerte
kw_curr = next(e for e in hist if e['kw'] == NN)
kw_prev = next(e for e in hist if e['kw'] == NN - 1)
port_wk    = (kw_curr['value'] - kw_prev['value']) / kw_prev['value']
port_total = (kw_curr['value'] - START_VALUE) / START_VALUE

# NASDAQ: Freitag KW-Ende vs. Freitag Vorwoche
ndx_curr = next(e for e in ndx if e['d'] == kw_curr['date'])['c']
ndx_prev = next(e for e in ndx if e['d'] == kw_prev['date'])['c']
ndx_wk    = (ndx_curr - ndx_prev) / ndx_prev
ndx_total = (ndx_curr - NDX_START) / NDX_START

alpha_wk    = port_wk - ndx_wk
alpha_total = port_total - ndx_total
```

Wochen über NASDAQ: manuell aus Historie ermitteln (Vergleich port_wk vs. ndx_wk
je KW) oder aus `instagram/CONTEXT.md` entnehmen.

### KW24-Trades (Referenzbeispiel)

Verkäufe KW24: DDOG +7,6% (09.06.), AMAT +5,1% (09.06.), WDC +2,7% (09.06.)
Käufe KW24: GOOGL (09.06.), ASML (12.06.), SQ (12.06.)

### Textformat (Plain Text, kein Markdown)

Ausgabe **ohne Markdown-Formatierung** (keine ##, keine **, keine ---),
damit der Text direkt kopiert und in den wikifolio-Feed eingefügt werden kann.
Struktur analog KW23-Referenz:

```
📊 Wochenreport KW NN (DD.MM. – DD.MM.)

Performance:
	•	Portfoliowert: +X,X% diese Woche
	•	Gesamtrendite Wikifolio seit 30.03.: +XX,X%
	•	Nasdaq-100: +X,X% diese Woche
	•	Gesamtrendite Nasdaq seit 30.03.: +XX,X%
	•	Alpha seit 30.03.: +XX,Xpp
	•	N von M Wochen den Nasdaq geschlagen

🔥 Trades der Woche:
✅ Käufe:
→ FIRMENNAME (DD.MM.)
Kurzbeschreibung: Sektor, RS-Signal, Positionsgröße.

❌ Verkäufe:
← FIRMENNAME (DD.MM., +/-XX,X% seit Kauf)
Kurzbeschreibung: Exit-Grund (RS-Abschwächung / Stopp / Gewinn mitgenommen).

[2–3 Narrativ-Abschnitte mit Emoji-Headline, je 3–5 Sätze]

⚙️ System-Konsistenz:
Die Kombination aus: [4 Bullet-Points] …beweist sich / liefert Woche für Woche.
N von M Wochen den Nasdaq geschlagen. Gesamtrendite XX% vs. XX%.

🎯 Ausblick:
[2–3 Sätze. Immer enden mit: Keine Prognosen, keine Meinungen – nur Daten,
Disziplin und Umsetzung.]
```

### Themen-Auswahl für Narrativ-Abschnitte

Pro Woche 2–3 der folgenden Winkel wählen (je nach Datenlage):
- Outperformance in schwachem Markt (Portfolio + vs. NASDAQ -)
- Outperformance in positivem Markt (beide +, Portfolio stärker)
- Einzeltrade-Highlight (größter Gewinner / Verlierer mit System-Erklärung)
- Schnelle Stopp-Umsetzung (Roundtrip < 5 Tage mit Verlust)
- Portfolio-Rotation (mehrere Exits + Entries in kurzer Folge)
- Re-Entry (Titel der früher mit Verlust verkauft wurde und jetzt zurückkommt)

### Nach dem Erstellen

Keine Datei-Commits nötig (Feed-Text ist reines LLM-Output). Nur committen,
wenn Daten-JSONs geändert wurden (neue Trades, neue Holdings, neuer KW-Wert).

## Instagram-Workflow (AI Alpha Selection)

Markenname: **AI Alpha Selection** (Singular, kein „Selections"). Kein
@-Handle auf Slides oder in Captions — nur der Markenname. Captions sind
**Kurz-Captions** (die volle Analyse steht auf den Slides) mit **max. 5
Hashtags** (Instagram-Limit; optimal 3–5). Nach Änderungen an
`instagram/render.py`/`theme.py`: `python3 -m instagram.qa_golden` laufen
lassen (Golden-Image-Regressionstest).

### Wochenrückblick-Regeln (Samstags)

**Kurse aktualisieren:** Wenn der Wochenrückblick am **Samstag** erstellt wird,
verwenden IMMER die **Freitags-Kurse** (letzter Handelstag):
- `--date YYYY-MM-DD` mit dem **Freitag-Datum** setzen (z. B. `2026-06-12`)
- Dies ensures alle Charts (Performance, Positionen, Trades, Aktie der Woche)
  zeigen die aktuellsten verfügbaren Kurse (EUR/USD, NASDAQ-100, Positionen)
- Nicht das Samstags-Datum verwenden — das würde ältere Kurse heranziehen

**Trade-Filter:** Nur Verkäufe mit **Rendite > 5%** (positiv oder negativ) als
Chart-Slides zeigen. Kleine Trades (<5%) und aktive Positionen (noch nicht
verkauft) nicht als Trade-Slides darstellen.

### Ausgabe-Pflichten nach Instagram-Generierung

Nach jeder Generierung von Instagram-Slides (Analyse-Post, Earnings-Post,
Wochenpost, Reel) IMMER:
1. **Alle Slides einzeln anzeigen** (jeden PNG via SendUserFile ausgeben —
   kein Überspringen, keine Auswahl)
2. **ZIP-Datei ausgeben** (`carousel_TICKER.zip` bzw. entsprechendes Archiv)
3. **Reel MP4 erzeugen** und ausgeben (Wochenpost: nur Hook + Wochenvergleich +
   CTA-Slide; Analyse/Earnings: 4 Teaser-Frames)
4. **Caption ausgeben** — `caption.txt` (Carousel) direkt im Chat anzeigen;
   bei Reel zusätzlich `reel_caption.txt`. Immer zusammen mit Slides + Reel.
5. **Auf `master` pushen** (bzw. den vorgegebenen Session-Branch) — Analyse-
   und Rating-Dateien committen, Slides sind gitignored

### Logo-Suche für Instagram-Slides

Logos liegen unter `instagram/assets/logos/`. Der Generator erwartet den
Dateinamen `TICKER.png` (Großbuchstaben). Existiert diese Datei nicht, nach
dem **vollen Unternehmensnamen** und gängigen Varianten suchen (z.B.
`Marvell.png` → `MRVL.png`, `Sandisk.png` → `SNDK.png`) und eine Kopie unter
dem Ticker-Namen anlegen. Reihenfolge der Suche:
1. `TICKER.png` (exakt)
2. Firmenname (shortName aus `data/fundamentals.json`) als Dateiname
3. Erste Silbe / bekannte Kurzform des Firmennamens
Wird ein Logo gefunden und kopiert → vor der Generierung erledigen, damit
das Cover das Logo zeigt.

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
   `data/rs_*.json` berechnet — nicht eintragen. **Für den Tiefgang zusätzlich**
   (optional, empfohlen): `quarterly` (Quartals-EPS → Slide „Gewinn je Quartal")
   und `segments` (Segment-Treiber → Slide „Was den Beat getragen hat").
4. Generieren — am besten mit individueller Beat-Hook (die Hook nennt **weder
   Firmenname noch Ticker**, siehe Design-Regeln in `PROMPT.md`):
   ```bash
   python3 -m instagram.generate --earnings TICKER --headline "<Beat/Turnaround-These>"
   ```
5. Output `out/instagram/<DATUM>_EARNINGS_<TICKER>/`: `carousel/` (bis zu 14 PNG),
   `reel/` (4 PNG), `caption.txt` **und `carousel_<TICKER>.zip`** (alle Slides
   gebündelt, wie bei den Aktienanalysen) zeigen — **kein Auto-Upload**. Danach die
   `instagram/data/earnings/TICKER.json` committen (out/-Slides sind gitignored).

## Monetarisierung / Controlling

Geschäfts-/Umsatz-Ebene (5 Säulen, Content-Pipeline, KPI-Funnel) liegt in
**`controlling/`** — bei Fragen zu Umsatz, Telegram-SaaS (39 €/Monat), Affiliate,
Newsletter, Sponsoring oder Conversion-KPIs dort starten (`controlling/README.md`).
KPI-Rechner: `python3 controlling/kpi_model.py`.
