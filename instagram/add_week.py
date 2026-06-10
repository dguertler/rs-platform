"""
Hängt den wikifolio-Zertifikatswert einer KW an instagram/data/wikifolio_history.json an
(oder aktualisiert ihn) und kann direkt den Wochenpost erzeugen.

Beispiel:
    python3 -m instagram.add_week --kw 22 --value 145.30
    python3 -m instagram.add_week --kw 22 --value 145.30 --generate
"""
import argparse
import subprocess
import sys

from . import store


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kw", type=int, required=True)
    ap.add_argument("--value", type=float, required=True,
                    help="Zertifikatswert (gleiche Skala wie start_value in config.json)")
    ap.add_argument("--date", help="Echtes Datum des Wochenwerts (YYYY-MM-DD)")
    ap.add_argument("--generate", action="store_true", help="danach Slides erzeugen")
    args = ap.parse_args()

    store.append_week(args.kw, args.value, date=args.date)
    print(f"✓ KW{args.kw} = {args.value} gespeichert"
          f"{f' ({args.date})' if args.date else ''}.")
    if args.generate:
        subprocess.run([sys.executable, "-m", "instagram.generate", "--kw", str(args.kw)])


if __name__ == "__main__":
    main()
