"""
Golden-Image-Regressionstest für die Render-Engine (render.py).

Rendert eine kleine, deterministische Auswahl von Slides (festes Datum, nur
statische Repo-Daten) und vergleicht sie pixelbasiert mit den Referenzbildern
unter instagram/qa/golden/. So fallen ungewollte Layout-Regressionen nach
Änderungen an render.py/theme.py sofort auf, ohne dass jede Slide manuell
geprüft werden muss. Die visuelle Kontrolle NEUER oder bewusst geänderter
Slide-Typen bleibt Pflicht (siehe CONTEXT.md, Qualitätssicherung).

Verwendung:
  python3 -m instagram.qa_golden            # prüfen (Exit 1 bei Abweichung)
  python3 -m instagram.qa_golden --update   # Referenzbilder neu erzeugen
                                            # (nur nach gewollten Design-Änderungen,
                                            #  vorher Slides visuell prüfen!)

Schwellwert: mittlere absolute Pixel-Abweichung <= 1.0 (0-255-Skala) gilt als
identisch — toleriert Encoder-Rauschen, schlägt bei echten Layout-Shifts an.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

from . import analysis as ana
from . import render

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, "qa", "golden")
OUT_DIR = os.path.join(HERE, "..", "out", "qa_golden")

FIXED_DATE = "2026-06-06"   # festes Slide-Datum → deterministische Bilder
THRESHOLD = 1.0             # mittlere |Differenz| je Pixelkanal (0–255)


def _cases():
    """Deterministische Test-Slides. Nur statische Quellen (analyses/*.md),
    KEINE täglich rotierenden Daten (rs_*.json) — sonst wären die Referenz-
    bilder nicht stabil."""
    a = ana.parse_analysis("AMD")
    return [
        ("analysis_cover", "carousel",
         lambda c: render.slide_analysis_cover(c, a, FIXED_DATE)),
        ("analysis_fazit", "carousel",
         lambda c: render.slide_analysis_fazit(c, a, FIXED_DATE)),
        ("analysis_cta", "carousel",
         lambda c: render.slide_analysis_cta(c, a, FIXED_DATE)),
        ("weekly_cta", "carousel",
         lambda c: render.slide_cta(c, FIXED_DATE,
                                    question="Hättest du hier auch gekauft?")),
        ("reel_cta", "reel",
         lambda c: render.slide_reel_cta(c, a, FIXED_DATE)),
    ]


def _render_case(name, fmt, draw):
    os.makedirs(OUT_DIR, exist_ok=True)
    c = render.Canvas(fmt)
    draw(c)
    path = os.path.join(OUT_DIR, f"{name}.png")
    c.save(path)
    return path


def _diff(path_a, path_b):
    img_a = np.asarray(Image.open(path_a).convert("RGB"), dtype=np.float64)
    img_b = np.asarray(Image.open(path_b).convert("RGB"), dtype=np.float64)
    if img_a.shape != img_b.shape:
        return None  # Dimensions-Abweichung = immer Fehler
    return float(np.abs(img_a - img_b).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true",
                    help="Referenzbilder neu schreiben (nach gewollter Änderung)")
    args = ap.parse_args()

    failed = []
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    for name, fmt, draw in _cases():
        try:
            out = _render_case(name, fmt, draw)
        except Exception as exc:
            print(f"✗ {name}: Render-Fehler — {exc}")
            failed.append(name)
            continue
        golden = os.path.join(GOLDEN_DIR, f"{name}.png")
        if args.update or not os.path.exists(golden):
            Image.open(out).save(golden)
            print(f"● {name}: Referenz {'aktualisiert' if args.update else 'angelegt'}")
            continue
        d = _diff(out, golden)
        if d is None:
            print(f"✗ {name}: Bildgröße weicht von Referenz ab")
            failed.append(name)
        elif d > THRESHOLD:
            print(f"✗ {name}: mittlere Abweichung {d:.2f} > {THRESHOLD} "
                  f"(Vergleich: {out} vs. {golden})")
            failed.append(name)
        else:
            print(f"✓ {name}: ok (Abweichung {d:.3f})")

    if failed:
        print(f"\n{len(failed)} Slide(s) weichen ab — render.py-Änderung prüfen; "
              f"war sie gewollt: Slides visuell kontrollieren, dann --update.")
        sys.exit(1)
    print("\nAlle Golden-Tests bestanden.")


if __name__ == "__main__":
    main()
