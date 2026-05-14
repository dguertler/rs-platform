"""Patch: fetch() -> window.apiFetch() im Babel-Script der Backtest-Seiten"""
from pathlib import Path

FRONTEND = Path(__file__).parent / "frontend"

for fname in ("backtest.html", "backtest_overview.html"):
    fpath = FRONTEND / fname
    text  = fpath.read_text(encoding="utf-8")

    babel_marker = '<script type="text/babel">'
    babel_start  = text.find(babel_marker)
    if babel_start == -1:
        print(f"SKIP {fname}: kein Babel-Script gefunden")
        continue

    before = text[:babel_start]
    babel  = text[babel_start:]

    count = babel.count("fetch(")
    if count == 0:
        print(f"SKIP {fname}: keine fetch()-Aufrufe im Babel-Script")
        continue

    patched_babel = babel.replace("fetch(", "window.apiFetch(")
    fpath.write_text(before + patched_babel, encoding="utf-8")
    print(f"patched {fname}: {count} fetch()-Aufruf(e) -> window.apiFetch()")

print("\nFertig. Server neu starten: start.bat")
