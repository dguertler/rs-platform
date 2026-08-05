"""
check_earnings_premarket.py — Live-Vorbörsen-/Intraday-Alert für Earnings-Beats
======================================================================================
Ergänzt check_earnings.py (Schlusskurs-zu-Schlusskurs, geprüft am Folgetag) um einen
schnellen Live-Kurs-Check: für Ticker, die laut data/earnings_calendar.json HEUTE
(BMO) oder am letzten Handelstag davor (AMC gestern Abend) Zahlen vorlegen, wird der
aktuelle Vorbörsen-/Session-Kurs gegen den letzten regulären Schlusskurs verglichen —
nicht erst der fertige Tagesschluss vom Folgetag.

Kriterien identisch zu check_earnings.py:
  - |Kurssprung| >= MIN_PRICE_JUMP (5%)
  - EPS-Surprise >= MIN_EPS_SURPRISE (10%)
  - Umsatz YoY nicht stark negativ (< -5%)

Wird von earnings_alert_premarket.yml nur aufgerufen, wenn
check_earnings_premarket_gate.py mindestens einen Kandidaten-Ticker gefunden hat
(Ticker-Liste kommt per --tickers, kommagetrennt).

Dedupe: .earnings_premarket_state/alerted.json (Liste "TICKER|DATUM") wird vom
Workflow per rollierendem Cache (restore-keys mit Tages-Präfix) über den Tag hinweg
mitgeführt, damit derselbe Ticker nicht bei jedem 15-Min-Tick erneut gemailt wird.
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import yfinance as yf

from check_earnings import (
    MIN_PRICE_JUMP, MIN_EPS_SURPRISE,
    get_earnings_surprise, send_earnings_email,
)

STATE_PATH = Path(".earnings_premarket_state/alerted.json")

MARKET_SOURCES = [
    ("data/rs_full.json",     "QQQ"),
    ("data/rs_dax.json",      "DAX"),
    ("data/rs_sp500.json",    "SPX"),
    ("data/rs_smallcap.json", "SC600"),
]


def load_state() -> set:
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_state(alerted: set):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(sorted(alerted)), encoding="utf-8")


def find_ticker_meta(ticker: str):
    """(source_label, score) aus den vier Markt-JSONs, oder (None, None)."""
    for path, label in MARKET_SOURCES:
        if not os.path.exists(path):
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        for entry in data.get("data", []):
            if entry.get("ticker") == ticker:
                return label, entry.get("score", 0)
    return None, None


def live_jump(ticker: str):
    """Aktueller Vorbörsen-/Session-Kurs vs. letzter reg. Schlusskurs.
    Rückgabe (pct_change, live_price, prev_close) oder (None, None, None)."""
    try:
        info = yf.Ticker(ticker).get_info()
    except Exception as e:
        print(f"  {ticker}: Live-Kurs-Abruf fehlgeschlagen — {e}")
        return None, None, None

    prev_close = info.get("regularMarketPreviousClose")
    live_price = (
        info.get("preMarketPrice")
        or info.get("postMarketPrice")
        or info.get("regularMarketPrice")
    )
    if not prev_close or not live_price:
        return None, None, None
    return live_price / prev_close - 1, live_price, prev_close


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", default="", help="Kommagetrennte Kandidaten-Ticker")
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        print("Keine Kandidaten übergeben — nichts zu tun.")
        return

    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = os.environ.get("SMTP_PORT", "587")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    to_addr   = os.environ.get("ALERT_EMAIL_TO", "")

    cal = json.loads(Path("data/earnings_calendar.json").read_text(encoding="utf-8"))
    next_earnings = cal.get("next_earnings", {})

    already_alerted = load_state()
    today_str = date.today().isoformat()

    new_alerts = []
    for ticker in tickers:
        state_key = f"{ticker}|{next_earnings.get(ticker, today_str)}"
        if state_key in already_alerted:
            print(f"  {ticker}: bereits heute gemeldet — übersprungen")
            continue

        jump, live_price, prev_close = live_jump(ticker)
        if jump is None:
            print(f"  {ticker}: kein Live-Kurs verfügbar")
            continue

        print(f"  {ticker}: Live-Kurs {live_price:.2f} vs. Vortagsschluss {prev_close:.2f} "
              f"({jump*100:+.1f}%)")

        if abs(jump) < MIN_PRICE_JUMP:
            continue

        target_date = next_earnings.get(ticker, today_str)
        earnings = get_earnings_surprise(ticker, target_date)
        if earnings is None:
            print(f"    → keine Earnings-Kennzahlen gefunden (noch nicht bei Yahoo?)")
            continue

        surprise = earnings["surprise_pct"]
        rev_yoy  = earnings.get("revenue_growth_yoy")
        print(f"    → Surprise: {surprise:.1f}%")

        if surprise < MIN_EPS_SURPRISE:
            print(f"    → unter EPS-Schwelle ({MIN_EPS_SURPRISE}%) — übersprungen")
            continue
        if rev_yoy is not None and rev_yoy < -0.05:
            print(f"    → Umsatz YoY stark negativ ({rev_yoy*100:.1f}%) — übersprungen")
            continue

        source, score = find_ticker_meta(ticker)
        print(f"  ✓ LIVE-ALERT: {ticker} ({source})  Sprung={jump*100:.1f}%  Surprise={surprise:.1f}%")

        alert = {
            "ticker":             ticker,
            "score":              score,
            "source":             source or "QQQ",
            "jump_pct":           jump,
            "surprise_pct":       surprise,
            "eps_estimate":       earnings["eps_estimate"],
            "eps_actual":         earnings["eps_actual"],
            "revenue_growth_yoy": rev_yoy,
            "charts":             [],
            "news":               {"specific": [], "general": []},
        }
        new_alerts.append(alert)
        already_alerted.add(state_key)

    if new_alerts:
        if all([smtp_host, smtp_user, smtp_pass, to_addr]):
            send_earnings_email(new_alerts, smtp_host, smtp_port, smtp_user, smtp_pass,
                                 to_addr, subject_prefix="⚡ Live ")
        else:
            print("SMTP nicht konfiguriert — Live-Mail übersprungen")

        tg_token   = os.environ.get("TELEGRAM_TOKEN", "")
        tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if tg_token:
            from telegram_handler import send_earnings_telegram, resolve_recipients
            tg_recipients = resolve_recipients(tg_chat_id)
            if tg_recipients:
                for a in new_alerts:
                    send_earnings_telegram(tg_token, tg_recipients, a)
    else:
        print("Keine neuen Live-Alerts.")

    save_state(already_alerted)


if __name__ == "__main__":
    main()
