import os, json
from urllib.request import Request, urlopen
from urllib.error import URLError


def send_reset_email(to_email: str, reset_url: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")

    print(f"[RESEND DEBUG] api_key present: {bool(api_key)}")
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
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
