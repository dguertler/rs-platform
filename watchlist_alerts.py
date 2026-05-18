"""
Watchlist Alert Script
======================
Checks each user's watchlist daily and sends an email if:
  1. A ticker falls out of the Top 20 of its index
  2. The Daily green dot (structure broken) disappears

Run this script once per day via cron after data is updated.
State is persisted in watchlist_alert_state.json.

Usage:
    python watchlist_alerts.py
    python watchlist_alerts.py --dry-run   # print alerts without sending
"""

import subprocess
subprocess.run(["pip", "install", "yfinance", "deep-translator", "-q"], capture_output=True)

import json
import os
import sys
import sqlite3
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

DRY_RUN = "--dry-run" in sys.argv

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", r"C:\Users\danie\Rel.-Strength"))
DB_PATH  = Path(os.getenv("DB_PATH", Path(__file__).parent / "backend" / "users.db"))
STATE_FILE = Path(__file__).parent / "watchlist_alert_state.json"

MARKET_FILES = {
    "nasdaq": "rs_full.json",
    "sp500":  "rs_sp500.json",
    "dax":    "rs_dax.json",
}
MARKET_NAMES = {
    "nasdaq": "Nasdaq-100",
    "sp500":  "S&P 500",
    "dax":    "DAX",
}


# ── GWS-D Analyse (Python port) ───────────────────────────────────────────────
def analyze_daily_structure(ohlcv: list) -> dict | None:
    if not ohlcv or len(ohlcv) < 10:
        return None
    n      = len(ohlcv)
    highs  = [d["h"] for d in ohlcv]
    lows   = [d["l"] for d in ohlcv]
    closes = [d["c"] for d in ohlcv]

    swing_highs = []
    for i in range(2, n - 2):
        if (highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and
                highs[i] >= highs[i+1] and highs[i] >= highs[i+2]):
            swing_highs.append({"idx": i, "price": highs[i]})

    swing_lows = []
    for i in range(2, n - 2):
        if (lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and
                lows[i] <= lows[i+1] and lows[i] <= lows[i+2]):
            swing_lows.append({"idx": i, "price": lows[i]})

    gws_candidates = []
    for j in range(1, len(swing_lows)):
        tief_neu = swing_lows[j]
        tief_alt = swing_lows[j - 1]
        if tief_neu["price"] < tief_alt["price"]:
            between = [sh for sh in swing_highs if tief_alt["idx"] < sh["idx"] < tief_neu["idx"]]
            if between:
                best = max(between, key=lambda x: x["price"])
                gws_candidates.append(best)

    gws_high = gws_candidates[-1] if gws_candidates else None
    breakout_idx = None
    if gws_high:
        for i in range(gws_high["idx"] + 1, n):
            if closes[i] > gws_high["price"]:
                breakout_idx = i
                break

    trend = "neutral"
    if len(swing_highs) >= 2:
        if swing_highs[-1]["price"] > swing_highs[-2]["price"]:
            trend = "bullish"
        elif swing_highs[-1]["price"] < swing_highs[-2]["price"]:
            trend = "bearish"

    broken = breakout_idx is not None or (gws_high is None and trend == "bullish")
    return {"broken": broken}


# ── Data Loading ──────────────────────────────────────────────────────────────
def load_market_data() -> dict:
    """Load all market JSON files. Returns {market: {"arr": [...], "top20": [...]}}"""
    result = {}
    for market, filename in MARKET_FILES.items():
        path = DATA_DIR / filename
        if not path.exists():
            print(f"  [SKIP] {path} not found")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            arr = raw if isinstance(raw, list) else raw.get("data", [])
            top20 = [e["ticker"] for e in arr[:20]]
            result[market] = {"arr": arr, "top20": top20}
        except Exception as e:
            print(f"  [ERR] Loading {filename}: {e}")
    return result


