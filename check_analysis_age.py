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


def load_ratings_index():
    data = load_json("data/ratings/index.json")
    if not data:
        return {}
    ratings = data.get("ratings") or []
    return {r["ticker"].upper(): r for r in ratings}


def load_state():
    data = load_json(STATE_FILE)
    if not data:
        return {"top20": [], "last_seen": {}}
    if "last_seen" not in data:
        data["last_seen"] = {}
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


def build_html(stale_items, new_items, today_str):
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
            rows += (
                f'<tr>'
                f'<td style="padding:6px 12px;font-weight:bold;color:#f1f5f9">{item["ticker"]}</td>'
                f'<td style="padding:6px 12px">{info}</td>'
                f'</tr>'
            )
        sections.append(f"""
<h2 style="color:#22c55e;margin-top:24px">🆕 Neue Aktien in den Top 20</h2>
<p style="color:#94a3b8;font-size:13px">
  Diese Aktien sind neu in den Top 20 der 3-Punkte-Setups aufgetaucht.
</p>
<table style="border-collapse:collapse;width:100%;margin-top:8px">
  <thead>
    <tr style="background:#1e2d45">
      <th style="padding:6px 12px;text-align:left;color:#64748b">Ticker</th>
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

    state = load_state()
    prev_top20 = set(state.get("top20", []))

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

    # Check for newly entered top-20
    # A stock counts as "new" only if it hasn't appeared in the top-20 for the last 7 days.
    NEW_COOLDOWN_DAYS = 7
    last_seen: dict = state.get("last_seen", {})
    cooldown_cutoff = today - timedelta(days=NEW_COOLDOWN_DAYS)

    new_items = []
    for ticker in current_top20:
        last_seen_date = last_seen.get(ticker)
        if last_seen_date:
            try:
                last_seen_dt = datetime.fromisoformat(last_seen_date)
                if last_seen_dt >= cooldown_cutoff:
                    # Seen within the last 7 days – not really new
                    continue
            except Exception:
                pass
        # Not seen in 7 days (or never) → genuinely new
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

    # Update state: save top20 list and refresh last_seen timestamps
    today_iso = today.strftime("%Y-%m-%d")
    for ticker in current_top20:
        last_seen[ticker] = today_iso
    state["top20"] = current_top20
    state["last_seen"] = last_seen
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

    html = build_html(stale_items, new_items, today_str)
    send_email(smtp_host, smtp_port, smtp_user, smtp_pass, to_addr, subject, html)
    print(f"Mail gesendet an {to_addr}")


if __name__ == "__main__":
    main()
