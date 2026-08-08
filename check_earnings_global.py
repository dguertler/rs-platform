"""
check_earnings_global.py — Earnings-Überraschung, breites US-/Europa-Universum
================================================================================
Wie check_earnings.py, aber statt nur die RS-getrackten Ticker (NASDAQ-100,
DAX, S&P 500, Smallcap 600) zu prüfen, wird ein deutlich breiteres Universum
gescannt (siehe earnings_universe.py): mehrere Tausend US-Ticker (NASDAQ Trader
Symbol-Directory) + große europäische Indizes (DAX, CAC 40, FTSE 100, IBEX 35,
FTSE MIB, SMI, AEX).

Kein Abzug historischer Kursdaten für den Scan nötig — nur die letzten ~10
Tage Schlusskurse (Batch-Download), um den Kurssprung zu berechnen. Historische
OHLCV (für Chart-Rendering) wird erst für die wenigen finalen Kandidaten
individuell nachgeladen.

Kriterien identisch zu check_earnings.py:
  - Kurssprung gestern >= MIN_PRICE_JUMP (5%)
  - EPS-Surprise >= MIN_EPS_SURPRISE (10%)
  - Umsatz YoY nicht stark negativ (< -5%)

Testmodus: UNIVERSE_LIMIT=N env var begrenzt US-/EU-Universum auf die ersten
N Ticker je Quelle (schneller Testlauf statt vollem Scan).
"""
import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "matplotlib", "lxml",
                 "deep-translator", "requests", "-q"])

import os
import sys
import time
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from earnings_universe import fetch_us_universe, fetch_europe_universe
from check_earnings import (
    MIN_PRICE_JUMP, MIN_EPS_SURPRISE, SOURCES,
    get_earnings_surprise, get_gws_price, render_chart, fetch_news,
    send_earnings_email,
)
import telegram_handler
import json


def load_rs_tracked_tickers() -> set[str]:
    """Ticker aus den vier RS-Indizes (siehe check_earnings.SOURCES) — die
    prüft bereits check_earnings.py separat, hier ausschließen um doppelte
    Alerts (zwei Mails für denselben Ticker) zu vermeiden."""
    tracked = set()
    for json_path, _source_label in SOURCES:
        if not os.path.exists(json_path):
            continue
        with open(json_path) as f:
            data = json.load(f)
        tracked.update(entry['ticker'] for entry in data.get('data', []))
    return tracked


# ── Kurs-Scan: nur letzte ~10 Tage, keine volle Historie ─────────────────────

def _jump_from_closes(closes: "pd.Series", target_date_str: str):
    closes = closes.dropna()
    if len(closes) < 2:
        return None
    dates = [d.strftime("%Y-%m-%d") for d in closes.index]
    for i in range(len(dates) - 1, 0, -1):
        if dates[i] == target_date_str:
            prev = closes.iloc[i - 1]
            if prev and prev > 0:
                return float(closes.iloc[i] / prev - 1)
            return None
    return None


def scan_price_jumps(tickers: list[str], target_date_str: str,
                      chunk_size: int = 250, pause: float = 1.0) -> list[tuple]:
    """Batch-Download der letzten 10 Tage Schlusskurse, gibt [(ticker, jump), ...]
    für alle Ticker mit Sprung >= MIN_PRICE_JUMP zurück."""
    candidates = []
    total = len(tickers)
    for start in range(0, total, chunk_size):
        chunk = tickers[start:start + chunk_size]
        print(f"  Kurs-Scan [{start + 1}-{start + len(chunk)}/{total}]...")
        try:
            raw = yf.download(chunk, period="10d", interval="1d",
                               auto_adjust=True, progress=False,
                               threads=True, group_by="ticker")
        except Exception as e:
            print(f"    Batch-Download fehlgeschlagen: {e}")
            continue
        for ticker in chunk:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if ticker not in raw.columns.get_level_values(0):
                        continue
                    closes = raw[ticker]["Close"]
                else:
                    closes = raw["Close"]
                jump = _jump_from_closes(closes, target_date_str)
            except Exception:
                continue
            if jump is not None and jump >= MIN_PRICE_JUMP:
                candidates.append((ticker, jump))
        time.sleep(pause)
    return candidates


