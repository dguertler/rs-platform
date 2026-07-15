"""
evaluate_signal_journal.py — Quartalsauswertung des Signal-Journals
(STRATEGIEPLAN.md Abschnitt 7).

Beantwortet die drei dort festgelegten Fragen, aber NUR wenn genug Daten
vorliegen, um überhaupt etwas Belastbares zu sagen (siehe MIN_N). Mit zu
wenig Daten lieber "noch keine Aussage möglich" als eine Scheinpräzision
aus 4 Trades.

1. Schlagen PASS-Titel die VETO-Titel? (Ø/Median Alpha-Rendite je Fenster)
2. Korreliert der Verdict-Score mit der Alpha-Rendite? (Pearson-r)
3. Funktioniert die Regime-Ampel live? (Ø Alpha je Regime)

Nutzung:
  python3 evaluate_signal_journal.py            # Menschenlesbarer Report
  python3 evaluate_signal_journal.py --json      # Für Automatisierung (Routine-Check)
"""
import json
import statistics
import sys
from pathlib import Path

JOURNAL_PATH = Path("data/signal_journal.json")
MIN_N = 30          # Mindestgröße je Vergleichsgruppe — Faustregel, keine Power-Analyse
WINDOWS = ["1w", "4w", "13w", "26w"]


def load_entries() -> list:
    if not JOURNAL_PATH.exists():
        return []
    return json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))["entries"]


def _with_alpha(entries: list, window: str) -> list:
    return [e for e in entries if e.get("fwd_alpha", {}).get(window) is not None]


def eval_pass_vs_veto(entries: list) -> dict:
    result = {}
    for w in WINDOWS:
        pool = _with_alpha(entries, w)
        pass_vals = [e["fwd_alpha"][w] for e in pool if (e.get("funnel_veto") or {}).get("decision") == "PASS"]
        veto_vals = [e["fwd_alpha"][w] for e in pool if (e.get("funnel_veto") or {}).get("decision") == "VETO"]
        sufficient = len(pass_vals) >= MIN_N and len(veto_vals) >= MIN_N
        result[w] = {
            "n_pass": len(pass_vals), "n_veto": len(veto_vals), "sufficient": sufficient,
            "pass_mean_alpha": round(statistics.mean(pass_vals), 2) if pass_vals else None,
            "veto_mean_alpha": round(statistics.mean(veto_vals), 2) if veto_vals else None,
        }
    return result


def eval_score_correlation(entries: list) -> dict:
    result = {}
    for w in WINDOWS:
        pool = [e for e in _with_alpha(entries, w) if e.get("verdict_score") is not None]
        sufficient = len(pool) >= MIN_N
        r = None
        if sufficient:
            scores = [e["verdict_score"] for e in pool]
            alphas = [e["fwd_alpha"][w] for e in pool]
            try:
                r = round(statistics.correlation(scores, alphas), 3)
            except statistics.StatisticsError:
                r = None
        result[w] = {"n": len(pool), "sufficient": sufficient, "pearson_r": r}
    return result


def eval_regime(entries: list) -> dict:
    result = {}
    for w in WINDOWS:
        pool = _with_alpha(entries, w)
        by_regime = {}
        for e in pool:
            by_regime.setdefault(e.get("regime", "unbekannt"), []).append(e["fwd_alpha"][w])
        sufficient = all(len(v) >= MIN_N for v in by_regime.values()) and len(by_regime) >= 2
        result[w] = {
            "sufficient": sufficient,
            "by_regime": {k: {"n": len(v), "mean_alpha": round(statistics.mean(v), 2)}
                          for k, v in by_regime.items()},
        }
    return result


def any_sufficient(report: dict) -> bool:
    for section in ("pass_vs_veto", "score_correlation", "regime"):
        for w in WINDOWS:
            if report[section][w]["sufficient"]:
                return True
    return False


def build_report() -> dict:
    entries = load_entries()
    return {
        "total_entries": len(entries),
        "pass_vs_veto": eval_pass_vs_veto(entries),
        "score_correlation": eval_score_correlation(entries),
        "regime": eval_regime(entries),
    }


def print_human(report: dict):
    print(f"Signal-Journal-Auswertung — {report['total_entries']} Einträge gesamt, Mindestgröße je Gruppe: {MIN_N}\n")

    print("1) PASS vs. VETO (Ø Alpha-Rendite ggü. Benchmark):")
    for w in WINDOWS:
        d = report["pass_vs_veto"][w]
        if d["sufficient"]:
            diff = d["pass_mean_alpha"] - d["veto_mean_alpha"]
            print(f"  {w:4s}: PASS n={d['n_pass']:4d} Ø{d['pass_mean_alpha']:+.1f}%  |  "
                  f"VETO n={d['n_veto']:4d} Ø{d['veto_mean_alpha']:+.1f}%  |  Differenz {diff:+.1f}pp")
        else:
            print(f"  {w:4s}: noch nicht genug Daten (PASS n={d['n_pass']}, VETO n={d['n_veto']}, Ziel je {MIN_N})")

    print("\n2) Korrelation Verdict-Score <-> Alpha-Rendite (Pearson r):")
    for w in WINDOWS:
        d = report["score_correlation"][w]
        if d["sufficient"]:
            print(f"  {w:4s}: n={d['n']:4d}  r={d['pearson_r']:+.3f}")
        else:
            print(f"  {w:4s}: noch nicht genug Daten (n={d['n']}, Ziel {MIN_N})")

    print("\n3) Regime-Ampel (Ø Alpha-Rendite je Regime):")
    for w in WINDOWS:
        d = report["regime"][w]
        flag = "" if d["sufficient"] else "  [noch nicht ausreichend]"
        parts = ", ".join(f"{k}: n={v['n']} Ø{v['mean_alpha']:+.1f}%" for k, v in d["by_regime"].items())
        print(f"  {w:4s}: {parts or 'keine Daten'}{flag}")

    print()
    if any_sufficient(report):
        print("=> Mindestens eine Auswertung ist jetzt statistisch tragfähig.")
    else:
        print("=> Noch keine Frage ausreichend beantwortbar — weiter sammeln.")


if __name__ == "__main__":
    rep = build_report()
    if "--json" in sys.argv:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        print_human(rep)
