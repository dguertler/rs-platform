"""Wächter für die Strategie-Loops: Wie viel Vorsprung vor QQQ ist bei N getesteten Varianten echt?

Grundidee (Bailey/López de Prado „Deflated Sharpe Ratio“, Harvey/Liu „Haircut“):
Wer N Varianten testet und die beste nimmt, findet auch ohne echten Vorteil einen positiven
Vorsprung. Gemessen wird deshalb der Vorsprung GEGEN QQQ (aktive Tagesrendite = Strategie − QQQ)
und gefragt, ob er die Erwartung des Maximums aus N Zufallsversuchen übersteigt.

    import sys; sys.path.insert(0, ".../scratchpad/loop/quant")
    from guard import guard, effective_trials, pf_ci
    g = guard(eq_strategy, eq_qqq, n_trials=TESTS_TOTAL)          # Serien mit Datumsindex
    print(g["verdict"], g["dsr"], g["excess_cagr_haircut"])

Kennzahlen:
  ir_ann          Information Ratio p. a. der aktiven Rendite (Strategie − QQQ, täglich)
  excess_cagr     CAGR(Strategie) − CAGR(QQQ) in Prozentpunkten
  sr0_ann         Erwartetes Maximum der IR aus n_trials Versuchen ohne Vorteil (Schwelle)
  dsr             Deflated Sharpe: P(echte IR > 0 | n_trials Versuche), korrigiert um Schiefe/Wölbung
  excess_cagr_haircut  Vorsprung nach Bonferroni-Haircut der t-Statistik (≤ 0 → nicht belegt)
  verdict         "echt" (dsr ≥ 0,95), "Hinweis" (0,80–0,95), "Rauschen" (< 0,80)

n_trials: ALLE bisher getesteten Varianten aller Loops zählen (auch verworfene). Sind die
Varianten stark korreliert, mit effective_trials(...) die effektive Zahl schätzen.
Nur numpy/pandas (scipy ist nicht installiert).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

EULER_GAMMA = 0.5772156649015329
DAYS = 252


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_ppf(p: float) -> float:
    """Inverse Normalverteilung (Bisektion, genau genug für Schwellen)."""
    p = min(max(p, 1e-12), 1 - 1e-12)
    lo, hi = -12.0, 12.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def expected_max_sharpe(n_trials: float, sr_std: float) -> float:
    """Erwartetes Maximum von n_trials Sharpe-Schätzungen mit Mittel 0 und Streuung sr_std."""
    if n_trials <= 1:
        return 0.0
    return sr_std * ((1 - EULER_GAMMA) * norm_ppf(1 - 1 / n_trials)
                     + EULER_GAMMA * norm_ppf(1 - 1 / (n_trials * math.e)))


def effective_trials(returns: pd.DataFrame) -> float:
    """Effektive Zahl unabhängiger Versuche aus den Tagesrenditen aller getesteten Varianten
    (Spalten): N_eff = ρ̄ + (1 − ρ̄)·N  (ρ̄ = mittlere paarweise Korrelation)."""
    n = returns.shape[1]
    if n <= 1:
        return float(n)
    c = returns.corr().values
    rho = (c.sum() - n) / (n * (n - 1))
    return float(rho + (1 - rho) * n)


def _active(eq: pd.Series, eq_bench: pd.Series) -> pd.Series:
    df = pd.concat([eq, eq_bench], axis=1, join="inner").dropna()
    r = df.pct_change().dropna()
    return r.iloc[:, 0] - r.iloc[:, 1]


def _cagr(eq: pd.Series) -> float:
    eq = eq.dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1


def guard(eq: pd.Series, eq_bench: pd.Series, n_trials: int, trial_sharpes: list | None = None) -> dict:
    """Bewertet den Vorsprung einer Equity-Kurve vor dem Benchmark bei n_trials getesteten Varianten.

    trial_sharpes: optional die (täglichen, nicht annualisierten) IR aller getesteten Varianten,
    um ihre Streuung zu schätzen. Ohne Angabe gilt die Streuung unter der Nullhypothese 1/sqrt(T).
    """
    a = _active(eq, eq_bench)
    T = len(a)
    sd = a.std()
    sr = a.mean() / sd if sd > 0 else 0.0                      # tägliche IR
    skew = float(((a - a.mean()) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    kurt = float(((a - a.mean()) ** 4).mean() / sd ** 4) if sd > 0 else 3.0
    sr_std = float(np.std(trial_sharpes, ddof=1)) if trial_sharpes and len(trial_sharpes) > 2 else 1 / math.sqrt(T)
    sr0 = expected_max_sharpe(n_trials, sr_std)
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr ** 2, 1e-12))
    psr0 = norm_cdf(sr * math.sqrt(T - 1) / denom)              # ohne Mehrfachtest-Korrektur
    dsr = norm_cdf((sr - sr0) * math.sqrt(T - 1) / denom)       # mit Korrektur
    # Haircut (Bonferroni) auf die t-Statistik → Vorsprung skalieren
    t = sr * math.sqrt(T)
    p = 2 * (1 - norm_cdf(abs(t)))
    p_adj = min(1.0, p * max(n_trials, 1))
    t_adj = norm_ppf(1 - p_adj / 2) if p_adj < 1 else 0.0
    shrink = max(t_adj, 0.0) / t if t > 0 else 0.0
    excess = (_cagr(eq) - _cagr(eq_bench)) * 100
    verdict = "echt" if dsr >= 0.95 else "Hinweis" if dsr >= 0.80 else "Rauschen"
    return {"n_trials": n_trials, "days": T, "ir_ann": sr * math.sqrt(DAYS), "t_stat": t,
            "excess_cagr": excess, "sr0_ann": sr0 * math.sqrt(DAYS), "psr": psr0, "dsr": dsr,
            "p_raw": p, "p_bonf": p_adj, "excess_cagr_haircut": excess * shrink if excess > 0 else excess,
            "skew": skew, "kurt": kurt, "verdict": verdict}


def pf_ci(trades: list, B: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Profitfaktor (in €) mit 95-%-Intervall, Bootstrap nach Einstiegsmonat (Trades desselben Monats
    sind nicht unabhängig). trades = Liste von dicts mit 'pnl' und 'entry' (YYYY-MM-DD)."""
    if not trades:
        return float("nan"), float("nan"), float("nan")
    pnl = np.array([t["pnl"] for t in trades], float)
    mon = np.array([t["entry"][:7] for t in trades])
    groups = [np.where(mon == u)[0] for u in np.unique(mon)]
    pf = lambda x: x[x > 0].sum() / -x[x <= 0].sum() if (x <= 0).any() and x[x <= 0].sum() < 0 else float("inf")
    rng = np.random.default_rng(seed)
    bs = [pf(pnl[np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))])]) for _ in range(B)]
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return pf(pnl), float(lo), float(hi)


def report(name: str, g: dict) -> str:
    return (f"{name}: Vorsprung {g['excess_cagr']:+.1f} Pkt p. a., IR {g['ir_ann']:.2f} (t {g['t_stat']:.2f}), "
            f"Schwelle bei N={g['n_trials']}: IR {g['sr0_ann']:.2f} → DSR {g['dsr']:.2f} ({g['verdict']}), "
            f"Vorsprung nach Haircut {g['excess_cagr_haircut']:+.1f} Pkt")
