import csv
from datetime import date
from io import StringIO

import duckdb
import pytest

from transport.ingest import build_database
from transport.models import DemandFilter
from transport.service import DemandService


def test_reject_counts_and_aggregate_reconcile(service):
    summary = service.summary()
    assert summary["source_rows"] == 12
    assert summary["accepted_rows"] == 4
    assert summary["rejected_rows"] == 8
    assert summary["outcomes"] == {"accepted":4, "outside_month_or_missing_pickup":2,
                                    "unknown_zone":1, "invalid_duration":2, "invalid_distance":3}
    assert summary["aggregate_rows"] == 3


def test_duplicate_observations_preserved_and_ties_ordered(service):
    rows = service.demand(DemandFilter(date(2025, 1, 1), date(2025, 1, 31)))
    assert [(row["zone_id"], row["pickups"]) for row in rows] == [(1, 2), (2, 2)]


def test_day_hour_and_zone_filters(service):
    query = DemandFilter(date(2025, 1, 1), date(2025, 1, 1), zone_id=1, hour=8)
    assert service.demand(query)[0]["pickups"] == 2
    assert service.demand(DemandFilter(date(2025, 1, 1), date(2025, 1, 1), hour=9)) == []


def test_month_end_trip_included_by_pickup(service):
    rows = service.demand(DemandFilter(date(2025, 1, 31), date(2025, 1, 31)))
    assert rows[0]["pickups"] == 1


def test_existing_database_preserved(files, folder):
    target = folder / "existing.duckdb"
    target.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        build_database(*files, target, date(2025, 1, 1))
    assert target.read_bytes() == b"keep"


def test_bad_schema_does_not_publish_database(files, folder):
    with duckdb.connect() as connection:
        connection.execute("COPY (SELECT 1 AS wrong) TO ? (FORMAT PARQUET)", [str(folder / "bad.parquet")])
    target = folder / "bad.duckdb"
    with pytest.raises(ValueError, match="columns"):
        build_database(folder / "bad.parquet", files[1], target, date(2025, 1, 1))
    assert not target.exists()


def test_duplicate_zone_lookup_rejected(files, folder):
    with files[1].open("a") as target:
        target.write("1,Test,Duplicate\n")
    with pytest.raises(ValueError, match="unique"):
        build_database(*files, folder / "duplicate.duckdb", date(2025, 1, 1))


def test_reader_can_be_substituted_and_csv_formula_is_neutralised():
    class MemoryReader:
        def summary(self):
            return {"month":"2025-01-01", "end_exclusive":"2025-02-01"}

        def demand(self, filters):
            return [{"zone_id":1, "zone":"=1+1", "borough":"Test", "pickups":2}]

    service = DemandService(MemoryReader())
    query = DemandFilter(date(2025, 1, 1), date(2025, 1, 1))
    row = next(csv.DictReader(StringIO(service.export_csv(query))))
    assert row["zone"] == "'=1+1"
