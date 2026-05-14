"""
Trim backtest JSON files to last 4 years to reduce file size.
Keeps enough history for the 60-week lookback window in backtest_logic.js.
Usage: python trim_backtest.py [--dry-run]
"""
import json, os, sys
from pathlib import Path
from datetime import date, timedelta

SRC_DIR  = Path(r"C:\Users\danie\Rel.-Strength")
DEST_DIR = Path(__file__).parent / "data"
CUTOFF   = (date.today() - timedelta(days=4 * 365)).isoformat()  # 4 years back
DRY_RUN  = "--dry-run" in sys.argv

DEST_DIR.mkdir(exist_ok=True)

def trim_list(items, date_key):
    if not items:
        return items
    return [x for x in items if str(x.get(date_key, ""))[:10] >= CUTOFF]

files = sorted(SRC_DIR.glob("backtest_*.json"))
print(f"Cutoff: {CUTOFF}  |  Files: {len(files)}  |  Dry-run: {DRY_RUN}\n")

total_before = total_after = 0
for path in files:
    size_before = path.stat().st_size
    total_before += size_before
    data = json.loads(path.read_text(encoding="utf-8"))

    data["ohlcv_w"]  = trim_list(data.get("ohlcv_w",  []), "d")
    data["ohlcv_d"]  = trim_list(data.get("ohlcv_d",  []), "d")
    data["ohlcv_4h"] = trim_list(data.get("ohlcv_4h", []), "d")
    if isinstance(data.get("top20Hist"), list):
        data["top20Hist"] = trim_list(data["top20Hist"], "d")

    out = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    size_after = len(out)
    total_after += size_after

    pct = 100 * size_after / size_before
    print(f"{path.name:40s}  {size_before/1e6:6.2f} MB -> {size_after/1e6:6.2f} MB  ({pct:.0f}%)")

    if not DRY_RUN:
        (DEST_DIR / path.name).write_bytes(out)

print(f"\nTotal: {total_before/1e6:.1f} MB -> {total_after/1e6:.1f} MB  ({100*total_after/total_before:.0f}%)")
if DRY_RUN:
    print("Dry-run — no files written.")
