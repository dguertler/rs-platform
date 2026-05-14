"""Patch: Pro-Gate Overlay fuer Backtest-Seiten"""
from pathlib import Path

FRONTEND = Path(__file__).parent / "frontend"

PRO_GATE_DIV = (
    '  <div id="pro-gate" style="display:none;position:fixed;inset:0;'
    'background:rgba(10,15,30,0.97);z-index:10000;'
    'align-items:center;justify-content:center">\n'
    '    <div style="text-align:center;padding:40px;background:#0f172a;'
    'border:1px solid #1e293b;border-radius:16px;max-width:380px;width:90%">\n'
    '      <div style="font-size:40px;margin-bottom:16px">&#128274;</div>\n'
    '      <h2 style="color:#f1f5f9;font-size:20px;font-weight:600;margin-bottom:10px">'
    'Pro-Account erforderlich</h2>\n'
    '      <p style="color:#64748b;font-size:14px;line-height:1.6;margin-bottom:24px">'
    'Backtests sind exklusiv fuer Pro-Nutzer verfuegbar.<br>'
    'Upgrade jetzt und erhalte Zugriff auf alle Analysen.</p>\n'
    '      <button onclick="(async function(){'
    'var x=await window.apiFetch(\'/api/stripe/checkout\');'
    'var d=await x.json();if(d.url)window.location.href=d.url;})()" '
    'style="background:#2563eb;color:#fff;border:none;border-radius:8px;'
    'padding:12px 0;font-size:15px;font-weight:600;cursor:pointer;width:100%;'
    'margin-bottom:12px">Jetzt upgraden</button>\n'
    '      <a href="/" style="display:block;color:#64748b;font-size:13px;'
    'text-decoration:none">&#8592; Zurueck zum Dashboard</a>\n'
    '    </div>\n'
    '  </div>\n'
)

OLD_BANNER = (
    '<script>\n'
    '  (async function() {\n'
    '    try {\n'
    '      var r = await window.apiFetch(\'/api/user/me\');\n'
    '      if (!r || r.status !== 200) return;\n'
    '      var u = await r.json();\n'
    '      var bar = document.getElementById(\'plan-bar\');\n'
    '      if (!bar) return;\n'
    '      var planHtml = u.plan === \'pro\'\n'
    '        ? \'<span style="color:#22c55e;font-weight:600">&#10003; Pro</span>\'\n'
    '        : \'Free&nbsp;<button onclick="(async function(){var x=await window.apiFetch(\\\'/api/stripe/checkout\\\');var d=await x.json();if(d.url)window.location.href=d.url;})()" style="background:#2563eb;color:#fff;border:none;padding:2px 10px;border-radius:4px;font-size:12px;cursor:pointer">Upgrade</button>\';\n'
    '      var adminLink = u.is_admin\n'
    '        ? \'&nbsp;&nbsp;<a href="/admin.html" style="color:#fbbf24;font-size:12px;text-decoration:none">Admin</a>\'\n'
    '        : \'\';\n'
    '      bar.innerHTML = planHtml\n'
    '        + \'&nbsp;&nbsp;<a href="/account.html" style="color:#94a3b8;font-size:12px;text-decoration:none">Konto</a>\'\n'
    '        + adminLink;\n'
    '    } catch(e) {}\n'
    '  })();\n'
    '</script>'
)

NEW_BANNER = (
    '<script>\n'
    '  (async function() {\n'
    '    try {\n'
    '      var r = await window.apiFetch(\'/api/user/me\');\n'
    '      if (!r || r.status !== 200) return;\n'
    '      var u = await r.json();\n'
    '      if (u.plan !== \'pro\') {\n'
    '        var gate = document.getElementById(\'pro-gate\');\n'
    '        if (gate) gate.style.display = \'flex\';\n'
    '        return;\n'
    '      }\n'
    '      var bar = document.getElementById(\'plan-bar\');\n'
    '      if (!bar) return;\n'
    '      var adminLink = u.is_admin\n'
    '        ? \'&nbsp;&nbsp;<a href="/admin.html" style="color:#fbbf24;font-size:12px;text-decoration:none">Admin</a>\'\n'
    '        : \'\';\n'
    '      bar.innerHTML = \'<span style="color:#22c55e;font-weight:600">&#10003; Pro</span>\'\n'
    '        + \'&nbsp;&nbsp;<a href="/account.html" style="color:#94a3b8;font-size:12px;text-decoration:none">Konto</a>\'\n'
    '        + adminLink;\n'
    '    } catch(e) {}\n'
    '  })();\n'
    '</script>'
)

for fname in ("backtest.html", "backtest_overview.html"):
    fpath = FRONTEND / fname
    if not fpath.exists():
        print(f"NOT FOUND: {fname}")
        continue
    text = fpath.read_text(encoding="utf-8")
    changed = False

    if "pro-gate" not in text:
        text = text.replace("<body>", "<body>\n" + PRO_GATE_DIV, 1)
        changed = True

    if OLD_BANNER in text:
        text = text.replace(OLD_BANNER, NEW_BANNER)
        changed = True
        print(f"patched {fname}")
    else:
        print(f"WARN {fname}: Banner-Muster nicht gefunden, nur Pro-Gate-Div eingefuegt")

    if changed:
        fpath.write_text(text, encoding="utf-8")

print("\nFertig. Server neu starten: start.bat")
