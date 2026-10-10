"""Tests für den 4H-Prüfjob (check_alerts_4h.py)."""
from datetime import datetime, timedelta, timezone

import check_alerts_4h as job


def test_bar_times_berlin_labels_match_tradingview():
    start, end = job.bar_times("2026-10-06 14:00")       # Sommerzeit: 14 Uhr Berlin = 8 Uhr New York
    assert start == datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    assert end - start == timedelta(hours=4)


def test_complete_bars_drops_running_bar():
    rows = [{"d": "2026-10-06 10:00"}, {"d": "2026-10-06 14:00"}]
    now = datetime(2026, 10, 6, 12, 20, tzinfo=timezone.utc)   # 10–14-Kerze seit 14:00 zu, 16 Min. Verzug
    assert [r["d"] for r in job.complete_bars(rows, now)] == ["2026-10-06 10:00"]
    assert job.complete_bars(rows, now - timedelta(minutes=10)) == []


def test_with_today_extends_daily_and_weekly():
    entry = {"ohlcv": [{"d": "2026-10-05", "o": 1, "h": 2, "l": 1, "c": 2}],
             "ohlcv_w": [{"d": "2026-10-05", "o": 1, "h": 2, "l": 1, "c": 2}]}
    today = {"d": "2026-10-06", "o": 2, "h": 5, "l": 0.5, "c": 4}
    daily, weekly = job.with_today(entry, today)
    assert daily[-1] == today and len(daily) == 2
    assert weekly[-1] == {"d": "2026-10-05", "o": 1, "h": 5, "l": 0.5, "c": 4}
    assert entry["ohlcv_w"][-1]["h"] == 2                     # Original unverändert


def test_evaluate_ignores_bars_outside_buy_window():
    rows = [{"d": f"2026-10-0{d} {h}", "o": 1, "h": 1, "l": 1, "c": 1}
            for d in range(1, 7) for h in ("10:00", "14:00", "18:00")]
    now = datetime(2026, 10, 6, 20, 20, tzinfo=timezone.utc)  # Kerze 18–22 Uhr gerade zu → Nachtlauf
    assert job.evaluate({"ohlcv": [], "ohlcv_w": []}, {"h4": rows, "today": None}, now) is None
