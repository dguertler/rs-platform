import json
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

TOP20_LIMIT = 20
MIN_POINTS = 3
MAX_AGE_DAYS = 21
STATE_FILE = "data/top20_state.json"

# Import GWS analysis from check_alerts (same repo)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_alerts import analyze_weekly_structure, analyze_daily_structure, analyze_4h_structure


def count_points(entry):
    struct_w  = analyze_weekly_structure(entry.get("ohlcv_w", []))
    struct_d  = analyze_daily_structure(entry.get("ohlcv", []))
    struct_4h = analyze_4h_structure(entry.get("ohlcv_4h", []))
    p_w  = bool(struct_w.get("broken"))    if struct_w  else False
    p_d  = bool(struct_d.get("broken"))    if struct_d  else False
    p_4h = bool(struct_4h.get("broken4h")) if struct_4h else False
    return int(p_w) + int(p_d) + int(p_4h)


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def get_top20_tickers():
    """Collect top-20 stocks with 3 points across all three indices, sorted by RS score."""
    sources = [
        "data/rs_full.json",
        "data/rs_dax.json",
        "data/rs_sp500.json",
    ]
    seen = set()
    result = []
    for path in sources:
        data = load_json(path)
        if not data:
            continue
        entries = data.get("data") or []
        for e in entries:
            ticker = e.get("ticker", "")
            if not ticker or ticker in seen:
                continue
            pts = count_points(e)
            rs = e.get("score", 0) or 0
            result.append({"ticker": ticker, "points": pts, "rs": rs})
            seen.add(ticker)

    three_pt = [e for e in result if e["points"] >= MIN_POINTS]
    three_pt.sort(key=lambda x: x["rs"], reverse=True)
    return [e["ticker"] for e in three_pt[:TOP20_LIMIT]]


def get_all_ranks():
    """Return {ticker: {'full': rank, 'dax': rank, 'sp500': rank}} for every stock.
    Rank = 1-based position in the (already RS-score-sorted) data array."""
    sources = {
        "full":  "data/rs_full.json",
        "dax":   "data/rs_dax.json",
        "sp500": "data/rs_sp500.json",
    }
    result = {}
    for key, path in sources.items():
        data = load_json(path)
        if not data:
            continue
        for idx, entry in enumerate(data.get("data") or []):
            ticker = entry.get("ticker", "")
            if not ticker:
                continue
            if ticker not in result:
                result[ticker] = {"full": None, "dax": None, "sp500": None}
            result[ticker][key] = idx + 1
    return result


def is_newly_in_top20(ticker, current_ranks, prev_ranks, threshold=TOP20_LIMIT):
    """True if ticker just entered top-N in any index (rank crossed threshold from above)."""
    curr = current_ranks.get(ticker, {})
    prev = prev_ranks.get(ticker, {})
    for key in ("full", "dax", "sp500"):
        curr_rank = curr.get(key)
        prev_rank = prev.get(key)
        if curr_rank is not None and curr_rank <= threshold:
            if prev_rank is None or prev_rank > threshold:
                return True
    return False


def best_rank_label(ticker, ranks):
    """Return a human-readable label for the best (lowest) rank across indices."""
    index_names = {"full": "NASDAQ-100", "dax": "DAX-40", "sp500": "S&P 500"}
    best = None
    best_key = None
    r = ranks.get(ticker, {})
    for key in ("full", "dax", "sp500"):
        v = r.get(key)
        if v is not None and (best is None or v < best):
            best = v
            best_key = key
    if best is None:
        return ""
    return f"#{best} {index_names[best_key]}"


def load_ratings_index():
    data = load_json("data/ratings/index.json")
    if not data:
        return {}
    ratings = data.get("ratings") or []
    return {r["ticker"].upper(): r for r in ratings}


def load_state():
    data = load_json(STATE_FILE)
    if not data:
        return {"top20": [], "ranks": {}}
    if "ranks" not in data:
        data["ranks"] = {}
    return data


