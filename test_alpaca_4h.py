"""
Prüft den Nachbau von Yahoos Stundenraster aus Alpaca-30-Minuten-Kerzen
(backtest_history/fetch_alpaca_4h.py) und die gemeinsame 4H-Bildung
(rs_core.hourly_to_4h_rows), die live und historisch dieselbe ist.

Aufruf: python3 -m pytest test_alpaca_4h.py -q
"""
import os
import sys

import pandas as pd

_REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO, "backtest_history"))

from fetch_alpaca_4h import yahoo_like_hourly   # noqa: E402
from rs_core import hourly_to_4h_rows           # noqa: E402


def _bars(day, start_et="04:00", end_et="20:00"):
    """30-Minuten-Kerzen eines Tages, Preis = laufender Zähler."""
    times = pd.date_range(f"{day} {start_et}", f"{day} {end_et}", freq="30min",
                          inclusive="left", tz="America/New_York")
    return [{"t": t.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
             "o": 100 + i, "h": 100.5 + i, "l": 99.5 + i, "c": 100.25 + i, "v": 10}
            for i, t in enumerate(times)]


def test_hourly_grid_matches_yahoo():
    h = yahoo_like_hourly(_bars("2020-03-04"))
    labels = [ts.strftime("%H:%M") for ts in h.index]
    assert labels == ["04:00", "05:00", "06:00", "07:00", "08:00", "09:00",
                      "09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30",
                      "16:00", "17:00", "18:00", "19:00"]
    # 9:00-Kerze = nur 9:00–9:30, 9:30-Kerze = 9:30–10:30, 15:30-Kerze = 15:30–16:00
    assert h.loc[h.index[5], "Volume"] == 10
    assert h.loc[h.index[6], "Volume"] == 20
    assert h.loc[h.index[12], "Volume"] == 10
    first = h.iloc[6]
    assert first["Open"] == 111 and first["Close"] == 112.25     # Kerzen 11 und 12 des Tages


def test_hourly_grid_on_dst_switch_day():
    # 08.03.2020: Umstellung auf Sommerzeit in den USA (Sonntag) — Montag danach prüfen
    h = yahoo_like_hourly(_bars("2020-03-09"))
    labels = [ts.strftime("%H:%M") for ts in h.index]
    assert "09:30" in labels and "10:30" in labels and "10:00" not in labels


def test_four_hour_blocks_like_live():
    rows = hourly_to_4h_rows(yahoo_like_hourly(_bars("2020-03-04")), decimals=4)
    # Blöcke ab Mitternacht ET: 4–8, 8–12, 12–16, 16–20 → Berliner Zeit 10/14/18/22 Uhr
    assert [r["d"] for r in rows] == ["2020-03-04 10:00", "2020-03-04 14:00",
                                      "2020-03-04 18:00", "2020-03-04 22:00"]
    assert rows[0]["o"] == 100 and rows[-1]["c"] == 100.25 + 31


def test_four_hour_blocks_fixed_across_dst():
    # Abruf über die US-Zeitumstellung (08.03.2020) hinweg: die Blöcke bleiben
    # bei 4/8/12/16 Uhr ET. In Berlin (noch Winterzeit) also 9/13/17/21 Uhr.
    bars = _bars("2020-03-05") + _bars("2020-03-09")
    rows = hourly_to_4h_rows(yahoo_like_hourly(bars), decimals=4)
    labels = [r["d"] for r in rows]
    assert labels[:4] == ["2020-03-05 10:00", "2020-03-05 14:00", "2020-03-05 18:00", "2020-03-05 22:00"]
    assert labels[4:] == ["2020-03-09 09:00", "2020-03-09 13:00", "2020-03-09 17:00", "2020-03-09 21:00"]


def test_failed_request_falls_back_to_single_symbols(tmp_path, monkeypatch):
    """Lehnt Alpaca ein Symbol ab, dürfen die anderen der Anfrage nicht verloren gehen."""
    import json
    import fetch_alpaca_4h as f4

    (tmp_path / "top20_inkl.json").write_text(json.dumps({"2020-03-04": ["AMD", "BAD", "WBD_2022"]}))
    (tmp_path / "meta.json").write_text(json.dumps({"symbols": {
        "WBD_2022": {"alpaca": {"query": "WBD", "from": "2020-01-01", "to": "2026-10-08"}}}}))
    monkeypatch.setattr(f4, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(f4, "credentials", lambda: ("k", "s"))
    monkeypatch.setattr(f4, "choose_feed", lambda *a: "sip")
    calls = []

    def fake_fetch(names, *a, **kw):
        calls.append(list(names))
        if "BAD" in names:
            raise RuntimeError("HTTP 422: invalid symbol")
        return {n: _bars("2020-03-04") for n in names}

    monkeypatch.setattr(f4, "fetch_bars", fake_fetch)
    f4.main()
    meta = json.loads((tmp_path / "h4_meta.json").read_text())
    assert set(meta["symbols"]) == {"AMD", "WBD_2022"}             # WBD_2022 über Alpaca-Symbol WBD
    assert meta["missing"] == ["BAD"] and "BAD" in meta["errors"]
    assert ["AMD", "BAD", "WBD"] in calls and ["AMD"] in calls       # erst gemeinsam, dann einzeln
