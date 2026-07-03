# Umsetzungs-Prompt — RS-Platform 2.0 (weiterführen mit Claude/Sonnet)

Dieser Prompt ist dafür gedacht, 1:1 als Aufgabenstellung an eine neue
Claude-Code-Session gegeben zu werden (z. B. wenn das Fable-5-Limit erreicht
ist und mit Sonnet 5 weitergearbeitet werden soll). Er enthält den vollen
Kontext — keine Rückfragen zum "warum" nötig, nur zum "wie im Detail".

---

## Kontext (bereits erledigt — nicht neu bauen)

Auf dem Branch `claude/rs-platform-stock-selection-utpupd` existiert bereits:

1. **`STRATEGIEPLAN.md`** — vollständiges Zielkonzept: Regime-Ampel, RS 2.0,
   Setup-Qualität, Exit-Regelwerk, Backtesting-Regeln B1–B10, Roadmap Phase A/B/C.
   **Lies diese Datei zuerst vollständig** — sie ist die fachliche Grundlage
   für alles, was unten umgesetzt werden soll.
2. **`backend/v2_analysis.py`** — berechnet aus den bestehenden Markt-JSONs
   (`data/rs_full.json`, `rs_dax.json`, `rs_sp500.json`, `rs_smallcap.json`)
   und `data/fundamentals.json`:
   - Regime-Ampel (Trend vs. 200d, Marktbreite, Volatilität) → Exposure-Budget
   - RS 2.0: volatilitätsadjustierter, gewichteter RS-Score als Perzentil-Rang
     je Universum (ersetzt NICHT den alten `score` in den JSONs — läuft parallel)
   - Investierbarkeits-Filter, GWS-Setup-Punkte, Stop-Berechnung (ATR-basiert,
     kein Look-Ahead — Swing-Low muss 2 Bars bestätigt sein)
   - Funnel-Status je Ticker: `KAUFLISTE` / `KANDIDAT` / `GEFILTERT`
3. **`backend/main.py`** — neuer Endpoint `GET /api/v2/{market}` (additiv,
   direkt vor `/api/ratings` eingefügt), gecacht wie die v1-Marktendpoints.
   Kein bestehender Endpoint wurde verändert.
4. **`frontend/v2.html`** — komplett neue, eigenständige Seite. Lädt
   `/api/v2/{market}` über dasselbe `apiFetch`/Token-Muster wie die v1-Seiten,
   zeigt Regime-Karte, Funnel-Tabelle, v1-vs-2.0-Ranking-Vergleich, und die
   Regelwerke (Exit-Regeln, B1–B10) als aufklappbare `<details>`-Blöcke.
5. In **allen** bestehenden Frontend-Seiten (`index.html`, `dax.html`,
   `sp500.html`, `smallcap.html`, `alpha.html`, `watchlist.html`,
   `backtest.html`, `backtest_overview.html`, `roadmap.html`) wurde der
   Nav-Bar ein zusätzlicher Button `<a href="v2.html" ...>RS-Platform 2.0</a>`
   angehängt — sonst wurde an diesen Dateien NICHTS verändert.

**Wichtigstes Prinzip, das für den gesamten weiteren Ausbau gilt:**
Die bestehende Plattform (v1: alle Original-Seiten, `/api/rs/*`, `/api/backtest/*`,
`generate_rating.py`, die wikifolio-/Instagram-Workflows) bleibt **byte-für-byte
unverändert nutzbar**. Alles Neue entsteht in eigenen Dateien
(`v2_analysis.py`, `v2.html`, ggf. weitere `v2_*.py`/`v2_*.html`) und
zusätzlichen `/api/v2/...`-Routen. Kein bestehender Endpoint, keine bestehende
Datei wird umgebaut, umbenannt oder in ihrer Semantik verändert. Wo eine
Änderung an geteiltem Code (z. B. `backend/gws_analysis.py`) fachlich nötig
wäre, gilt: nur **erweitern** (neue Funktion daneben), nie bestehende
Funktionssignaturen ändern, die v1 verwendet.

