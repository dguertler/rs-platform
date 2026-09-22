"""
check_exits.py — Verkaufssignale für Watchlist-Titel

Läuft täglich nach den RS-Updates. Für jeden Titel auf der Watchlist, der ein
offenes Breakout-Signal hat, wird die Ausstiegsregel des Backtests geprüft:

  Signal am Tagesschluss, wenn
    • die Tagesstruktur (Stand Vortag) NICHT gebrochen ist
      UND der Schlusskurs unter dem letzten Swing-Tief liegt, oder
    • der Schlusskurs unter dem Stopp liegt
  Ausführung zur Eröffnung des Folgetages.

Das ist dieselbe Regel wie in frontend/backtest_logic.js (simulateTrades) —
bewusst ohne Rückdatierung, damit Live-Verhalten und Backtest übereinstimmen.

Zustand:
  data/watchlist.json     — vom Nutzer gepflegt (Ticker-Liste)
  data/open_signals.json  — von diesem Skript geführt (offene Positionen)

ENV: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO
     TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (optional)
"""
import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from gws_core import _find_swing_points, _gws_core, swing_low_stop

_REPO = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_REPO, "data")

WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")
STATE_FILE = os.path.join(DATA_DIR, "open_signals.json")
SIGNALS_FILE = os.path.join(DATA_DIR, "signals.json")

# Quelle → RS-Datei. Das Feld `source` in signals.json zeigt hierauf.
SOURCE_FILES = {
    "QQQ": "rs_full.json",
    "SPX": "rs_sp500.json",
    "DAX": "rs_dax.json",
    "SC600": "rs_smallcap.json",
}

MIN_BARS = 30        # wie analyzeStructure in backtest_logic.js
STOP_BUFFER = 0.99   # Stopp einen Tick unter das Swing-Tief


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
    }


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
                market[ticker] = {"ohlcv": rows, "source": source}
    return market


def save_state(state):
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)


# ── Einstieg aus dem gemeldeten Signal ableiten ───────────────────────────────

def derive_entry(ohlcv, signal_date):
    """Einstieg = Eröffnung des Folgetages, Stopp = letztes Swing-Tief × 0,99.
    Beides genau so wie im Backtest, damit die Mail zum getesteten Verhalten passt."""
    entry_bar = next((b for b in ohlcv if b["d"] > signal_date), None)
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

def find_exit(ohlcv, position, last_checked):
    """Erster Ausstiegstag nach last_checked. Gibt None zurück, solange keiner vorliegt."""
    for i, day in enumerate(ohlcv):
        if day["d"] < position["entry_date"]:
            continue
        if last_checked and day["d"] <= last_checked:
            continue

        reason = None
        struct = daily_structure(ohlcv[:i])
        if struct and not struct["broken"]:
            lows = struct["swing_lows"]
            if lows and day["c"] < lows[-1]["price"]:
                reason = "Strukturbruch"
        if reason is None and day["c"] < position["stop_price"]:
            reason = "Stopp"
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
    return None


# ── Benachrichtigung ──────────────────────────────────────────────────────────

def build_email_html(exits):
    rows = []
    for e in exits:
        gain = (e["exit_price"] / e["entry_price"] - 1) * 100
        color = "#4ade80" if gain >= 0 else "#f87171"
        rows.append(f"""
  <div style="margin:0 0 16px;padding:14px;background:#0f172a;
              border:1px solid #1e293b;border-left:4px solid {color};border-radius:8px">
    <div style="font-size:15px;font-weight:bold;color:#e2e8f0;margin-bottom:8px">
      {e['ticker']} <span style="font-size:11px;color:#64748b">({e['source']})</span>
      <span style="float:right;color:{color}">{gain:+.1f} %</span>
    </div>
    <div style="font-size:12px;color:#94a3b8;line-height:1.7">
      Grund: <strong style="color:#e2e8f0">{e['reason']}</strong><br>
      Einstieg: {e['entry_date']} zu {e['entry_price']:.2f}<br>
      Signal am {e['signal_date']}, Ausführung {e['exit_date']} zu {e['exit_price']:.2f}<br>
      Stopp lag bei {e['stop_price']:.2f}
    </div>
  </div>""")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="background:#060b14;color:#e2e8f0;font-family:monospace;
             padding:24px;max-width:780px;margin:0 auto">
  <h2 style="color:#fbbf24;margin:0 0 4px">Verkaufssignal &mdash; {datetime.now().strftime('%d.%m.%Y')}</h2>
  <p style="color:#64748b;margin:0 0 20px;font-size:12px">
    {len(exits)} Titel deiner Watchlist haben die Ausstiegsregel ausgelöst.
  </p>
  {''.join(rows)}
  <p style="color:#475569;font-size:11px;margin-top:24px;line-height:1.6">
    Regel wie im Backtest: Tagesstruktur gebrochen und Schluss unter dem letzten
    Swing-Tief, oder Schluss unter dem Stopp. Ausführung zur Eröffnung des
    Folgetages. Die Meldung bezieht sich auf das Signal des Systems, nicht auf
    deinen tatsächlichen Depotbestand.
  </p>
