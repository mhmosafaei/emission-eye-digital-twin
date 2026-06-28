from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.windowing import create_performance_windows_from_feature_rows


def build_windows(vessel_id: str | None = None, window_minutes: int = 15) -> dict:
    windows = create_performance_windows_from_feature_rows(vessel_id=vessel_id, window_minutes=window_minutes)
    valid_windows = sum(int(window.is_valid_window) for window in windows)
    return {
        "windows_created": len(windows),
        "valid_windows": valid_windows,
        "invalid_windows": len(windows) - valid_windows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build performance windows from stored feature rows.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    parser.add_argument("--window-minutes", type=int, default=15, help="Window size in minutes.")
    args = parser.parse_args()

    print(json.dumps(build_windows(vessel_id=args.vessel_id, window_minutes=args.window_minutes), indent=2))


if __name__ == "__main__":
    main()