Wenn unklar ist, ob eine geplante Änderung dieses Prinzip verletzt: NICHT
umsetzen, sondern im Chat kurz zur Bestätigung vorlegen.

---

## Auftrag — was als Nächstes zu tun ist

Arbeite die Phasen aus `STRATEGIEPLAN.md` Abschnitt 8 ("Umsetzungs-Roadmap")
der Reihe nach ab. Der aktuelle Stand deckt einen Teil von Phase A ab
(Regime-Ampel, RS 2.0 als Anzeige). Die folgenden Punkte fehlen noch:

### Phase A — Rest

1. **Volumen in die OHLCV-Exporte aufnehmen.**
   `rs_colab.py`, `dax_colab.py`, `sp500_colab_1.py`/`_2.py`,
   `smallcap_colab_1.py`/`_2.py` laden Volumen bereits über `yf.download`,
   exportieren es aber nicht in die `ohlcv`-Arrays (nur o/h/l/c). Ergänze
   `"v": round(float(vol), 0)` in `_ohlcv_from_raw` / `_ohlcv_individual` und
   den analogen Funktionen der anderen Collector-Skripte — **additiv**, d.h.
   bestehende Felder bleiben, nur `"v"` kommt dazu. Prüfe, dass kein
   bestehender Consumer (v1-Frontend, `backend/main.py`, `gws_analysis.py`)
   durch das zusätzliche Feld bricht (sollte er nicht, da JSON-Objekte gelesen
   werden und ein zusätzliches Feld nichts kaputt macht — trotzdem verifizieren).
   Danach in `backend/v2_analysis.py` die Volumen-Bestätigung ergänzen
   (Breakout-Tag-Volumen ≥ 1,5× 20-Tage-Durchschnitt) als fünftes Setup-Kriterium.

2. **Investierbarkeits-Filter schärfen:** Ø-Dollar-Volumen 20 Tage
   (aus dem neuen Volumen-Feld berechenbar) als zusätzliches Kriterium in
   `build_v2_payload()` (`v2_analysis.py`) ergänzen, gemäß den Schwellen in
   `STRATEGIEPLAN.md` Abschnitt 2 "Stufe 1".

3. **Earnings-Sperre:** Kandidaten mit Earnings-Termin in < 5 Handelstagen
   aus der Kaufliste herausnehmen (Status z. B. `EARNINGS-SPERRE`). Earnings-
   Termine sind über `yfinance` (`Ticker.calendar` / `.earnings_dates`)
   verfügbar — siehe `check_earnings.py` für ein bestehendes Beispiel, wie das
   Repo bereits mit Earnings-Terminen umgeht.

4. **Exit-Regelwerk 2.0 dokumentieren wo Trades entstehen:** Das Regelwerk aus
   `STRATEGIEPLAN.md` Abschnitt 3 ist aktuell nur in `v2.html` als Text
   sichtbar. Sobald das wikifolio danach gehandelt wird, sollte es zusätzlich
   an der Stelle verankert werden, wo Trades dokumentiert werden — vermutlich
   `instagram/CONTEXT.md` bzw. ein neuer Abschnitt in `CLAUDE.md` (nur nach
   Rücksprache mit dem Nutzer, da `CLAUDE.md`-Regeln laut Projektkonvention
   Single-Source-of-Truth sind und nicht einfach dupliziert werden dürfen).

### Phase B — Backtesting 2.0

