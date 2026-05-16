"""
Sendet eine Fehler-E-Mail wenn ein GitHub-Actions-Job fehlschlägt.
Aufruf: python notify_failure.py
Erwartet ENV: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO,
              JOB_NAME, RUN_URL
"""
import smtplib, os
from email.mime.text import MIMEText

host = os.environ.get("SMTP_HOST", "")
port = int(os.environ.get("SMTP_PORT", "587"))
user = os.environ.get("SMTP_USER", "")
pw   = os.environ.get("SMTP_PASS", "")
to   = os.environ.get("ALERT_EMAIL_TO", "")
job  = os.environ.get("JOB_NAME", "Unbekannter Job")
url  = os.environ.get("RUN_URL", "")

if not all([host, user, pw, to]):
    print("SMTP nicht konfiguriert – Mail übersprungen")
    raise SystemExit(0)

body = f"""GitHub Actions – Job fehlgeschlagen

Job:  {job}
URL:  {url}

Bitte manuell ausführen:
  GitHub → Actions → {job} → Run workflow

Alle anderen Jobs der Nacht-Kette die danach laufen sollten,
müssen ebenfalls manuell angestossen werden:

  01:00 UTC  → NASDAQ-Update       (update_rs.yml)
  01:15 UTC  → S&P-500-Update      (update_sp500.yml)
  01:30 UTC  → DAX-Update          (update_dax.yml)
  01:45 UTC  → Backtest-Update     (update_backtest_daily.yml)
  02:00 UTC  → Breakout-Alert      (stock_alerts.yml)
  02:15 UTC  → Earnings-Alert      (earnings_alert.yml)
"""

msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = f"Fehler GitHub Actions: {job}"
msg["From"]    = user
msg["To"]      = to

with smtplib.SMTP(host, port) as s:
    s.starttls()
    s.login(user, pw)
    s.sendmail(user, [to], msg.as_string())

print(f"Fehler-Mail gesendet: {job}")
