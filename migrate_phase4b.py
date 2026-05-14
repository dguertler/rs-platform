"""Patch: User-Menue rechts oben auf allen Dashboard-Seiten"""
from pathlib import Path

FRONTEND = Path(__file__).parent / "frontend"

INJECT = """<script>
  (async function() {
    try {
      var r = await window.apiFetch('/api/user/me');
      if (!r || r.status !== 200) return;
      var u = await r.json();
      var bar = document.getElementById('plan-bar');
      if (!bar) return;
      var planHtml = u.plan === 'pro'
        ? '<span style="color:#22c55e;font-weight:600">&#10003; Pro</span>'
        : 'Free&nbsp;<button onclick="(async function(){var x=await window.apiFetch(\\'/api/stripe/checkout\\');var d=await x.json();if(d.url)window.location.href=d.url;})()" style="background:#2563eb;color:#fff;border:none;padding:2px 10px;border-radius:4px;font-size:12px;cursor:pointer">Upgrade</button>';
      var adminLink = u.is_admin
        ? '&nbsp;&nbsp;<a href="/admin.html" style="color:#fbbf24;font-size:12px;text-decoration:none">Admin</a>'
        : '';
      bar.innerHTML = planHtml
        + '&nbsp;&nbsp;<a href="/account.html" style="color:#94a3b8;font-size:12px;text-decoration:none">Konto</a>'
        + adminLink;
    } catch(e) {}
  })();
</script>
"""

MARKER = '})();\n</script>\n<script type="text/babel">'
SKIP = {"login.html", "forgot.html", "reset.html", "account.html", "admin.html"}

patched = 0
for f in FRONTEND.glob("*.html"):
    if f.name in SKIP:
        continue
    text = f.read_text(encoding="utf-8")
    if "plan-bar" not in text:
        print(f"SKIP {f.name} (kein plan-bar)")
        continue
    if "/account.html" in text:
        print(f"SKIP {f.name} (bereits gepatcht)")
        continue
    if MARKER in text:
        text = text.replace(MARKER, f"}})()\n</script>\n{INJECT}<script type=\"text/babel\">", 1)
        f.write_text(text, encoding="utf-8")
        print(f"patched {f.name}")
        patched += 1
    else:
        # Fallback: vor </body> einfuegen
        if "</body>" in text:
            text = text.replace("</body>", INJECT + "</body>", 1)
            f.write_text(text, encoding="utf-8")
            print(f"patched {f.name} (fallback)")
            patched += 1
        else:
            print(f"SKIP {f.name} (Marker nicht gefunden)")

print(f"\n{patched} Datei(en) aktualisiert.")