5. **Neue Python-Portfolio-Engine** unter `backtest_v2/engine.py` (neues
   Verzeichnis, nichts an `load_backtest.py`/`backtest_logic.js` verändern).
   Muss die Regeln B1–B10 aus `STRATEGIEPLAN.md` Abschnitt 5 erfüllen:
   - Signal-Funktionen aus `backend/gws_analysis.py` und `backend/v2_analysis.py`
     **importieren und wiederverwenden**, nicht duplizieren (Regel B10).
   - Portfolio-Ebene: Positionslimits, Cash-Quote, Regime-Budget aus
     Abschnitt 4 "Portfolio-Regeln" implementieren.
   - Kein Look-Ahead (B1): Entry immer zum Open des Folgetags nach bestätigtem
     Signal; Swing-Punkte gelten erst 2 Bars nach Auftreten als bestätigt
     (siehe bereits existierende Funktion `_last_confirmed_swing_low` in
     `backend/v2_analysis.py` als Vorbild für "kein Look-Ahead").
   - Kosten (B2): 0,1 % und 0,2 % Slippage+Gebühren als zwei parallele Läufe.
   - Kennzahlen (B7): CAGR, Sharpe, Calmar, Max-DD, DD-Dauer, Exposure-Zeit,
     Profit-Factor, Trade-Anzahl, Alpha vs. Benchmark — je Regime (green/
     yellow/red) getrennt ausweisen.
   - Benchmark-Vergleich (B8): gegen Buy-and-Hold QQQ und gegen simple
     200d-Regel auf QQQ.

6. **Historische Indexmitgliedschaft** (Regel B3): `data/index_history.json`
   aus der Wikipedia-Änderungshistorie der Indizes rekonstruieren (NASDAQ-100,
   S&P 500, DAX-Zusammensetzungsänderungen sind dort tabellarisch gepflegt).
   Neues Skript `fetch_index_history.py` (analog zu `fetch_tickers.py`, das
   bereits die aktuelle Zusammensetzung lädt — hier um die Historie erweitern,
   ohne `fetch_tickers.py` selbst zu verändern; neue Funktion in neuer Datei
   oder als klar abgegrenzte Ergänzung).

7. **Out-of-Sample-Kalibrierung** (B4/B5): Trainingsfenster bis 2021,
   Validierung 2022–2026 (Pflicht: enthält den Bärenmarkt 2022 als Testfall
   für das Regime-Modul). Sensitivitätsanalyse ±30 % auf: Fenster-Gewichte
   (`RS2_WINDOWS` in `v2_analysis.py`), Perzentil-Schwellen
   (`REGIME_THRESHOLDS`), ATR-Faktor (`MAX_STOP_ATR`), Zeit-Stopp (15 Tage).
   Ergebnis in `backtest_v2/results/` versioniert ablegen (ein Report pro
   Kalibrierungslauf, z. B. `2026-07_calibration.md` + Rohdaten als JSON).

8. **`v2.html` um einen "Backtest 2.0"-Reiter erweitern**, der die
   `backtest_v2/results/`-Reports anzeigt (analog zum bestehenden Muster:
   Backend-Endpoint `/api/v2/backtest/{run_id}` liefert JSON, Frontend rendert).

### Phase C — Hybrid-Betrieb & Feedback

9. **LLM-Veto-Format** in `analyses/PROMPT.md` ergänzen (dort, nicht in
   `generate_rating.py` — Single-Source-of-Truth-Regel aus `CLAUDE.md`
   beachten): neue Pflichtsektion, die `PASS`/`REDUCE`/`VETO` mit
   Kategorie-Begründung ausgibt (siehe `STRATEGIEPLAN.md` Abschnitt 6).
   `generate_rating.py` entsprechend um das Parsen dieses neuen Feldes
   erweitern — additiv, bestehende Rating-Parser-Logik (Q/G/V/K, Score,
   Verdict) bleibt unverändert.

10. **`data/signal_journal.json`** + Logging-Hook: jedes Funnel-Signal aus
    `/api/v2/{market}` wird bei Erzeugung protokolliert (Datum, Ticker,
    RS2-Perzentil, Regime, Setup-Punkte, LLM-Entscheidung, Verdict-Score).
    Neues Skript `update_signal_journal.py` (täglich, analog zu
    `check_hidden_alpha.py`), das automatisch Folgerenditen nach 1/4/13/26
    Wochen nachträgt (rolling update bestehender Einträge).

