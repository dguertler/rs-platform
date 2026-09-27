"""
Tests für index_membership.py — rückwirkendes Top-20-Ranking nur unter den
damaligen Indexmitgliedern (NASDAQ-100 und S&P 500).

Aufruf: python3 -m pytest test_index_membership.py -q
"""
import json

import numpy as np
import pandas as pd

import index_membership as im


def test_apply_official_adds_and_closes_members():
    intervals = {"A": [["2020-01-01", None]], "B": [["2020-01-01", None]], "C": [["2019-01-01", "2021-01-01"]]}
    official = ["A", "C"] + [f"X{i}" for i in range(im.MIN_OFFICIAL)]
    out = im.apply_official(intervals, official, as_of="2026-09-01")
    assert out["A"] == [["2020-01-01", None]]
    assert out["B"] == [["2020-01-01", "2026-09-01"]]           # nicht mehr offiziell → endet
    assert out["C"] == [["2019-01-01", "2021-01-01"], ["2026-09-01", None]]
    assert out["X0"] == [["2026-09-01", None]]
    assert intervals["B"] == [["2020-01-01", None]]             # Eingabe unverändert


def test_apply_official_ignores_incomplete_list():
    intervals = {"A": [["2020-01-01", None]]}
    assert im.apply_official(intervals, ["B"], as_of="2026-09-01") == intervals


def test_active_in_window_and_current_members():
    intervals = {"OLD": [["2010-01-01", "2020-01-01"]], "LEFT": [["2010-01-01", "2025-06-01"]],
                 "NOW": [["2024-01-01", None]]}
    assert im.active_in_window(intervals, "2024-09-01") == ["LEFT", "NOW"]
    assert im.current_members(intervals) == ["NOW"]


def test_load_intervals_maps_renamed_symbols(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"intervals": {"FB": [["2012-12-12", "2022-06-09"]],
                                              "META": [["2022-06-09", None]]}}))
    iv = im.load_intervals(str(path))
    assert iv == {"META": [["2012-12-12", "2022-06-09"], ["2022-06-09", None]]}
    assert im.load_intervals(str(tmp_path / "fehlt.json")) is None


def test_watchlist_extras(tmp_path, monkeypatch):
    wl = tmp_path / "w.json"
    wl.write_text(json.dumps({"tickers": ["NTRA", "MSFT"]}))
    monkeypatch.setattr(im, "WATCHLIST_FILE", str(wl))
    assert im.watchlist_extras({"MSFT"}) == ["NTRA"]


def test_point_in_time_top20_ranks_only_members():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2024-01-01", periods=300)
    data = {f"T{k:02d}": 50 * np.exp(np.cumsum(rng.normal(0.001 * k, 0.02, 300))) for k in range(30)}
    data["BM"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))
    close = pd.DataFrame(data, index=idx)
    day_cut = idx[150].strftime("%Y-%m-%d")
    intervals = {f"T{k:02d}": [["2020-01-01", None]] for k in range(25)}
    intervals["T29"] = [["2020-01-01", day_cut]]            # stärkster Titel, scheidet aus
    history, prev_rank = im.point_in_time_top20(close, "BM", intervals)
    assert history and prev_rank
    for day, top in history.items():
        assert len(top) == 20
        assert all(t in intervals for t in top)               # T25–T28 nie Mitglied
        if day >= day_cut:
            assert "T29" not in top
    assert any("T29" in top for day, top in history.items() if day < day_cut)
    assert "T29" not in prev_rank
