"""
check_exits.py — Verkäufe, Stopp-Verschiebungen und Modell-Depot

Wird von check_alerts.py im täglichen Breakout-Lauf aufgerufen (eine
gemeinsame Mail für Käufe, Verkäufe und SL-Verschiebungen); direkt aufgerufen
prüft es nur die Watchlist und meldet Verkäufe/SL-Verschiebungen allein.

Ausstiegsregel wie in frontend/backtest_logic.js (simulateTrades):
  Signal am Tagesschluss, wenn
    • Trendumkehr: der Schlusskurs liegt unter dem Trendumkehr-Tief (Stand
      Vortag) — dem letzten Swing-Tief vor dem letzten Swing-Hoch, oder
    • der Schlusskurs unter dem Stopp liegt, oder
    • Zeitstopp (seit 12.10.2026 abgeschaltet, TIME_STOP_ENABLED): 10 Handelstage nach dem Einstieg liegt der Schluss nicht
      mindestens 5 % über dem Einstiegskurs
  Ausführung zur Eröffnung des Folgetages.

Wirksamer Stopp (SL) für den nächsten Tag = höherer Wert aus Stopp und
Trendumkehr-Tief — ändert er sich, wird das als SL-Verschiebung gemeldet.

Zustand:
  data/watchlist.json     — vom Nutzer gepflegt (Ticker-Liste)
  data/open_signals.json  — Signale der Watchlist-Titel (Verkauf/SL per Mail)
  data/live_depot.json    — Modell-Depot: höchstens 10 Positionen; entscheidet
                            in der Breakout-Mail über „Kauf" oder „kein Kauf"

ENV: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO
     TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (optional)
"""
import json
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from gws_core import _find_swing_points, _gws_core, swing_low_stop

_REPO = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_REPO, "data")

WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")
STATE_FILE = os.path.join(DATA_DIR, "open_signals.json")
DEPOT_FILE = os.path.join(DATA_DIR, "live_depot.json")
SIGNALS_FILE = os.path.join(DATA_DIR, "signals.json")
EARNINGS_FILE = os.path.join(DATA_DIR, "earnings_history.json")
CALENDAR_FILE = os.path.join(DATA_DIR, "earnings_calendar.json")

# Quelle → RS-Datei. Das Feld `source` in signals.json zeigt hierauf.
SOURCE_FILES = {
    "QQQ": "rs_full.json",
    "SPX": "rs_sp500.json",
    "SC600": "rs_smallcap.json",
}

MIN_BARS = 30        # wie analyzeStructure in backtest_logic.js
STOP_BUFFER = 0.99   # Stopp einen Tick unter das Swing-Tief
# Einstands-Stopp wie breakEven in backtest_logic.js (seit 13.10.2026): Schließt ein Tag mindestens
# BREAK_EVEN_R × R über dem Einstieg (R = Einstieg − Stopp), gilt ab dem nächsten Tag der Einstieg
# als Stopp; ein Schluss darunter → Verkauf zur Eröffnung (Grund „Einstand“)
BREAK_EVEN_R = 2
TIME_STOP_ENABLED = False   # wie timeStopEnabled in backtest_logic.js (abgeschaltet seit 12.10.2026)
TIME_STOP_DAYS = 10  # Zeitstopp wie TIME_STOP_DAYS / TIME_STOP_MIN in backtest_logic.js
TIME_STOP_MIN = 0.05
MAX_POSITIONS = 10   # Modell-Depot wie backtest_history/portfolio.js
EARNINGS_BLOCK_DAYS = 4   # wie EARNINGS_BLOCK_DAYS in backtest_logic.js
DEPOT_SINCE = "2026-09-22"   # ab hier nur noch 4H-Auslöser verschickt (Rekonstruktion)


# ── Struktur (Port von analyzeStructure aus backtest_logic.js) ────────────────