11. **Quartalsauswertung** als neues Skript `signal_journal_report.py`, das
    die drei Fragen aus `STRATEGIEPLAN.md` Abschnitt 7 beantwortet und einen
    Report in `controlling/` ablegt (dort liegt bereits die
    Geschäfts-/Controlling-Ebene laut `CLAUDE.md`).

---

## Arbeitsweise / Leitplanken für diese Session

- **Immer zuerst lesen, dann schreiben:** `STRATEGIEPLAN.md` komplett, dann
  die konkret betroffene(n) Datei(en) mit dem Read-Tool, bevor editiert wird.
- **v1 niemals anfassen**, außer um an bestehenden Nav-Bars einen weiteren
  Menüpunkt anzuhängen (wie bereits bei `v2.html` geschehen) — auch dann nur
  rein additiv, keine bestehende Zeile verändern.
- **Kein Look-Ahead-Bias**: Bei jeder neuen Signal- oder Backtest-Funktion
  explizit prüfen, ob nur Daten verwendet werden, die zum Signalzeitpunkt
  bereits bekannt waren (Regel B1). Das ist der häufigste Fehler in diesem
  Codebereich (siehe S4 in `STRATEGIEPLAN.md` Abschnitt 1 — bereits in v1
  vorhanden, in v2 bereits behoben, bei neuem Code immer wieder prüfen).
- **Smoke-Test nach jeder Backend-Änderung:** `backend/main.py` mit
  `python3 -c "import ast; ast.parse(open('main.py').read())"` auf Syntax
  prüfen, danach mit `fastapi.testclient.TestClient` (Context-Manager wegen
  Startup-Event/DB-Init!) mindestens den neuen Endpoint UND einen
  unveränderten v1-Endpoint (`/api/rs/nasdaq`) gegentesten, um Regressionsfreiheit
  zu belegen. `DATA_DIR` env var auf das lokale `data/`-Verzeichnis setzen.
- **Git:** Alle Änderungen auf dem bestehenden Branch
  `claude/rs-platform-stock-selection-utpupd` fortführen (bzw. auf `master`,
  falls der Nutzer das inzwischen gemerged hat — im Zweifel nachfragen bzw.
  `git log`/`git branch` prüfen). Nach jedem sinnvollen Zwischenschritt
  committen (deutsch oder englisch, klar beschreibend) und den Hash im
  Chat ausgeben, z. B. `[a3f92c1] Commit-Nachricht` (Repo-Konvention aus
  `CLAUDE.md`).
- **Keine neuen Abhängigkeiten ohne Not.** Alles in `v2_analysis.py` verwendet
  bewusst nur die Python-Standardbibliothek (`math`, `statistics`) — für die
  Backtest-Engine ist `pandas`/`numpy` ok (bereits Projektabhängigkeit), aber
  nichts Neues ohne Prüfung von `requirements.txt`.
- **DATA_DIR ist konfigurierbar** (`os.getenv("DATA_DIR", ...)`) — beim
  lokalen Testen immer auf das Repo-`data/`-Verzeichnis setzen, niemals den
  Windows-Fallback-Pfad in `main.py` Zeile 42 anfassen (Produktions-Pfad des
  Nutzers).

---

## Definition of Done

Nach Abschluss der bearbeiteten Phase(n):
- Neuer Code lauffähig, gegen echte Daten smoke-getestet (siehe oben)
- `v1`-Endpoints/-Seiten nachweislich unverändert (Diff-Check: `git diff
  <alter-commit> -- frontend/index.html` etc. sollte für alle v1-Dateien
  außer dem einen Nav-Bar-Zusatz leer sein)
- `STRATEGIEPLAN.md` bei Bedarf aktualisiert, wenn sich Parameter durch die
  Kalibrierung (Phase B) geändert haben — alte Werte ersetzen, nicht
  ergänzen (Single-Source-of-Truth-Regel aus `CLAUDE.md`)
- Commit(s) gepusht, Hash im Chat ausgegeben
