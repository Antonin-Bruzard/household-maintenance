#!/usr/bin/env python3
"""Run the workspace-only maintenance prototype at http://127.0.0.1:8765."""
from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path

from prototype.household_maintenance.local_demo import LocalDemoServer


def main() -> None:
    parser = argparse.ArgumentParser(description="Local household-maintenance demo")
    parser.add_argument("--data", type=Path, default=Path(".demo-data/maintenance.json"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with LocalDemoServer(args.data, port=args.port) as server:
        print(f"Panel local : {server.url}/panel.html")
        print(f"Carte Lovelace : {server.url}/household-maintenance-card.js")
        print("Ctrl+C pour arrêter ; les données restent limitées au fichier --data.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