# ── Chart-OHLCV für finale Kandidaten (nur die wenigen Treffer) ──────────────

def _individual_ohlcv(ticker: str, period: str, interval: str, n_candles: int) -> list[dict]:
    try:
        df = yf.download(ticker, period=period, interval=interval,
                          auto_adjust=True, progress=False)
        if df.empty:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna()
        result = []
        for dt, row in df.iterrows():
            result.append({
                "d": dt.strftime("%Y-%m-%d"),
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]), 2),
                "c": round(float(row["Close"]), 2),
            })
        return result[-n_candles:]
    except Exception as e:
        print(f"    OHLCV {ticker} ({interval}) fehlgeschlagen: {e}")
        return []


def _individual_ohlcv_4h(ticker: str, days: int = 60, n_candles: int = 60) -> list[dict]:
    try:
        df = yf.download(ticker, period=f"{days}d", interval="1h",
                          prepost=True, auto_adjust=True, progress=False)
        if df.empty:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna()
        df_4h = df.resample("4h").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
        ).dropna()
        result = []
        for dt, row in df_4h.iterrows():
            result.append({
                "d": dt.strftime("%Y-%m-%d %H:%M"),
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]), 2),
                "c": round(float(row["Close"]), 2),
            })
        return result[-n_candles:]
    except Exception as e:
        print(f"    4H-OHLCV {ticker} fehlgeschlagen: {e}")
        return []


def build_alert(ticker: str, source: str, jump: float, earnings: dict) -> dict:
    ohlcv_w = _individual_ohlcv(ticker, "2y", "1wk", 30)
    ohlcv_d = _individual_ohlcv(ticker, "2y", "1d", 40)
    ohlcv_4h = _individual_ohlcv_4h(ticker)

    gws_w = get_gws_price(ohlcv_w, window=1)
    gws_d = get_gws_price(ohlcv_d)
    gws_4h = get_gws_price(ohlcv_4h)

    w_b64 = render_chart(ohlcv_w, ticker, "Weekly (letzten 30 Kerzen)", gws_price=gws_w, n_candles=30)
    d_b64 = render_chart(ohlcv_d, ticker, "Daily (letzten 40 Kerzen)", gws_price=gws_d)
    h4_b64 = render_chart(ohlcv_4h, ticker, "4H (letzten 60 Kerzen)", gws_price=gws_4h, n_candles=60)

    charts = []
    if w_b64:
        charts.append((w_b64, "Weekly"))
    if d_b64:
        charts.append((d_b64, "Daily"))
    if h4_b64:
        charts.append((h4_b64, "4H"))

    return {
        "ticker": ticker,
        "score": None,
        "source": source,
        "jump_pct": jump,
        "surprise_pct": earnings["surprise_pct"],
        "eps_estimate": earnings["eps_estimate"],
        "eps_actual": earnings["eps_actual"],
        "revenue_growth_yoy": earnings.get("revenue_growth_yoy"),
        "charts": charts,
        "news": fetch_news(ticker),
    }


