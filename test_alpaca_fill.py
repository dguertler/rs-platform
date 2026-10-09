"""
Prüft den Alpaca-Ersatz für Indexmitglieder, die Yahoo nicht mehr führt
(backtest_history/prepare_data.alpaca_fill, backtest_history/alpaca.py).

Aufruf: python3 -m pytest test_alpaca_fill.py -q
"""
import os
import sys

import pandas as pd

_REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO, "backtest_history"))

import alpaca                                    # noqa: E402
from prepare_data import alpaca_fill             # noqa: E402


def _frame(start, end, price=10.0):
    idx = pd.bdate_range(start, end)
    return pd.DataFrame({"Open": price, "High": price + 1, "Low": price - 1, "Close": price}, index=idx)


def _res(ivs):
    return {"yahoo": None, "accepted": [], "rejected": ivs, "status": "keine_daten"}


def test_fills_delisted_member_from_2016_and_keeps_old_gaps():
    resolution = {
        "ATVI": _res([["2007-02-01", "2023-10-16"]]),     # übernommen 2023
        "DTV": _res([["2007-02-01", "2015-07-27"]]),      # vor 2016 weg → bleibt offen
        "WBD": _res([["2022-12-19", None]]),              # Yahoo führt die Aktie nicht mehr
    }
    daily, yahoo_intervals = {}, {}
    frames = {"ATVI": _frame("2016-01-04", "2023-10-13"), "WBD": _frame("2016-01-04", "2026-10-06")}
    asked = []

    def fetch(symbols):
        asked.extend(symbols)
        return {s: frames[s] for s in symbols if s in frames}

    sources = alpaca_fill(resolution, yahoo_intervals, daily, fetch)
    assert "DTV" not in asked                                   # Zeitraum endet vor Alpaca
    assert set(sources) == {"ATVI", "WBD"}
    assert yahoo_intervals["ATVI"] == [["2016-01-04", "2023-10-16"]]
    assert yahoo_intervals["WBD"] == [["2022-12-19", None]]
    assert resolution["ATVI"]["source"] == "alpaca" and "status" not in resolution["ATVI"]
    assert resolution["DTV"]["status"] == "keine_daten"
    assert sources["WBD"]["query"] == "WBD" and daily["WBD"].index[-1] == pd.Timestamp("2026-10-06")


def test_reused_ticker_gets_own_name_and_is_cut_at_membership_end():
    # Yahoo führt unter SNDK die neue Sandisk (ab 2025); die alte lief bis 2016
    daily = {"SNDK": _frame("2025-02-24", "2026-10-08", 50.0)}
    resolution = {"SNDK": {"yahoo": "SNDK", "accepted": [["2025-11-24", None]],
                           "rejected": [["2007-02-01", "2016-05-12"]]}}
    yahoo_intervals = {"SNDK": [["2025-11-24", None]]}
    old_and_new = pd.concat([_frame("2016-01-04", "2016-05-12", 70.0), _frame("2025-02-24", "2026-10-08", 50.0)])
    sources = alpaca_fill(resolution, yahoo_intervals, daily, lambda syms: {"SNDK": old_and_new})
    assert list(sources) == ["SNDK_2016"]
    assert sources["SNDK_2016"] == {"query": "SNDK", "from": "2016-01-04", "to": "2016-05-12"}
    assert daily["SNDK_2016"].index[-1] == pd.Timestamp("2016-05-12")
    assert daily["SNDK"].index[0] == pd.Timestamp("2025-02-24")       # Yahoo-Reihe unverändert
    assert yahoo_intervals["SNDK_2016"] == [["2016-01-04", "2016-05-12"]]
    assert resolution["SNDK"]["yahoo"] == "SNDK" and resolution["SNDK"]["rejected"] == []


def test_alpaca_daily_and_weekly_frames():
    bars = [{"t": "2016-01-04T05:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5},
            {"t": "2016-01-05T05:00:00Z", "o": 1.5, "h": 2.5, "l": 1, "c": 2},
            {"t": "2016-01-11T05:00:00Z", "o": 2, "h": 3, "l": 1.5, "c": 2.5}]
    d = alpaca.daily_frame(bars)
    assert [x.strftime("%Y-%m-%d") for x in d.index] == ["2016-01-04", "2016-01-05", "2016-01-11"]
    w = alpaca.weekly_from_daily(d)
    assert [x.strftime("%Y-%m-%d") for x in w.index] == ["2016-01-04", "2016-01-11"]   # Montage
    assert w.iloc[0].tolist() == [1, 2.5, 0.5, 2]