def daily_structure(ohlcv):
    """Gebrochen = GWS-Hoch vorhanden UND überschritten. Bewusst ohne den
    Trend-Fallback und ohne Mindestabstand aus check_alerts.py — die
    Ausstiegsregel muss exakt der Backtest-Engine entsprechen."""
    if not ohlcv or len(ohlcv) < MIN_BARS:
        return None
    n = len(ohlcv)
    highs = [c["h"] for c in ohlcv]
    lows = [c["l"] for c in ohlcv]
    closes = [c["c"] for c in ohlcv]
    swing_highs, swing_lows = _find_swing_points(highs, lows, n)
    gws_high, breakout_idx = _gws_core(swing_highs, swing_lows, closes, n, min_margin=0.0)
    return {
        "broken": gws_high is not None and breakout_idx is not None,
        "swing_lows": swing_lows[-6:],
        "swing_highs": swing_highs[-6:],
    }


def trend_low(struct):
    """Trendumkehr-Tief wie trendLowOf in backtest_logic.js: das letzte Swing-Tief
    vor dem letzten Swing-Hoch — das Tief, aus dem das letzte Hoch entstanden ist
    (Referenz-Trade AVGO: Tief 25.06.2024, Schluss darunter am 17.07.2024)."""
    if not struct or not struct["swing_highs"]:
        return None
    last_high = struct["swing_highs"][-1]["idx"]
    lows = [l for l in struct["swing_lows"] if l["idx"] < last_high]
    return lows[-1]["price"] if lows else None


def entry_trend_low(ohlcv, struct, entry_date):
    """Trendumkehr-Tief für eine offene Position wie entryTrendLow in backtest_logic.js (seit
    13.10.2026): War das Tief schon vor dem Kauf per Schluss unterschritten (verbraucht), gilt bis
    zum nächsten Swing-Hoch das tiefste Tief seit diesem Bruch bis vor den Kauftag (CDNS 29.06.2026:
    375,94 vom 12.06. am 24./25.06. gebrochen → 358,76 vom 26.06.)."""
    low = trend_low(struct)
    if low is None or not entry_date:
        return low
    last_high = struct["swing_highs"][-1]["idx"]
    e = next((i for i, b in enumerate(ohlcv) if b["d"] >= entry_date), None)
    if e is None or last_high >= e:
        return low
    first = next((i for i in range(last_high + 1, e) if ohlcv[i]["c"] < low), None)
    return low if first is None else min(b["l"] for b in ohlcv[first:e])


# ── Earnings (wie nextEarnings/earningsSellDay in backtest_logic.js) ──────────

def load_earnings():
    """ticker → [[YYYY-MM-DD, 'bmo'|'amc'|'unk'], …] aus earnings_history.json;
    fehlt ein Ticker dort, zählt der nächste Termin aus earnings_calendar.json
    (Uhrzeit unbekannt)."""
    hist = load_json(EARNINGS_FILE, {}).get("tickers", {})
    cal = load_json(CALENDAR_FILE, {}).get("next_earnings", {})
    out = {t: rows for t, rows in hist.items()}
    for t, d in cal.items():
        rows = out.setdefault(t, [])
        if all(r[0] != d for r in rows):
            rows.append([d, "unk"])
            rows.sort()
    return out


def next_earnings(earnings, day):
    return next((e for e in earnings or [] if e[0] >= day), None)


def earnings_blocks_entry(earnings, entry_day):
    """Kein Kauf, wenn die nächsten Zahlen weniger als 4 Kalendertage entfernt sind."""
    e = next_earnings(earnings, entry_day)
    if not e:
        return None
    days = (datetime.strptime(e[0], "%Y-%m-%d") - datetime.strptime(entry_day, "%Y-%m-%d")).days
    return e if days < EARNINGS_BLOCK_DAYS else None


EARNINGS_DROP_MIN = 0.05


