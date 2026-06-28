from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ml_prediction import predict_expected_co2_for_windows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate expected CO2 predictions for performance windows.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    parser.add_argument("--limit", type=int, default=500, help="Maximum windows to predict.")
    args = parser.parse_args()
    print(json.dumps(predict_expected_co2_for_windows(vessel_id=args.vessel_id, limit=args.limit), indent=2))


if __name__ == "__main__":
    main()
