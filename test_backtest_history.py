"""
Offline-Durchlauf des historischen Backtests (backtest_history/) ohne Yahoo:
yf.download wird durch die Kurse aus data/backtest_*.json und data/rs_full.json
ersetzt, die Mitgliedschaft ist künstlich. Geprüft wird die Verdrahtung —
Symbolauflösung, Ranking nur unter Mitgliedern, Varianten inkl./exkl.,
Jahresauswertung —, nicht das Ergebnis.

Aufruf: python3 -m pytest test_backtest_history.py -q
"""
import json
import os
import subprocess
import sys

import pandas as pd
import pytest

_REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO, "backtest_history"))

import prepare_data  # noqa: E402

MEMBER_START = "2024-10-01"
DELISTED = "CTSH"          # Kursreihe wird im Test am 2025-06-30 abgeschnitten
LEFT_INDEX = "EBAY"        # Mitgliedschaft endet 2025-03-17


def _frame(rows, cols=("o", "h", "l", "c")):
    names = {"o": "Open", "h": "High", "l": "Low", "c": "Close"}
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["d"])
    return df[list(cols)].rename(columns=names)


def _load_repo_prices():
    rs = json.load(open(os.path.join(_REPO, "data", "rs_full.json")))
    daily, weekly = {}, {}
    for entry in rs["data"]:
        path = os.path.join(_REPO, "data", f"backtest_{entry['ticker'].lower()}.json")
        if not os.path.exists(path):
            continue
        bt = json.load(open(path))
        daily[entry["ticker"]] = _frame(bt["ohlcv_d"])
        weekly[entry["ticker"]] = _frame(bt["ohlcv_w"])
    daily["QQQ"] = _frame(rs["benchmark_ohlcv"])
    weekly["QQQ"] = _frame(rs["benchmark_ohlcv_w"])
    daily["^NDX"] = _frame(rs["ndx_ohlcv"], cols=("c",))
    cut = pd.Timestamp("2025-06-30")
    daily[DELISTED] = daily[DELISTED][daily[DELISTED].index <= cut]
    weekly[DELISTED] = weekly[DELISTED][weekly[DELISTED].index <= cut]
    return daily, weekly


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bth")
    daily, weekly = _load_repo_prices()
    tickers = sorted(t for t in daily if t not in ("QQQ", "^NDX", "META"))[:45]
    tickers = sorted(set(tickers) | {DELISTED, LEFT_INDEX})
    intervals = {t: [[MEMBER_START, None]] for t in tickers}
    intervals[LEFT_INDEX] = [[MEMBER_START, "2025-03-17"]]
    intervals["FB"] = [[MEMBER_START, "2025-01-15"]]        # Alias → META
    intervals["META"] = [["2025-01-15", None]]
    intervals["ZZZZ"] = [[MEMBER_START, None]]              # keine Kursdaten
    membership = {"source": "test", "start": MEMBER_START, "intervals": intervals}
    mfile = tmp / "membership.json"
    mfile.write_text(json.dumps(membership))

    def fake_download(symbols, start=None, end=None, interval="1d", group_by=None, **_):
        src = daily if interval == "1d" else weekly
        if isinstance(symbols, str):
            if symbols not in src:
                return pd.DataFrame()
            return src[symbols].copy()
        present = [s for s in symbols if s in src]
        if not present:
            return pd.DataFrame()
        return pd.concat({s: src[s] for s in present}, axis=1)

    orig = (prepare_data.MEMBERSHIP_FILE, prepare_data.CACHE_DIR, prepare_data.yf.download)
    prepare_data.MEMBERSHIP_FILE = str(mfile)
    prepare_data.CACHE_DIR = str(tmp / "cache")
    prepare_data.yf.download = fake_download
    try:
        prepare_data.main()
    finally:
        prepare_data.MEMBERSHIP_FILE, prepare_data.CACHE_DIR, prepare_data.yf.download = orig

    out = tmp / "results.json"
    env = {**os.environ, "BACKTEST_HISTORY_CACHE": str(tmp / "cache"), "BACKTEST_HISTORY_OUT": str(out)}
    subprocess.run(["node", os.path.join(_REPO, "backtest_history", "run_backtest.js")],
                   check=True, env=env, capture_output=True)
    cache = tmp / "cache"
    return {
        "meta": json.loads((cache / "meta.json").read_text()),
        "top20_inkl": json.loads((cache / "top20_inkl.json").read_text()),
        "top20_exkl": json.loads((cache / "top20_exkl.json").read_text()),
        "results": json.loads(out.read_text()),
        "intervals": intervals,
    }


def test_symbol_resolution(pipeline):
    res = pipeline["meta"]["resolution"]
    assert res["ZZZZ"]["status"] == "keine_daten"
    assert res["FB"]["yahoo"] == "META" and res["FB"]["status"] == "aktiv"
    assert res[DELISTED]["status"] == "delisted_mit_daten"
    assert res[LEFT_INDEX]["status"] == "aktiv"


def test_ranking_only_among_members(pipeline):
    for day, top in pipeline["top20_inkl"].items():
        assert day >= MEMBER_START
        assert len(top) == 20
        if day >= "2025-03-17":
            assert LEFT_INDEX not in top
    assert all(DELISTED not in top for top in pipeline["top20_exkl"].values())


def test_meta_membership_for_renamed_symbol(pipeline):
    # FB (bis 2025-01-15) und META (ab dann) laufen auf dieselbe Yahoo-Reihe
    days = [d for d, top in pipeline["top20_inkl"].items() if "META" in top]
    assert all(d >= MEMBER_START for d in days)


def test_results_per_year_and_variants(pipeline):
    r = pipeline["results"]
    assert set(r["variants"]) == {"inkl", "exkl"}
    inkl = r["variants"]["inkl"]
    assert inkl["trades"], "keine Trades simuliert"
    for t in inkl["trades"]:
        assert t["trigger"] in ("D", "W")
        top = pipeline["top20_inkl"].get(t["entryDate"])
        if top is not None:                  # Engine prüft zuerst den Einstiegstag
            assert t["ticker"] in top
    years = {t["entryDate"][:4] for t in inkl["trades"]}
    assert years == set(inkl["years"])
    assert sum(v["nTrades"] for v in inkl["years"].values()) == len(inkl["trades"])
    assert all(t["ticker"] != DELISTED for t in r["variants"]["exkl"]["trades"])
    assert "2025" in r["ndx"] and "pct" in r["ndx"]["2025"]
    assert r["symbols"]["keineDaten"] == 1
    assert "ZZZZ" in r["coverage"]["2025"]["missing"]
    assert r["calibration"]["modes"]["4H"]["total"]["nTrades"] > 0
