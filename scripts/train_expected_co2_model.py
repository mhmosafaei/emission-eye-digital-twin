from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ml_training import train_expected_co2_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the expected CO2 model from performance windows.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    args = parser.parse_args()
    print(json.dumps(train_expected_co2_model(vessel_id=args.vessel_id), indent=2))


if __name__ == "__main__":
    main()
