import argparse
from pathlib import Path
import sys

from .config import DEFAULT_CONFIG, load_config


def main():
    parser = argparse.ArgumentParser(description="MISS-Hauptprogramm: Kamera, Sortierung und Bewertung")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--simulate", action="store_true", help="Mit PC-Fenster und Testgeräten starten")
    parser.add_argument("--scale", type=int, choices=(1, 2, 3), default=1, help="Display-Vergrößerung in der Simulation (Standard: 1, native Pixel)")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.simulate:
            from Simulation.main import main as simulate
            return simulate(["--scale", str(args.scale), "--config", str(args.config)])
        from .hardware import run_hardware
        run_hardware(config)
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        print(f"MISS konnte nicht ausgeführt werden: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
