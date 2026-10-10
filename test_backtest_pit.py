"""Tests für die zeitpunktgenaue Backtest-Logik (frontend/backtest_logic.js)."""
import json
import subprocess

SNIPPET = """
const fs = require('fs'), vm = require('vm');
vm.runInThisContext(fs.readFileSync('frontend/backtest_logic.js', 'utf8'));
const out = {
  sat: weekOfBar('2026-10-03'), mon: weekOfBar('2026-10-05'),
  blocks: ['2026-10-06 10:00', '2026-10-06 13:00', '2026-10-06 18:00', '2026-10-06 22:00'].map(h4Block),
  weekly: normalizeWeekly([
    { d: '2026-09-21', o: 1, h: 5, l: 1, c: 4 },
    { d: '2026-09-22', o: 4, h: 6, l: 2, c: 3 },
    { d: '2026-09-28', o: 3, h: 4, l: 3, c: 4 },
  ]),
  merged: mergeSeries(
    { ohlcv_w: [{ d: '2026-09-26', o: 1, h: 2, l: 1, c: 2 }],
      ohlcv_d: [{ d: '2026-10-01', o: 1, h: 2, l: 1, c: 10 }, { d: '2026-10-02', o: 1, h: 2, l: 1, c: 10 }],
      ohlcv_4h: [{ d: '2026-10-02 10:00', o: 1, h: 2, l: 1, c: 10 }] },
    { ohlcv_w: [{ d: '2026-09-28', o: 2, h: 3, l: 2, c: 3 }],
      ohlcv_d: [{ d: '2026-10-02', o: 2, h: 3, l: 2, c: 20 }, { d: '2026-10-05', o: 2, h: 3, l: 2, c: 21 }],
      ohlcv_4h: [{ d: '2026-10-05 10:00', o: 2, h: 3, l: 2, c: 21 }] }),
};
console.log(JSON.stringify(out));
"""


def run():
    return json.loads(subprocess.run(["node", "-e", SNIPPET], capture_output=True, text=True, check=True).stdout)


def test_weekly_labels_saturday_and_monday_map_to_same_week():
    out = run()
    assert out["sat"] == out["mon"] == "2026-10-05"


def test_h4_blocks_follow_berlin_bar_start_incl_shifted_dst():
    assert run()["blocks"] == [0, 1, 2, 3]


def test_duplicate_weekly_rows_are_combined():
    weekly = run()["weekly"]
    assert [w["d"] for w in weekly] == ["2026-09-21", "2026-09-28"]
    assert weekly[0] == {"d": "2026-09-21", "o": 1, "h": 6, "l": 1, "c": 3}


def test_merge_rescales_history_after_split_and_prefers_live_overlap():
    m = run()["merged"]
    assert [b["d"] for b in m["ohlcv_d"]] == ["2026-10-01", "2026-10-02", "2026-10-05"]
    assert m["ohlcv_d"][0]["c"] == 20            # Historie ×2 (Split seit dem historischen Lauf)
    assert m["ohlcv_d"][1]["c"] == 20            # Überlappung aus den täglichen Kursen
    assert [w["d"] for w in m["ohlcv_w"]] == ["2026-09-28"]
