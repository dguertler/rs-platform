"""test_split_detection.py — Regressionstests für die Split-Erkennung.

Läuft ohne Netzwerk:  python3 -m unittest test_split_detection

Die Testfälle sind echte Vorkommnisse aus data/backtest_*.json, keine
erfundenen Zahlen: KLAC (10:1 am 18.05.2026) und CRWD (4:1 am 01.07.2026)
sind unbereinigte Splits, MRNA (+84 % am 19.08.2026) ist eine echte
Kursbewegung, die nicht als Split behandelt werden darf.
"""

import unittest

from repair_backtest_splits import find_jumps, is_genuine_move
from update_backtest_daily import scale_drift


def bar(date, close, open_=None):
    return {"d": date, "o": open_ if open_ is not None else close,
            "h": close, "l": close, "c": close}


class TestScaleDrift(unittest.TestCase):
    """scale_drift vergleicht gespeicherte mit frisch geladenen Kerzen."""

    def test_ohne_split_kein_drift(self):
        stored = [bar("2026-09-14", 100.0), bar("2026-09-15", 101.0), bar("2026-09-16", 102.0)]
        fresh = [bar("2026-09-14", 100.0), bar("2026-09-15", 101.0), bar("2026-09-16", 102.0)]
        self.assertAlmostEqual(scale_drift(stored, fresh), 1.0, places=6)

    def test_klac_10_zu_1_split_wird_erkannt(self):
        # Bestand unbereinigt (~1800), frischer Abruf bereinigt (~180)
        stored = [bar("2026-05-13", 1795.0), bar("2026-05-14", 1800.0), bar("2026-05-15", 1804.32)]
        fresh = [bar("2026-05-13", 179.5), bar("2026-05-14", 180.0), bar("2026-05-15", 180.43)]
        drift = scale_drift(stored, fresh)
        self.assertLess(abs(drift - 0.1), 0.001)

    def test_zu_wenig_ueberlappung_gibt_none(self):
        stored = [bar("2026-09-14", 100.0), bar("2026-09-15", 101.0)]
        fresh = [bar("2026-09-16", 102.0), bar("2026-09-17", 103.0)]
        self.assertIsNone(scale_drift(stored, fresh))

    def test_dividendenanpassung_bleibt_unter_der_schwelle(self):
        # Kleine Anpassungen (<1 %) dürfen kein Neuladen auslösen
        stored = [bar("2026-09-14", 100.0), bar("2026-09-15", 101.0), bar("2026-09-16", 102.0)]
        fresh = [bar("2026-09-14", 99.7), bar("2026-09-15", 100.7), bar("2026-09-16", 101.7)]
        self.assertLess(abs(scale_drift(stored, fresh) - 1.0), 0.01)


class TestJumpKlassifizierung(unittest.TestCase):
    """find_jumps findet Brüche, is_genuine_move trennt echt von Artefakt."""

    def test_findet_den_klac_bruch(self):
        rows = [bar("2026-05-15", 1804.32), bar("2026-05-18", 175.65, open_=182.09)]
        jumps = find_jumps(rows)
        self.assertEqual(len(jumps), 1)
        self.assertEqual(jumps[0]["date"], "2026-05-18")
        self.assertLess(jumps[0]["ratio"], 0.55)

    def test_normale_bewegung_ist_kein_sprung(self):
        rows = [bar("2026-09-15", 100.0), bar("2026-09-16", 108.0, open_=106.0)]
        self.assertEqual(find_jumps(rows), [])

    def test_mrna_gap_ist_echt_weil_referenz_ihn_zeigt(self):
        # 19.08.2026: 62,96 → Eröffnung 116,02. Referenz zeigt denselben Sprung.
        jump = {"date": "2026-08-19", "prev_date": "2026-08-18", "ratio": 116.02 / 62.96}
        ref = {"2026-08-18": {"o": 64.0, "c": 62.96}, "2026-08-19": {"o": 116.02, "c": 174.38}}
        self.assertIs(is_genuine_move(jump, ref), True)

    def test_klac_gap_ist_artefakt_weil_referenz_glatt_laeuft(self):
        jump = {"date": "2026-05-18", "prev_date": "2026-05-15", "ratio": 182.09 / 1804.32}
        ref = {"2026-05-15": {"o": 179.0, "c": 180.43}, "2026-05-18": {"o": 182.09, "c": 175.65}}
        self.assertIs(is_genuine_move(jump, ref), False)

    def test_ohne_referenz_nicht_entscheidbar(self):
        jump = {"date": "2023-07-12", "prev_date": "2023-07-11", "ratio": 2.164}
        self.assertIsNone(is_genuine_move(jump, {}))


if __name__ == "__main__":
    unittest.main()
