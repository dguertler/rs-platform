import smtplib, os
from email.mime.text import MIMEText


def send_reset_email(to_email: str, reset_url: str) -> bool:
    host  = os.environ.get("SMTP_HOST", "")
    port  = int(os.environ.get("SMTP_PORT", "587"))
    user  = os.environ.get("SMTP_USER", "")
    pw    = os.environ.get("SMTP_PASS", "")
    frm   = os.environ.get("SMTP_FROM", user)
    if not host or not user:
        print(f"[RESET LINK] {to_email} -> {reset_url}")
        return True
    msg = MIMEText(
        f"Hallo,\n\nPasswort zuruecksetzen:\n\n{reset_url}\n\n"
        "Der Link ist 1 Stunde gueltig.\n\nRS Platform"
    )
    msg["Subject"] = "RS Platform - Passwort zuruecksetzen"
    msg["From"]    = frm
    msg["To"]      = to_email
    try:
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        print(f"[RESET LINK] {to_email} -> {reset_url}")
        return False
