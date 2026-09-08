"""test_earnings_gate.py — Regressionstests für die Earnings-Alert-Schwellen.

Läuft ohne Netzwerk und ohne yfinance:  python3 -m unittest test_earnings_gate

Die Testfälle sind echte Quartalsmeldungen, keine erfundenen Zahlen — sie
halten fest, welche Meldungen das Gate passieren müssen und welche nicht.
"""

import unittest

from earnings_gate import (
    TRIGGER_EPS_BEAT, TRIGGER_PRICE_REACTION,
    detect_eps_oneoff, evaluate_gate,
)


class TestPriceReactionTrigger(unittest.TestCase):
    """Mega-Caps: Kursreaktion als Auslöser, wo die EPS-Surprise strukturell klein ist."""

    def test_msft_fq4_2026_passiert_ueber_eps_beat(self):
        # 29.07.2026: EPS 4,74 $ vs. 4,24 $ erwartet, +15,5 % am Folgetag
        result = evaluate_gate(jump=0.155, surprise_pct=11.8,
                               revenue_growth_yoy=0.18, rs_tracked=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.trigger, TRIGGER_EPS_BEAT)

    def test_amzn_q2_2026_passiert_ueber_kursreaktion(self):
        # 30.07.2026: bereinigt 1,97 $ vs. 1,86 $ = +6,1 % — unter der EPS-Schwelle,
        # aber +15,3 % Kursreaktion. Vor dem Kursreaktions-Trigger fiel AMZN raus.
        result = evaluate_gate(jump=0.153, surprise_pct=6.1,
                               revenue_growth_yoy=0.20, rs_tracked=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.trigger, TRIGGER_PRICE_REACTION)

    def test_pltr_q2_2026_passiert_ueber_eps_beat(self):
        # 03.08.2026: EPS 0,41 $ vs. 0,28 $, +29,5 % am Folgetag
        result = evaluate_gate(jump=0.295, surprise_pct=46.4,
                               revenue_growth_yoy=0.93, rs_tracked=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.trigger, TRIGGER_EPS_BEAT)

    def test_kursreaktion_nur_fuer_rs_getrackte_titel(self):
        # Derselbe Sprung bei einem nicht getrackten Micro-Cap → kein Alert,
        # sonst flutet jeder 8-%-Sprung im 6000-Ticker-Universum den Scan.
        result = evaluate_gate(jump=0.153, surprise_pct=6.1,
                               revenue_growth_yoy=0.20, rs_tracked=False)
        self.assertFalse(result.passed)

    def test_kursreaktion_greift_nicht_bei_kursverlust(self):
        # MRNA Q2 2026 (31.07.2026): −5,35 % Kursreaktion, Surprise +3,0 %
        result = evaluate_gate(jump=-0.0535, surprise_pct=3.0,
                               revenue_growth_yoy=0.021, rs_tracked=True)
        self.assertFalse(result.passed)


class TestOneOffDetection(unittest.TestCase):
    """Einmaleffekte dürfen keine Surprise vortäuschen — echte Turnarounds schon."""

    def test_amzn_gaap_eps_wird_als_einmaleffekt_erkannt(self):
        # GAAP-EPS 5,75 $ enthält 53,4 Mrd. $ Anthropic-Neubewertung,
        # Vorquartale lagen bei ~1,7–2,1 $, Umsatz +20 % YoY.
        self.assertTrue(detect_eps_oneoff(
            eps_actual=5.75, prior_eps=[2.05, 1.86, 1.68, 1.43],
            revenue_growth_yoy=0.20))

    def test_verzerrte_surprise_loest_keinen_eps_beat_aus(self):
        result = evaluate_gate(jump=0.153, surprise_pct=209.0,
                               revenue_growth_yoy=0.20,
                               eps_distorted=True, rs_tracked=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.trigger, TRIGGER_PRICE_REACTION,
                         "Alert muss über die Kursreaktion kommen, nicht über die "
                         "verzerrte Surprise")
        self.assertNotIn("209.0", result.reason,
                         "Die verzerrte Surprise darf in der Begründung nicht "
                         "als Kennzahl auftauchen")

    def test_verzerrte_surprise_ohne_kursreaktion_faellt_raus(self):
        result = evaluate_gate(jump=0.06, surprise_pct=209.0,
                               revenue_growth_yoy=0.20,
                               eps_distorted=True, rs_tracked=True)
        self.assertFalse(result.passed)
        self.assertIn("Einmaleffekt", result.reason)

    def test_cnc_turnaround_gilt_nicht_als_einmaleffekt(self):
        # Referenzmuster aus CLAUDE.md: Q4 25 EPS −1,16 $ → Q1 26 EPS 3,37 $.
        # Verlustquartal in der Historie → Turnaround-Muster, kein Einmaleffekt.
        self.assertFalse(detect_eps_oneoff(
            eps_actual=3.37, prior_eps=[-1.16, 0.86, 1.62, 2.16],
            revenue_growth_yoy=0.15))

    def test_hyperwachstum_gilt_nicht_als_einmaleffekt(self):
        # EPS-Sprung, der vom Umsatz getragen wird (YoY ≥ 100 %)
        self.assertFalse(detect_eps_oneoff(
            eps_actual=0.60, prior_eps=[0.18, 0.15, 0.13, 0.11],
            revenue_growth_yoy=1.40))

    def test_ohne_historie_keine_verzerrung(self):
        self.assertFalse(detect_eps_oneoff(eps_actual=5.75, prior_eps=[],
                                           revenue_growth_yoy=0.20))


class TestBestehendeSchwellen(unittest.TestCase):
    """Das bisherige Verhalten bleibt für Small-/Midcaps unverändert."""

    def test_bbcp_klassischer_eps_beat(self):
        # 04.09.2026: Surprise +38,1 %, Sprung +16,0 %, nicht RS-getrackt
        result = evaluate_gate(jump=0.160, surprise_pct=38.1,
                               revenue_growth_yoy=0.13, rs_tracked=False)
        self.assertTrue(result.passed)
        self.assertEqual(result.trigger, TRIGGER_EPS_BEAT)

    def test_umsatzeinbruch_vetot_auch_bei_grossem_beat(self):
        result = evaluate_gate(jump=0.20, surprise_pct=50.0,
                               revenue_growth_yoy=-0.12, rs_tracked=True)
        self.assertFalse(result.passed)
        self.assertIn("Umsatz", result.reason)

    def test_umsatzeinbruch_vetot_auch_die_kursreaktion(self):
        result = evaluate_gate(jump=0.20, surprise_pct=2.0,
                               revenue_growth_yoy=-0.12, rs_tracked=True)
        self.assertFalse(result.passed)

    def test_fehlende_umsatzdaten_blockieren_nicht(self):
        result = evaluate_gate(jump=0.09, surprise_pct=2.0,
                               revenue_growth_yoy=None, rs_tracked=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.trigger, TRIGGER_PRICE_REACTION)


if __name__ == "__main__":
    unittest.main()
