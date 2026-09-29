import argparse
from datetime import date
import json
from pathlib import Path

from transport.ingest import build_database


def main():
    parser = argparse.ArgumentParser(description="Build transport demand aggregates")
    parser.add_argument("--trips", type=Path, required=True)
    parser.add_argument("--zones", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=Path("data/demand.duckdb"))
    parser.add_argument("--month", type=date.fromisoformat, default=date(2025, 1, 1))
    args = parser.parse_args()
    result = build_database(args.trips, args.zones, args.database, args.month)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