def save_state(state):
    os.makedirs("data", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_email(smtp_host, smtp_port, smtp_user, smtp_pass, to_addr, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP(smtp_host, int(smtp_port), timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_addr, msg.as_string())


def build_html(stale_items, new_items, today_str, current_ranks=None):
    sections = []

    if stale_items:
        rows = ""
        for item in stale_items:
            rows += (
                f'<tr>'
                f'<td style="padding:6px 12px;font-weight:bold;color:#f1f5f9">{item["ticker"]}</td>'
                f'<td style="padding:6px 12px;color:#94a3b8">{item["created_str"]}</td>'
                f'<td style="padding:6px 12px;color:#f87171">{item["age_days"]} Tage alt</td>'
                f'</tr>'
            )
        sections.append(f"""
<h2 style="color:#f59e0b;margin-top:24px">⚠️ Veraltete Analysen (&gt; 3 Wochen)</h2>
<p style="color:#94a3b8;font-size:13px">
  Die folgenden Top-20-Aktien (3 Punkte) haben Analysen, die älter als {MAX_AGE_DAYS} Tage sind.
  Bitte Analysen aktualisieren.
</p>
<table style="border-collapse:collapse;width:100%;margin-top:8px">
  <thead>
    <tr style="background:#1e2d45">
      <th style="padding:6px 12px;text-align:left;color:#64748b">Ticker</th>
      <th style="padding:6px 12px;text-align:left;color:#64748b">Erstellt am</th>
      <th style="padding:6px 12px;text-align:left;color:#64748b">Alter</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>""")

    if new_items:
        rows = ""
        for item in new_items:
            if item.get("has_analysis"):
                info = f'<span style="color:#60a5fa">Analyse vom {item["created_str"]}</span>'
            else:
                info = '<span style="color:#f87171">Noch keine Analyse vorhanden</span>'
            rank_label = best_rank_label(item["ticker"], current_ranks or {})
            rank_cell = f'<span style="color:#a78bfa;font-size:12px">{rank_label}</span>' if rank_label else ""
            rows += (
                f'<tr>'
                f'<td style="padding:6px 12px;font-weight:bold;color:#f1f5f9">{item["ticker"]}</td>'
                f'<td style="padding:6px 12px">{rank_cell}</td>'
                f'<td style="padding:6px 12px">{info}</td>'
                f'</tr>'
            )
        sections.append(f"""
<h2 style="color:#22c55e;margin-top:24px">🆕 Neue Aktien in den Top 20</h2>
<p style="color:#94a3b8;font-size:13px">
  Diese Aktien haben die Top-20-Grenze ihres Index neu durchbrochen (Rang vorher &gt; 20, jetzt &le; 20).
</p>
<table style="border-collapse:collapse;width:100%;margin-top:8px">
  <thead>
    <tr style="background:#1e2d45">
      <th style="padding:6px 12px;text-align:left;color:#64748b">Ticker</th>
      <th style="padding:6px 12px;text-align:left;color:#64748b">Rang</th>
      <th style="padding:6px 12px;text-align:left;color:#64748b">Analyse-Status</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>""")

    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html><body style="background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;
padding:24px;max-width:700px;margin:0 auto">
<h1 style="color:#f1f5f9;font-size:18px;margin-bottom:4px">
  Analyse-Check &mdash; {today_str}
</h1>
{body}
<p style="font-size:10px;color:#334155;margin-top:32px">
  Automatisch generiert von RS-Platform · check_analysis_age.py
</p>
</body></html>"""


def main():
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = os.environ.get("SMTP_PORT", "587")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    to_addr   = os.environ.get("ALERT_EMAIL_TO", "")

    if not all([smtp_host, smtp_user, smtp_pass, to_addr]):
        print("FEHLER: SMTP_HOST, SMTP_USER, SMTP_PASS und ALERT_EMAIL_TO müssen gesetzt sein.")
        return

    today = datetime.now()
    today_str = today.strftime("%d.%m.%Y")
    cutoff = today - timedelta(days=MAX_AGE_DAYS)

    current_top20 = get_top20_tickers()
    print(f"Top-20 (3 Punkte): {current_top20}")

    current_ranks = get_all_ranks()

    state = load_state()
    prev_ranks = state.get("ranks", {})

    ratings = load_ratings_index()

    # Check for stale analyses
    stale_items = []
    for ticker in current_top20:
        r = ratings.get(ticker.upper())
        if not r:
            continue
        created_str = r.get("created_at", "")
        if not created_str:
            continue
        try:
            created = datetime.fromisoformat(created_str)
        except Exception:
            continue
        if created < cutoff:
            age_days = (today - created).days
            stale_items.append({
                "ticker": ticker,
                "created_str": created.strftime("%d.%m.%Y"),
                "age_days": age_days,
            })

    # Check for newly entered top-20: rank crossed from >20 to ≤20 in any index
    new_items = []
    for ticker in current_top20:
        if not is_newly_in_top20(ticker, current_ranks, prev_ranks):
            continue
        r = ratings.get(ticker.upper())
        if r and r.get("created_at"):
            try:
                created = datetime.fromisoformat(r["created_at"])
                new_items.append({
                    "ticker": ticker,
                    "has_analysis": True,
                    "created_str": created.strftime("%d.%m.%Y"),
                })
            except Exception:
                new_items.append({"ticker": ticker, "has_analysis": False})
        else:
            new_items.append({"ticker": ticker, "has_analysis": False})

    # Update state with current ranks and top20
    state["top20"] = current_top20
    state["ranks"] = current_ranks
    save_state(state)

    if not stale_items and not new_items:
        print("Kein Handlungsbedarf heute.")
        return

    print(f"Veraltete Analysen: {[i['ticker'] for i in stale_items]}")
    print(f"Neue Top-20: {[i['ticker'] for i in new_items]}")

    subject_parts = []
    if stale_items:
        subject_parts.append(f"{len(stale_items)} veraltete Analyse(n)")
    if new_items:
        subject_parts.append(f"{len(new_items)} neue Top-20-Aktie(n)")
    subject = f"RS-Platform Analyse-Check {today_str}: {' & '.join(subject_parts)}"

    html = build_html(stale_items, new_items, today_str, current_ranks)
    send_email(smtp_host, smtp_port, smtp_user, smtp_pass, to_addr, subject, html)
    print(f"Mail gesendet an {to_addr}")


if __name__ == "__main__":
    main()