def find_ticker(ticker: str, market_data: dict) -> list[dict]:
    """Find ticker across all markets. Returns list of market hits."""
    hits = []
    ticker_upper = ticker.upper()
    for market, mdata in market_data.items():
        for idx, entry in enumerate(mdata["arr"]):
            if entry.get("ticker", "").upper() == ticker_upper:
                daily_struct = analyze_daily_structure(entry.get("ohlcv", []))
                hits.append({
                    "market":     market,
                    "rank":       idx + 1,
                    "in_top20":   idx < 20,
                    "daily_broken": daily_struct["broken"] if daily_struct else None,
                })
                break
    return hits


# ── State Management ──────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ── Database ──────────────────────────────────────────────────────────────────
def get_all_watchlists() -> dict[str, list[str]]:
    """Returns {email: [ticker, ...]}"""
    if not DB_PATH.exists():
        print(f"  [ERR] DB not found: {DB_PATH}")
        return {}
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT user_email, ticker FROM watchlist ORDER BY user_email, added_at"
            ).fetchall()
        result: dict[str, list[str]] = {}
        for email, ticker in rows:
            result.setdefault(email, []).append(ticker)
        return result
    except Exception as e:
        print(f"  [ERR] Reading watchlists: {e}")
        return {}


# ── Email ─────────────────────────────────────────────────────────────────────
def send_watchlist_email(to_email: str, alerts: list[dict], date_str: str) -> bool:
    """Send a watchlist alert email to the user."""
    resend_key = os.getenv("RESEND_API_KEY", "")
    smtp_host  = os.getenv("SMTP_HOST", "")
    smtp_port  = int(os.getenv("SMTP_PORT", "587"))
    smtp_user  = os.getenv("SMTP_USER", "")
    smtp_pass  = os.getenv("SMTP_PASS", "")

    subject = f"Watchlist-Alarm {date_str}: {len(alerts)} Änderung(en)"

    def dot_html(active: bool | None) -> str:
        if active is None:
            return '<span style="color:#475569">—</span>'
        color = "#4ade80" if active else "#ef4444"
        return f'<span style="color:{color};font-weight:bold">{"●" if active else "○"}</span>'

    rows_html = ""
    for a in alerts:
        badge_color = "#22c55e" if a.get("in_top20") else "#ef4444"
        badge_text  = "TOP 20 ✓" if a.get("in_top20") else "NICHT TOP 20"
        market_label = MARKET_NAMES.get(a.get("market", ""), a.get("market", ""))
        rank_text = f"#{a.get('rank', '?')} in {market_label}" if a.get("rank") else ""
        rows_html += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px 12px;font-family:monospace;font-weight:700;color:#f1f5f9">{a["ticker"]}</td>
          <td style="padding:8px 12px;font-size:12px;color:#94a3b8">{rank_text}</td>
          <td style="padding:8px 12px">
            <span style="background:{badge_color}22;color:{badge_color};border:1px solid {badge_color}44;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:700">
              {badge_text}
            </span>
          </td>
          <td style="padding:8px 12px;text-align:center">{dot_html(a.get('daily_broken'))}</td>
          <td style="padding:8px 12px;font-size:11px;color:#64748b">{a.get('reason','')}</td>
        </tr>"""

    app_url = os.getenv("APP_URL", "http://localhost:8000")
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/></head>
<body style="background:#060b14;color:#e2e8f0;font-family:Inter,system-ui,sans-serif;padding:20px">
  <div style="max-width:680px;margin:0 auto">
    <h2 style="color:#8b5cf6;font-family:monospace;margin-bottom:4px">★ Watchlist-Alarm</h2>
    <p style="color:#475569;font-size:13px;margin-bottom:20px">{date_str} · {len(alerts)} Änderung(en) in deiner Watchlist</p>
    <table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:8px;overflow:hidden">
      <thead>
        <tr style="background:#1e293b;font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:0.5px">
          <th style="padding:8px 12px;text-align:left">Ticker</th>
          <th style="padding:8px 12px;text-align:left">Rang</th>
          <th style="padding:8px 12px;text-align:left">Top-20-Status</th>
          <th style="padding:8px 12px;text-align:center">D</th>
          <th style="padding:8px 12px;text-align:left">Änderung</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p style="margin-top:20px;font-size:12px;color:#334155">
      <a href="{app_url}/watchlist.html" style="color:#8b5cf6">→ Watchlist öffnen</a>
    </p>
  </div>
</body></html>"""

    if DRY_RUN:
        print(f"\n[DRY-RUN] E-Mail an {to_email}:\n{subject}")
        for a in alerts:
            print(f"  · {a['ticker']}: {a['reason']}")
        return True

    # Try Resend first
    if resend_key:
        import urllib.request
        payload = json.dumps({
            "from": "RS Platform <alerts@resend.dev>",
            "to":   [to_email],
            "subject": subject,
            "html":    html,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=15)
            print(f"  [OK] Resend → {to_email}")
            return True
        except Exception as e:
            print(f"  [WARN] Resend fehlgeschlagen: {e}")

    # Fallback: SMTP
    if smtp_host and smtp_user:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = smtp_user
            msg["To"]      = to_email
            msg.attach(MIMEText(html, "html", "utf-8"))
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
                s.starttls()
                s.login(smtp_user, smtp_pass)
                s.sendmail(smtp_user, [to_email], msg.as_string())
            print(f"  [OK] SMTP → {to_email}")
            return True
        except Exception as e:
            print(f"  [ERR] SMTP fehlgeschlagen: {e}")

    print(f"  [WARN] Kein E-Mail-Versand konfiguriert. Alarm für {to_email}: {subject}")
    return False


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n=== Watchlist-Alerts {today} {'(DRY-RUN)' if DRY_RUN else ''} ===")

    market_data = load_market_data()
    if not market_data:
        print("Keine Marktdaten vorhanden. Abbruch.")
        return

    watchlists = get_all_watchlists()
    if not watchlists:
        print("Keine Watchlists in der Datenbank.")
        return

    state = load_state()
    new_state = {}

    for email, tickers in watchlists.items():
        print(f"\nNutzer: {email} ({len(tickers)} Ticker)")
        user_alerts = []

        for ticker in tickers:
            hits = find_ticker(ticker, market_data)
            ticker_key = f"{email}::{ticker}"

            prev = state.get(ticker_key, {})
            new_state[ticker_key] = {}

            for hit in hits:
                market = hit["market"]
                mk = f"{ticker_key}::{market}"
                prev_mk = prev.get(market, {})
                curr_state = {
                    "in_top20":     hit["in_top20"],
                    "daily_broken": hit["daily_broken"],
                    "rank":         hit["rank"],
                }
                new_state[ticker_key][market] = curr_state

                # Check: was in top20, now isn't
                if prev_mk.get("in_top20") is True and not hit["in_top20"]:
                    user_alerts.append({
                        "ticker":       ticker,
                        "market":       market,
                        "rank":         hit["rank"],
                        "in_top20":     hit["in_top20"],
                        "daily_broken": hit["daily_broken"],
                        "reason":       f"Nicht mehr in Top 20 des {MARKET_NAMES.get(market, market)} (jetzt #{hit['rank']})",
                    })

                # Check: daily dot was green, now gone
                if prev_mk.get("daily_broken") is True and hit["daily_broken"] is False:
                    user_alerts.append({
                        "ticker":       ticker,
                        "market":       market,
                        "rank":         hit["rank"],
                        "in_top20":     hit["in_top20"],
                        "daily_broken": hit["daily_broken"],
                        "reason":       f"Daily-Struktur (grüner Punkt) verloren",
                    })

            # No hits in any market
            if not hits:
                new_state[ticker_key] = {}

        if user_alerts:
            print(f"  → {len(user_alerts)} Alert(s): {[a['ticker']+' '+a['reason'] for a in user_alerts]}")
            send_watchlist_email(email, user_alerts, today)
        else:
            print(f"  → Keine Änderungen")

    save_state(new_state)
    print(f"\n=== Fertig. State gespeichert in {STATE_FILE} ===")


if __name__ == "__main__":
    run()