def main():
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    to_addr   = os.environ.get('ALERT_EMAIL_TO', '')

    if not all([smtp_host, smtp_user, smtp_pass, to_addr]):
        print('FEHLER: Bitte SMTP_HOST, SMTP_USER, SMTP_PASS und ALERT_EMAIL_TO setzen.')
        sys.exit(1)

    test_date = os.environ.get('TEST_DATE', '').strip()
    if test_date:
        yesterday_str = test_date
        print(f'check_earnings_global.py – TEST-MODUS, Datum: {yesterday_str}')
    else:
        today = date.today()
        yesterday = today - timedelta(days=1)
        if yesterday.weekday() == 6:
            yesterday = yesterday - timedelta(days=2)
        elif yesterday.weekday() == 5:
            yesterday = yesterday - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        print(f'check_earnings_global.py – Prüfe Earnings vom {yesterday_str}')

    print("\nBaue Ticker-Universum...")
    us_tickers = fetch_us_universe()
    eu_tickers = fetch_europe_universe()
    print(f"US: {len(us_tickers)} Ticker, EU: {len(eu_tickers)} Ticker gesamt")

    rs_tracked = load_rs_tracked_tickers()
    if rs_tracked:
        us_before, eu_before = len(us_tickers), len(eu_tickers)
        us_tickers = [t for t in us_tickers if t not in rs_tracked]
        eu_tickers = [t for t in eu_tickers if t not in rs_tracked]
        print(f"RS-getrackte Ticker ausgeschlossen (bereits von check_earnings.py "
              f"geprüft): US {us_before}→{len(us_tickers)}, EU {eu_before}→{len(eu_tickers)}")
    else:
        print("RS-Indexdateien nicht gefunden — kein Ausschluss möglich")

    limit = os.environ.get('UNIVERSE_LIMIT', '').strip()
    if limit:
        n = int(limit)
        us_tickers = us_tickers[:n]
        eu_tickers = eu_tickers[:n]
        print(f"UNIVERSE_LIMIT={n} aktiv (Testmodus) — US={len(us_tickers)}, EU={len(eu_tickers)}")

    print(f"\n── Kurs-Scan US ({len(us_tickers)} Ticker) ──")
    us_candidates = scan_price_jumps(us_tickers, yesterday_str)
    print(f"US: {len(us_candidates)} Kandidaten mit >= {MIN_PRICE_JUMP * 100:.0f}% Kurssprung")

    print(f"\n── Kurs-Scan EU ({len(eu_tickers)} Ticker) ──")
    eu_candidates = scan_price_jumps(eu_tickers, yesterday_str)
    print(f"EU: {len(eu_candidates)} Kandidaten mit >= {MIN_PRICE_JUMP * 100:.0f}% Kurssprung")

    all_alerts = []
    for source_label, candidates in [("US", us_candidates), ("EU", eu_candidates)]:
        for ticker, jump in candidates:
            print(f"  Kurssprung {ticker} ({source_label}): +{jump * 100:.1f}% – prüfe Earnings …")
            earnings = get_earnings_surprise(ticker, yesterday_str)
            if earnings is None:
                print(f"    → keine Earnings gefunden")
                continue

            surprise = earnings['surprise_pct']
            rev_yoy = earnings.get('revenue_growth_yoy')
            print(f"    → Surprise: {surprise:.1f}%")

            if surprise < MIN_EPS_SURPRISE:
                print(f"    → unter EPS-Schwelle ({MIN_EPS_SURPRISE}%) – übersprungen")
                continue
            if rev_yoy is not None and rev_yoy < -0.05:
                print(f"    → Umsatz YoY stark negativ ({rev_yoy * 100:.1f}%) – übersprungen")
                continue

            print(f"  ✓ ALERT: {ticker} ({source_label})  Sprung={jump * 100:.1f}%  Surprise={surprise:.1f}%")
            all_alerts.append(build_alert(ticker, source_label, jump, earnings))

    all_alerts.sort(key=lambda a: a['surprise_pct'], reverse=True)
    print(f"\nGlobale Earnings-Alerts gesamt: {len(all_alerts)}")

    if all_alerts:
        send_earnings_email(all_alerts, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr,
                             subject_prefix='[Global] ')
        tg_token = os.environ.get('TELEGRAM_TOKEN', '')
        tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        if tg_token:
            from telegram_handler import send_earnings_telegram, resolve_recipients
            tg_recipients = resolve_recipients(tg_chat_id)
            if tg_recipients:
                for a in all_alerts:
                    send_earnings_telegram(tg_token, tg_recipients, a)

        from earnings_alert_log import append_alerts
        append_alerts(all_alerts, source='global',
                       report_dates={a['ticker']: yesterday_str for a in all_alerts})
    else:
        print('Keine globalen Earnings-Überraschungen gefunden.')


if __name__ == "__main__":
    main()
