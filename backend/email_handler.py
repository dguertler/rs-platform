import os, json, smtplib
from email.mime.text import MIMEText
from urllib.request import Request, urlopen
from urllib.error import URLError


def send_reset_email(to_email: str, reset_url: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")

    if not api_key:
        print(f"[RESET LINK] {to_email} -> {reset_url}")
        return True

    payload = json.dumps({
        "from": "RS Platform <onboarding@resend.dev>",
        "to": [to_email],
        "subject": "RS Platform - Passwort zuruecksetzen",
        "text": (
            f"Hallo,\n\nPasswort zuruecksetzen:\n\n{reset_url}\n\n"
            "Der Link ist 1 Stunde gueltig.\n\nRS Platform"
        )
    }).encode("utf-8")

    req = Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "rs-platform/1.0",
        },
        method="POST"
    )
    try:
        urlopen(req, timeout=10)
        return True
    except URLError as e:
        body = e.read().decode("utf-8") if hasattr(e, "read") else ""
        print(f"[EMAIL ERROR] {e} | {body}")
        print(f"[RESET LINK] {to_email} -> {reset_url}")
        return False


def send_reset_email_gmail(to_email: str, reset_url: str) -> bool:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    pw   = os.environ.get("SMTP_PASS", "")

    if not user or not pw:
        print(f"[GMAIL] Keine SMTP-Credentials — SMTP_USER/SMTP_PASS fehlen")
        print(f"[RESET LINK] {to_email} -> {reset_url}")
        return False

    msg = MIMEText(
        f"Hallo,\n\nPasswort zuruecksetzen:\n\n{reset_url}\n\n"
        "Der Link ist 1 Stunde gueltig.\n\nRS Platform"
    )
    msg["Subject"] = "RS Platform - Passwort zuruecksetzen"
    msg["From"]    = user
    msg["To"]      = to_email

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, pw)
            server.sendmail(user, [to_email], msg.as_string())
        print(f"[GMAIL] Mail gesendet an {to_email}")
        return True
    except Exception as e:
        print(f"[GMAIL ERROR] {e}")
        print(f"[RESET LINK] {to_email} -> {reset_url}")
        return False
