"""
Prüft, dass update_backtest_daily.merge_4h das neu geladene 4H-Fenster sauber
einsetzt statt zwei 4H-Raster übereinanderzulegen (Fehler Sept. 2024 – Mai 2026).

Aufruf: python3 -m pytest test_update_backtest_4h.py -q
"""
from update_backtest_daily import merge_4h


def row(d, c=1.0):
    return {"d": d, "o": c, "h": c, "l": c, "c": c}


def test_mixed_grid_is_replaced_by_new_window():
    old = [row("2024-09-26 05:30"), row("2024-09-26 10:00"), row("2024-09-26 13:30"), row("2024-09-26 14:00"),
           row("2024-09-27 10:00")]
    new = [row("2024-09-26 10:00", 2), row("2024-09-26 14:00", 2), row("2024-09-27 10:00", 2)]
    assert merge_4h(old, new) == new


def test_older_rows_kept_only_on_current_grid():
    old = [row("2024-09-20 05:30"), row("2024-09-20 10:00"), row("2024-09-26 10:00")]
    new = [row("2024-09-26 10:00", 2)]
    assert merge_4h(old, new) == [row("2024-09-20 10:00"), row("2024-09-26 10:00", 2)]


def test_empty_fetch_keeps_existing_rows():
    old = [row("2024-09-20 10:00")]
    assert merge_4h(old, []) == old