def earnings_drop_block(earnings, ohlcv, signal_day):
    """Kurs fällt nach den Zahlen (wie earningsDropBlocks in frontend/backtest_logic.js):
    Schließt der Reaktionstag (nach Börsenschluss: nächster Handelstag, sonst der Tag der
    Zahlen) mindestens 5 % unter dem Schluss davor, gibt es keinen Kauf, bis Daily danach
    einmal rot war oder ein Schluss über dem Kurs vor den Zahlen liegt (AVGO: Zahlen
    31.08.2023 nach Börsenschluss, 01.09. −5,4 % → kein Kauf am 14.09.). Rückgabe: der
    Termin [Datum, Zeit], der sperrt, sonst None. ohlcv: Tageskerzen, mindestens bis vor
    signal_day."""
    from check_alerts import analyze_daily_structure   # spät: check_alerts importiert dieses Modul
    e = None
    for x in earnings or []:
        if x[0] >= signal_day:
            break
        e = x
    if not e:
        return None
    r = next((i for i, b in enumerate(ohlcv)
              if (b["d"] > e[0] if e[1] == "amc" else b["d"] >= e[0])), -1)
    if r < 1 or ohlcv[r]["d"] >= signal_day or ohlcv[r]["c"] > ohlcv[r - 1]["c"] * (1 - EARNINGS_DROP_MIN):
        return None
    sig = next((i for i, b in enumerate(ohlcv) if b["d"] >= signal_day), len(ohlcv))
    if any(ohlcv[i]["c"] > ohlcv[r - 1]["c"] for i in range(r + 1, sig)):
        return None
    for i in range(r, sig):
        st = analyze_daily_structure(ohlcv[:i + 1])
        if not (st and st["broken"]):
            return None
    return e


def earnings_sell_day(ohlcv, e):
    """Verkaufstag vor den Zahlen: nach Börsenschluss derselbe Tag, sonst der
    Handelstag davor (bei Zahlen vor Börsenbeginn bzw. unbekannter Uhrzeit).
    Liegt der Vortag noch nicht in den Kursen, wird der Werktag davor geschätzt."""
    if e[1] == "amc":
        return e[0]
    prev = [b["d"] for b in ohlcv if b["d"] < e[0]]
    if prev and ohlcv[-1]["d"] >= e[0]:
        return prev[-1]
    d = datetime.strptime(e[0], "%Y-%m-%d") - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def h4_close_14(h4, day):
    """Schluss der 14-Uhr-Kerze (Block 10–14/14–18 Uhr Berlin wie h4Block)."""
    for b in h4 or []:
        if b["d"][:10] == day and 10 < int(b["d"][11:13]) <= 14:
            return b["c"]
    return None


# ── Dateien ───────────────────────────────────────────────────────────────────

def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_watchlist():
    raw = load_json(WATCHLIST_FILE, {})
    tickers = raw.get("tickers", []) if isinstance(raw, dict) else raw
    return {str(t).upper().strip() for t in tickers if str(t).strip()}


def load_market_data():
    """ticker → {'ohlcv': [...], 'source': 'QQQ'} aus allen RS-Dateien."""
    market = {}
    for source, filename in SOURCE_FILES.items():
        payload = load_json(os.path.join(DATA_DIR, filename), {})
        for entry in payload.get("data", []):
            ticker = entry.get("ticker")
            rows = entry.get("ohlcv") or []
            if ticker and rows and ticker not in market:
                market[ticker] = {"ohlcv": rows, "source": source, "ohlcv_4h": entry.get("ohlcv_4h") or []}
    return market


def save_state(state):
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)


# ── Einstieg aus dem gemeldeten Signal ableiten ───────────────────────────────

def derive_entry(ohlcv, signal_date):
    """Einstieg = Eröffnung am Alert-Tag, Stopp = letztes Swing-Tief × 0,99.

    signal_date ist der Versandtag (signals.json): Die Mail geht vor Börsenbeginn
    raus und beruht auf dem Schluss des Vortages — gekauft wird also zur
    Eröffnung genau dieses Tages, wie in der Live-Bilanz (live_alerts/) und im
    Backtest (Eröffnung nach dem Signaltag)."""
    entry_bar = next((b for b in ohlcv if b["d"] >= signal_date), None)
    if not entry_bar:
        return None

    before = [b for b in ohlcv if b["d"] < entry_bar["d"]]
    if len(before) < 3:
        return None

    stop = swing_low_stop(before, STOP_BUFFER)
    if stop is None or stop >= entry_bar["o"]:
        return None      # Stopp über dem Einstieg — kein sinnvoller Trade
    return {"entry_date": entry_bar["d"], "entry_price": entry_bar["o"], "stop_price": stop}


# ── Ausstieg ──────────────────────────────────────────────────────────────────

