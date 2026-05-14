"""Einmalig ausfuehren: Kopiert HTML-Dateien und aendert fetch()-Pfade auf API-Endpoints."""
from pathlib import Path

SRC = Path(r"C:\Users\danie\Rel.-Strength")
DST = Path(r"C:\Users\danie\rs-platform\frontend")

DST.mkdir(parents=True, exist_ok=True)
(DST / "ratings").mkdir(exist_ok=True)

COMMON = [
    ('fetch("rs_full.json")',        'fetch("/api/rs/nasdaq")'),
    ('fetch("rs_sp500.json")',       'fetch("/api/rs/sp500")'),
    ('fetch("rs_dax.json")',         'fetch("/api/rs/dax")'),
    ('fetch("signals.json")',        'fetch("/api/signals")'),
    ('fetch("ratings/index.json")',  'fetch("/api/ratings")'),
]

BACKTEST_EXTRA = [
    (
        "const jsonFile    = `backtest_${t.toLowerCase().replace(/\\./g, '_')}.json`;",
        "const jsonFile    = `/api/backtest/${t}`;"
    ),
    (
        "const sources = ['rs_full.json', 'rs_sp500.json', 'rs_dax.json'];",
        "const sources = ['/api/rs/nasdaq', '/api/rs/sp500', '/api/rs/dax'];"
    ),
    (
        "const rsFiles = ['rs_full.json', 'rs_sp500.json', 'rs_dax.json'];",
        "const rsFiles = ['/api/rs/nasdaq', '/api/rs/sp500', '/api/rs/dax'];"
    ),
]

OVERVIEW_EXTRA = [
    ("{ file: 'rs_full.json',  index: 'QQQ' },",  "{ file: '/api/rs/nasdaq',  index: 'QQQ' },"),
    ("{ file: 'rs_sp500.json', index: 'SPX' },",   "{ file: '/api/rs/sp500', index: 'SPX' },"),
    ("{ file: 'rs_dax.json',   index: 'DAX' },",   "{ file: '/api/rs/dax',   index: 'DAX' },"),
    (
        "fetch(`backtest_${s.ticker.toLowerCase().replace(/\\./g, '_')}.json`)",
        "fetch(`/api/backtest/${s.ticker}`)"
    ),
]

FILES = [
    ("index.html",             DST / "index.html",             []),
    ("sp500.html",             DST / "sp500.html",             []),
    ("dax.html",               DST / "dax.html",               []),
    ("backtest.html",          DST / "backtest.html",          BACKTEST_EXTRA),
    ("backtest_overview.html", DST / "backtest_overview.html", OVERVIEW_EXTRA),
    ("ratings/sndk.html",      DST / "ratings" / "sndk.html",  []),
]

for src_rel, dst_path, extras in FILES:
    src_path = SRC / src_rel
    if not src_path.exists():
        print(f"  SKIP (nicht gefunden): {src_rel}")
        continue
    content = src_path.read_text(encoding="utf-8")
    for old, new in COMMON + extras:
        content = content.replace(old, new)
    dst_path.write_text(content, encoding="utf-8")
    print(f"  OK  {src_rel}")

print("\nMigration abgeschlossen.")
