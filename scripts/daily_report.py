import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trader.db import init_db
from trader.reports.performance import get_performance_report, save_daily_snapshot
import json


def main():
    init_db()

    save_daily_snapshot()
    print("Daily snapshot saved.")

    report = get_performance_report("daily")
    print("\n=== Daily Performance Report ===")
    print(json.dumps(report, indent=2, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
