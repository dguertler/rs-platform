"""
build_static_api.py — erzeugt die "RS-Platform 2.0"-Payloads als statische
JSON-Dateien für GitHub Pages.

Vorher berechnete das FastAPI-Backend (/api/v2/{market}, /api/v2/backtest/{market})
das bei jedem Request live aus data/rs_*.json + data/fundamentals.json +
data/earnings_calendar.json. Ohne Backend übernimmt dieses Skript den Job
einmal beim Deploy (siehe .github/workflows/deploy-pages.yml) und schreibt
das Ergebnis nach data/v2_{market}.json bzw. data/v2_backtest_{market}.json,
von wo die Frontend-Seiten (v2.html) es statisch laden.

Usage:
    python3 build_static_api.py [--data-dir data] [--out-dir data]
"""
import argparse
import json
from pathlib import Path

from v2_analysis import build_v2_payload

MARKET_FILES = {
    "nasdaq": "rs_full.json",
    "sp500": "rs_sp500.json",
    "dax": "rs_dax.json",
    "smallcap": "rs_smallcap.json",
}


def _load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_v2(data_dir: Path, out_dir: Path) -> None:
    fund_path = data_dir / "fundamentals.json"
    earnings_path = data_dir / "earnings_calendar.json"
    fund = _load(fund_path).get("tickers", {}) if fund_path.exists() else {}
    earnings_map = _load(earnings_path).get("next_earnings", {}) if earnings_path.exists() else {}

    for market, filename in MARKET_FILES.items():
        path = data_dir / filename
        if not path.exists():
            print(f"[build_static_api] SKIP v2_{market}.json: {path} fehlt")
            continue
        raw = _load(path)
        payload = build_v2_payload(raw, fund, market, earnings_map=earnings_map)
        out_path = out_dir / f"v2_{market}.json"
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        print(f"[build_static_api] {out_path} geschrieben")


def build_v2_backtest(repo_root: Path, out_dir: Path) -> None:
    results_dir = repo_root / "backtest_v2" / "results"
    if not results_dir.exists():
        print("[build_static_api] SKIP v2_backtest_*.json: backtest_v2/results fehlt")
        return
    for market in MARKET_FILES:
        candidates = sorted(results_dir.glob(f"{market}_*.json"), reverse=True)
        if not candidates:
            continue
        out_path = out_dir / f"v2_backtest_{market}.json"
        out_path.write_text(candidates[0].read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[build_static_api] {out_path} geschrieben (aus {candidates[0].name})")


def main() -> None:
    repo_root = Path(__file__).parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(repo_root / "data"))
    parser.add_argument("--out-dir", default=str(repo_root / "data"))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    build_v2(data_dir, out_dir)
    build_v2_backtest(repo_root, out_dir)


if __name__ == "__main__":
    main()
