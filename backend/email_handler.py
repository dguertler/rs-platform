import os, json
from urllib.request import Request, urlopen
from urllib.error import URLError


def send_reset_email(to_email: str, reset_url: str) -> bool:
    api_key = os.environ.get("BREVO_API_KEY", "")
    sender_email = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", ""))
    sender_name = "RS Platform"

    if "<" in sender_email:
        parts = sender_email.split("<")
        sender_name = parts[0].strip()
        sender_email = parts[1].replace(">", "").strip()

    if not api_key or not sender_email:
        print(f"[RESET LINK] {to_email} -> {reset_url}")
        return True

    payload = json.dumps({
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": "RS Platform - Passwort zuruecksetzen",
        "textContent": (
            f"Hallo,\n\nPasswort zuruecksetzen:\n\n{reset_url}\n\n"
            "Der Link ist 1 Stunde gueltig.\n\nRS Platform"
        )
    }).encode("utf-8")

    req = Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        method="POST"
    )
    try:
        urlopen(req, timeout=10)
        return True
    except URLError as e:
        print(f"[EMAIL ERROR] {e}")
        print(f"[RESET LINK] {to_email} -> {reset_url}")
        return False