def effective_stop(ohlcv, position, i):
    """Stopp für den Tagesschluss von ohlcv[i]: ursprünglicher Stopp oder — sobald ein Schluss seit
    dem Einstieg (vor Tag i) mindestens BREAK_EVEN_R × R darüber lag — der Einstieg (Einstand)."""
    entry, stop = position.get("entry_price"), position.get("stop_price")
    if not BREAK_EVEN_R or entry is None or stop is None or entry <= stop:
        return stop, False
    target = entry + BREAK_EVEN_R * (entry - stop)
    hit = any(b["d"] >= position["entry_date"] and b["c"] >= target for b in ohlcv[:i])
    return (entry, True) if hit else (stop, False)


def find_exit(ohlcv, position, last_checked, earnings=None, h4=None, today=None):
    """Erster Ausstiegstag nach last_checked. Gibt None zurück, solange keiner vorliegt.

    earnings: Termine des Titels — Verkauf zum Schluss der 14-Uhr-Kerze am letzten
    Handelstag vor den nächsten Zahlen. Liegt dieser Tag nach dem letzten Kurs, aber
    spätestens heute (today), wird der Verkauf schon als anstehend gemeldet."""
    entry_idx = next((k for k, b in enumerate(ohlcv) if b["d"] >= position["entry_date"]), None)
    # Erste Zahlen, deren Verkaufstag noch nicht geprüft wurde — ein Termin, der schon vor
    # last_checked lag, löst nicht nachträglich aus (MRVL 12.10.2026: Zahlen 27.08., Position erst
    # ab 09.10. verfolgt → fälschlich „Earnings“ verkauft)
    e, sell_day, after = None, None, position["entry_date"]
    while True:
        e = next_earnings(earnings, after)
        sell_day = earnings_sell_day(ohlcv, e) if e else None
        if not (sell_day and last_checked and sell_day <= last_checked):
            break
        after = (datetime.strptime(e[0], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    if sell_day and sell_day < position["entry_date"]:
        sell_day = None
    when = {"amc": "nach Börsenschluss", "bmo": "vor Börsenbeginn"}.get(e[1], "Uhrzeit offen") if e else ""
    for i, day in enumerate(ohlcv):
        if day["d"] < position["entry_date"]:
            continue
        if last_checked and day["d"] <= last_checked:
            continue
        if sell_day and day["d"] >= sell_day:
            return {"signal_date": day["d"], "exit_date": day["d"], "reason": f"Earnings am {e[0]} ({when})",
                    "exit_price": h4_close_14(h4, day["d"]) or day["c"], "pending": False,
                    "earnings": True}

        reason = None
        if (TIME_STOP_ENABLED and entry_idx is not None and i - entry_idx == TIME_STOP_DAYS
                and day["c"] < position["entry_price"] * (1 + TIME_STOP_MIN)):
            reason = "Zeitstopp"
        low = entry_trend_low(ohlcv, daily_structure(ohlcv[:i]), position["entry_date"]) if reason is None else None
        if low is not None and day["c"] < low:
            reason = "Trendumkehr"
        stop, at_entry = effective_stop(ohlcv, position, i)
        if reason is None and day["c"] < stop:
            reason = "Einstand" if at_entry else "Stopp"
        if reason is None:
            continue

        nxt = next((b for b in ohlcv if b["d"] > day["d"]), None)
        return {
            "signal_date": day["d"],
            "exit_date": nxt["d"] if nxt else day["d"],
            "exit_price": nxt["o"] if nxt else day["c"],
            "reason": reason,
            "pending": nxt is None,   # Ausführung erst am nächsten Handelstag
        }
    if sell_day and ohlcv and ohlcv[-1]["d"] < sell_day <= (today or "0000"):
        return {"signal_date": sell_day, "exit_date": sell_day, "reason": f"Earnings am {e[0]} ({when})",
                "exit_price": ohlcv[-1]["c"], "pending": True, "earnings": True}
    return None


def exit_level(ohlcv, stop_price, entry_date=None):
    """Wirksamer Stopp für den nächsten Handelstag: (Kurs, Art).

    Ein Schluss unter dem Trendumkehr-Tief löst ebenfalls aus — es gilt der
    höhere der beiden Werte (vor dem Kauf verbrauchtes Tief: entry_trend_low)."""
    low = entry_trend_low(ohlcv, daily_structure(ohlcv), entry_date)
    if low is not None and low > stop_price:
        return round(low, 2), "Trendumkehr-Tief"
    return round(stop_price, 2), "Stopp"


def time_stop_info(ohlcv, position):
    """Prüftag des Zeitstopps (10. Handelstag nach dem Einstieg) und Mindestkurs."""
    idx = next((k for k, b in enumerate(ohlcv) if b["d"] >= position["entry_date"]), None)
    need = round(position["entry_price"] * (1 + TIME_STOP_MIN), 2)
    if idx is None:
        return None, need
    k = idx + TIME_STOP_DAYS
    return (ohlcv[k]["d"] if k < len(ohlcv) else None), need


# ── Benachrichtigung (nur bei direktem Aufruf; sonst Teil der Breakout-Mail) ──

def exit_rows_html(exits):
    rows = []
    for e in exits:
        gain = (e["exit_price"] / e["entry_price"] - 1) * 100
        color = "#4ade80" if gain >= 0 else "#f87171"
        rows.append(f"""
  <div style="margin:0 0 16px;padding:14px;background:#0f172a;
              border:1px solid #1e293b;border-left:4px solid {color};border-radius:8px">
    <div style="font-size:15px;font-weight:bold;color:#e2e8f0;margin-bottom:8px">
      VERKAUF {e['ticker']} <span style="font-size:11px;color:#64748b">({e['source']})</span>
      <span style="float:right;color:{color}">{gain:+.1f} %</span>
    </div>
    <div style="font-size:12px;color:#94a3b8;line-height:1.7">
      Grund: <strong style="color:#e2e8f0">{e['reason']}</strong><br>
      Einstieg: {e['entry_date']} zu {e['entry_price']:.2f}<br>
      {f"Verkauf am {e['exit_date']} zum Schluss der 14-Uhr-Kerze (18:00)" if e.get('earnings')
       else f"Signal am {e['signal_date']}, Verkauf zur Eröffnung {e['exit_date']}"}
      ({'Kurs folgt' if e.get('pending') else f"{e['exit_price']:.2f}"})
    </div>
  </div>""")
    return "".join(rows)


def sl_rows_html(moves):
    rows = []
    for m in moves:
        up = m["new"] > m["old"]
        color = "#4ade80" if up else "#fbbf24"
        ts = ("" if not TIME_STOP_ENABLED else
              f" &middot; Zeitstopp-Prüfung am {m['time_stop_date']}: Schluss mind. {m['time_stop_need']:.2f}"
              if m.get("time_stop_pending") else " &middot; Zeitstopp bestanden")
        rows.append(f"""
  <div style="margin:0 0 16px;padding:14px;background:#0f172a;
              border:1px solid #1e293b;border-left:4px solid {color};border-radius:8px">
    <div style="font-size:15px;font-weight:bold;color:#e2e8f0;margin-bottom:8px">
      SL {m['ticker']} <span style="font-size:11px;color:#64748b">({m['source']})</span>
      <span style="float:right;color:{color}">{m['old']:.2f} &rarr; {m['new']:.2f}</span>
    </div>
    <div style="font-size:12px;color:#94a3b8;line-height:1.7">
      Neuer Stopp: <strong style="color:#e2e8f0">{m['new']:.2f}</strong> ({m['kind']}) &middot;
      letzter Schluss {m['last_close']:.2f}<br>
      Einstieg: {m['entry_date']} zu {m['entry_price']:.2f}{ts}
    </div>
  </div>""")
    return "".join(rows)


def build_email_html(exits, moves=()):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="background:#060b14;color:#e2e8f0;font-family:monospace;
             padding:24px;max-width:780px;margin:0 auto">
  <h2 style="color:#fbbf24;margin:0 0 4px">Verkäufe &amp; Stopps &mdash; {datetime.now().strftime('%d.%m.%Y')}</h2>
  <p style="color:#64748b;margin:0 0 20px;font-size:12px">Watchlist-Titel</p>
  {exit_rows_html(exits)}{sl_rows_html(moves)}
  <p style="color:#475569;font-size:11px;margin-top:24px;line-height:1.6">
    Regel wie im Backtest: Schluss unter dem Stopp bzw. unter dem Tief, aus dem
    das letzte Hoch entstanden ist (Trendumkehr) — Verkauf zur Eröffnung des
    Folgetages —, oder vor Earnings zum Schluss der 14-Uhr-Kerze am Tag davor.
    Die Meldung bezieht sich auf das Signal des Systems, nicht auf deinen
    tatsächlichen Depotbestand.
  </p>
</body></html>"""


def send_email(exits, moves=()):
    host = os.environ.get("SMTP_HOST", "")
    user = os.environ.get("SMTP_USER", "")
    pw = os.environ.get("SMTP_PASS", "")
    to = os.environ.get("ALERT_EMAIL_TO", "")
    if not all([host, user, pw, to]):
        print("  SMTP nicht konfiguriert – Mail übersprungen")
        return
    msg = MIMEText(build_email_html(exits, moves), "html", "utf-8")
    parts = ([f"{len(exits)} Verkauf/Verkäufe"] if exits else []) + ([f"{len(moves)} SL-Verschiebung(en)"] if moves else [])
    msg["Subject"] = f"Verkäufe & Stopps {datetime.now().strftime('%d.%m.%Y')}: {', '.join(parts)}"
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(user, pw)
        smtp.send_message(msg)
    print(f"  Mail an {to} verschickt")


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def collect_new_positions(watchlist, market, signals, positions, closed, earnings=None):
    """Neue 4H-Breakouts für Watchlist-Titel als offene Position aufnehmen.

    Übersprungen wird ein Signal, wenn es bereits abgeschlossen wurde (`closed`)
    oder wenn der Alert-Tag noch keine Kerze hat — der Einstiegskurs ist die
    Eröffnung des Alert-Tages, die liefert erst der nächste Datenlauf.
    """
    opened, pending = [], []
    for ticker, entries in signals.items():
        key = ticker.upper()
        if key not in watchlist or key in positions or ticker not in market:
            continue
        fourh = [s for s in entries if s.get("trigger_tf") == "4h"]
        if not fourh:
            continue
        latest = max(fourh, key=lambda s: s["signal_date"])
        if closed.get(key) == latest["signal_date"]:
            continue
        entry = derive_entry(market[ticker]["ohlcv"], latest["signal_date"])
        if entry and latest.get("entry_price"):     # 4H-Prüfjob: Kauf im Tagesverlauf
            entry["entry_price"] = latest["entry_price"]
        if not entry:
            pending.append(f"{key} ({latest['signal_date']})")
            continue
        if earnings_blocks_entry((earnings or {}).get(ticker), entry["entry_date"]):
            closed[key] = latest["signal_date"]      # kein Kauf so kurz vor den Zahlen
            continue
        if earnings_drop_block((earnings or {}).get(ticker), market[ticker]["ohlcv"], latest["signal_date"]):
            closed[key] = latest["signal_date"]      # kein Kauf: Kurs fiel nach den Zahlen
            continue
        positions[key] = {
            "ticker": ticker,
            "source": latest.get("source") or market[ticker]["source"],
            "signal_date": latest["signal_date"],
            "last_checked": None,
            "adopted": True,          # erster Lauf: Altbestand nicht melden
            **entry,
        }
        opened.append(key)
    return opened, pending


def _sl_move(key, position, ohlcv):
    """Neuen wirksamen Stopp berechnen; Änderung gegenüber dem gemeldeten Stand zurückgeben."""
    stop, at_entry = effective_stop(ohlcv, position, len(ohlcv))
    level, kind = exit_level(ohlcv, stop, position.get("entry_date"))
    if at_entry and kind == "Stopp":
        kind = "Einstand"
    prev = position.get("sl_level")
    position["sl_level"] = level
    if prev is None or abs(level - prev) < 0.005:
        return None
    ts_date, need = time_stop_info(ohlcv, position)
    return {"ticker": key, "source": position.get("source", ""), "old": prev, "new": level,
            "kind": kind, "last_close": ohlcv[-1]["c"], "entry_date": position["entry_date"],
            "entry_price": position["entry_price"], "time_stop_date": ts_date or "—",
            "time_stop_need": need, "time_stop_pending": ts_date is None or ts_date > ohlcv[-1]["d"]}


def process_watchlist(market=None, signals=None):
    """Watchlist-Signale fortschreiben. Gibt (exits, sl_moves) für die Mail zurück."""
    watchlist = load_watchlist()
    if not watchlist:
        print("Watchlist leer oder nicht vorhanden – nichts zu prüfen.")
        return [], []
    market = market if market is not None else load_market_data()
    signals = signals if signals is not None else load_json(SIGNALS_FILE, {})
    state = load_json(STATE_FILE, {"positions": {}, "closed": {}})
    positions = state.get("positions", {})
    closed = state.get("closed", {})

    # Titel, die von der Watchlist genommen wurden, nicht weiter verfolgen
    for key in [k for k in positions if k not in watchlist]:
        positions.pop(key)

    earnings = load_earnings()
    today = datetime.now().strftime("%Y-%m-%d")
    opened, pending = collect_new_positions(watchlist, market, signals, positions, closed, earnings)
    for key in opened:
        p = positions[key]
        print(f"  neu verfolgt: {key} ab {p['entry_date']} zu {p['entry_price']:.2f}, "
              f"Stopp {p['stop_price']:.2f}")
    for label in pending:
        print(f"  Signal ohne Folgetag, wartet auf den nächsten Kurstag: {label}")

    exits, moves = [], []
    for key, position in list(positions.items()):
        data = market.get(position["ticker"])
        if not data:
            continue
        hit = find_exit(data["ohlcv"], position, position.get("last_checked"),
                        earnings.get(position["ticker"]), data.get("ohlcv_4h"), today)
        if hit and hit["pending"] and not position.get("adopted"):
            # Signal steht, Verkauf zur nächsten Eröffnung — jetzt melden, Position
            # erst nach der Ausführung schließen (dann ohne zweite Meldung)
            if position.get("exit_reported") != hit["signal_date"]:
                exits.append({**position, **hit})
                position["exit_reported"] = hit["signal_date"]
            continue
        if hit and not hit["pending"]:
            positions.pop(key)
            closed[key] = position["signal_date"]
            if position.get("adopted"):
                # Beim ersten Erfassen liegt der Ausstieg oft schon Wochen zurück —
                # das ist keine Handlungsaufforderung und wird nicht gemeldet.
                print(f"  {key}: Signal bereits abgeschlossen ({hit['signal_date']}), nicht gemeldet")
            elif position.get("exit_reported") != hit["signal_date"]:
                exits.append({**position, **hit})
            continue
        position["last_checked"] = data["ohlcv"][-1]["d"]
        adopted = position.pop("adopted", None)
        move = _sl_move(key, position, data["ohlcv"])
        if move and not adopted:
            moves.append(move)

    state["positions"] = positions
    state["closed"] = closed
    save_state(state)
    print(f"Watchlist {len(watchlist)} Titel | offene Signale {len(positions)} | "
          f"Verkäufe {len(exits)} | SL-Verschiebungen {len(moves)}")
    return exits, moves


# ── Modell-Depot (höchstens 10 Positionen) ────────────────────────────────────

def _close_finished(positions, market, until=None, earnings=None):
    """Positionen mit Ausstiegssignal entfernen (auch wenn der Verkauf erst zur
    nächsten Eröffnung stattfindet — der Platz ist dann für Käufe am selben Tag frei)."""
    freed = []
    for key, p in list(positions.items()):
        data = market.get(p["ticker"])
        if not data:
            continue
        if p.get("entry_price") is None:
            entry = derive_entry(data["ohlcv"], p["signal_date"])
            if not entry:
                if any(b["d"] >= p["signal_date"] for b in data["ohlcv"]):
                    # Folgetag da, aber kein gültiger Einstieg (Stopp über dem Kurs) — kein Trade
                    positions.pop(key)
                continue
            p.update(entry)
        hit = find_exit(data["ohlcv"], p, None, (earnings or {}).get(p["ticker"]), data.get("ohlcv_4h"),
                        datetime.now().strftime("%Y-%m-%d"))
        if hit and (until is None or hit["exit_date"] <= until):
            positions.pop(key)
            freed.append({**p, **hit})
    return freed


def rebuild_depot(signals, market):
    """Depot aus den seit DEPOT_SINCE verschickten 4H-Breakouts nachspielen."""
    sent = sorted(((s["signal_date"], t) for t, lst in signals.items() for s in lst
                   if s.get("in_top20") and s.get("trigger_tf") == "4h" and s["signal_date"] >= DEPOT_SINCE),
                  key=lambda x: x[0])
    positions = {}
    earnings = load_earnings()
    for date, ticker in sent:
        data = market.get(ticker)
        if not data or ticker.upper() in positions:
            continue
        entry = derive_entry(data["ohlcv"], date)
        _close_finished(positions, market, until=entry["entry_date"] if entry else date, earnings=earnings)
        if not entry and any(b["d"] >= date for b in data["ohlcv"]):
            continue          # kein gültiger Einstieg (Stopp über dem Kurs)
        if earnings_blocks_entry(earnings.get(ticker), entry["entry_date"] if entry else date):
            continue          # kein Kauf so kurz vor den Zahlen
        if earnings_drop_block(earnings.get(ticker), data["ohlcv"], date):
            continue          # kein Kauf: Kurs fiel nach den Zahlen
        if len(positions) < MAX_POSITIONS:
            positions[ticker.upper()] = {"ticker": ticker, "source": data["source"], "signal_date": date,
                                         **(entry or {"entry_price": None})}
    _close_finished(positions, market, earnings=earnings)
    return {"positions": positions, "rebuilt_from": DEPOT_SINCE}


def depot_decisions(alerts, signals, market, today):
    """Kauf / kein Kauf je Breakout (Reihenfolge = RS-Rang) und Depot fortschreiben."""
    depot = load_json(DEPOT_FILE, None) or rebuild_depot(signals, market)
    positions = depot.setdefault("positions", {})
    earnings = load_earnings()
    for f in _close_finished(positions, market, earnings=earnings):
        print(f"  Depot: {f['ticker']} raus ({f['reason']}, Signal {f['signal_date']})")
    for a in sorted(alerts, key=lambda x: x.get("rank") or 99):
        key = a["ticker"].upper()
        blocked = earnings_blocks_entry(earnings.get(a["ticker"]), today)
        ohlcv = (market.get(a["ticker"]) or {}).get("ohlcv") or []
        dropped = earnings_drop_block(earnings.get(a["ticker"]), ohlcv, today)
        if key in positions:
            a["decision"] = "bereits im Depot"
        elif blocked:
            a["decision"] = f"Kein Kauf – Earnings am {datetime.strptime(blocked[0], '%Y-%m-%d'):%d.%m.%Y}"
        elif dropped:
            a["decision"] = (f"Kein Kauf – Kurs fiel nach den Earnings vom "
                             f"{datetime.strptime(dropped[0], '%Y-%m-%d'):%d.%m.%Y}")
        elif len(positions) < MAX_POSITIONS:
            a["decision"] = "Kauf"
            positions[key] = {"ticker": a["ticker"], "source": a.get("source", ""), "signal_date": today,
                              "entry_price": None, "stop_price": a.get("stop_price")}
            if a.get("entry_price"):      # 4H-Prüfjob: Kauf sofort, nicht erst zur Tageseröffnung
                positions[key].update(entry_date=today, entry_price=a["entry_price"],
                                      entry_time=a.get("entry_time"))
        else:
            a["decision"] = f"Kein Kauf – {MAX_POSITIONS} von {MAX_POSITIONS} Plätzen belegt"
        a["depot_count"] = len(positions)
    depot["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(DEPOT_FILE, "w") as f:
        json.dump(depot, f, indent=1, ensure_ascii=False)
    return depot


def main():
    exits, moves = process_watchlist()
    for e in exits:
        print(f"  VERKAUF {e['ticker']}: {e['reason']} am {e['signal_date']} → {e['exit_date']}")
    for m in moves:
        print(f"  SL {m['ticker']}: {m['old']:.2f} → {m['new']:.2f} ({m['kind']})")
    if exits or moves:
        send_email(exits, moves)


if __name__ == "__main__":
    main()