</body></html>"""


def send_email(exits):
    host = os.environ.get("SMTP_HOST", "")
    user = os.environ.get("SMTP_USER", "")
    pw = os.environ.get("SMTP_PASS", "")
    to = os.environ.get("ALERT_EMAIL_TO", "")
    if not all([host, user, pw, to]):
        print("  SMTP nicht konfiguriert – Mail übersprungen")
        return
    msg = MIMEText(build_email_html(exits), "html", "utf-8")
    msg["Subject"] = f"Verkaufssignal {datetime.now().strftime('%d.%m.%Y')}: {len(exits)} Titel"
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(user, pw)
        smtp.send_message(msg)
    print(f"  Mail an {to} verschickt")


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def collect_new_positions(watchlist, market, signals, positions, closed):
    """Neue 4H-Breakouts für Watchlist-Titel als offene Position aufnehmen.

    Übersprungen wird ein Signal, wenn es bereits abgeschlossen wurde (`closed`)
    oder wenn es noch keinen Folgetag gibt — der Einstiegskurs ist die Eröffnung
    des Folgetages, den liefert erst der nächste Datenlauf.
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
        if not entry:
            pending.append(f"{key} ({latest['signal_date']})")
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


def main():
    watchlist = load_watchlist()
    if not watchlist:
        print("Watchlist leer oder nicht vorhanden – nichts zu prüfen.")
        return

    market = load_market_data()
    signals = load_json(SIGNALS_FILE, {})
    state = load_json(STATE_FILE, {"positions": {}, "closed": {}})
    positions = state.get("positions", {})
    closed = state.get("closed", {})

    # Titel, die von der Watchlist genommen wurden, nicht weiter verfolgen
    for key in [k for k in positions if k not in watchlist]:
        positions.pop(key)

    opened, pending = collect_new_positions(watchlist, market, signals, positions, closed)
    for key in opened:
        p = positions[key]
        print(f"  neu verfolgt: {key} ab {p['entry_date']} zu {p['entry_price']:.2f}, "
              f"Stopp {p['stop_price']:.2f}")
    for label in pending:
        print(f"  Signal ohne Folgetag, wartet auf den nächsten Kurstag: {label}")

    exits = []
    for key, position in list(positions.items()):
        data = market.get(position["ticker"])
        if not data:
            continue
        hit = find_exit(data["ohlcv"], position, position.get("last_checked"))
        if hit and hit["pending"]:
            # Signal steht, Ausführungskurs gibt es erst morgen — nächsten Lauf abwarten
            print(f"  {key}: Signal am {hit['signal_date']}, Ausführung folgt")
            continue
        if not hit:
            position["last_checked"] = data["ohlcv"][-1]["d"]
            position.pop("adopted", None)
            continue

        positions.pop(key)
        closed[key] = position["signal_date"]
        if position.get("adopted"):
            # Beim ersten Erfassen liegt der Ausstieg oft schon Wochen zurück —
            # das ist keine Handlungsaufforderung und wird nicht gemeldet.
            print(f"  {key}: Signal bereits abgeschlossen ({hit['signal_date']}), nicht gemeldet")
            continue
        exits.append({**position, **hit})

    state["positions"] = positions
    state["closed"] = closed
    save_state(state)

    print(f"Watchlist {len(watchlist)} Titel | offene Signale {len(positions)} | Ausstiege {len(exits)}")
    if exits:
        for e in exits:
            print(f"  EXIT {e['ticker']}: {e['reason']} am {e['signal_date']} "
                  f"→ {e['exit_date']} zu {e['exit_price']:.2f}")
        send_email(exits)


if __name__ == "__main__":
    main()
