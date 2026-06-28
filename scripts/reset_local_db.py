from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import dispose_db


def reset_local_db(*, yes: bool = False) -> dict:
    db_path = Path("data") / "emission_eye_twin.sqlite3"
    existed = db_path.exists()

    if not yes:
        raise SystemExit(
            "Refusing to reset the local database without confirmation. Re-run with --yes to delete data/emission_eye_twin.sqlite3."
        )

    if existed:
        dispose_db()
        last_error: Exception | None = None
        for _ in range(5):
            try:
                db_path.unlink()
                last_error = None
                break
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.2)
        if last_error is not None:
            raise last_error

    return {
        "database_path": str(db_path),
        "deleted": existed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete the local SQLite database used by the demo backend.")
    parser.add_argument("--yes", action="store_true", help="Confirm database deletion.")
    args = parser.parse_args()

    summary = reset_local_db(yes=args.yes)
    print(summary)


if __name__ == "__main__":
    main()
