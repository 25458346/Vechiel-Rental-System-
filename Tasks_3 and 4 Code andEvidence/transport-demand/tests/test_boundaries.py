from datetime import date

import duckdb
import pytest

from transport.ingest import build_database
from transport.models import DemandFilter


@pytest.mark.parametrize("field,value", [("hour",-1),("hour",24),("zone_id",0),("zone_id",264),("limit",0),("limit",101)])
def test_domain_filter_bounds(field, value):
    with pytest.raises(ValueError):
        DemandFilter(date(2025,1,1), date(2025,1,31), **{field:value})


def test_inclusive_duration_distance_boundaries(files, folder):
    trips, zones = files
    special = folder / "boundaries.parquet"
    with duckdb.connect() as connection:
        connection.execute("""COPY (
            SELECT TIMESTAMP '2025-01-01 00:00:00' tpep_pickup_datetime,
                   TIMESTAMP '2025-01-01 03:00:00' tpep_dropoff_datetime,
                   1 PULocationID, 200.0 trip_distance
        ) TO ? (FORMAT PARQUET)""", [str(special)])
    result = build_database(special,zones,folder/'boundary.duckdb',date(2025,1,1))
    assert result['accepted_rows'] == 1
    assert result['rejected_rows'] == 0


def test_all_invalid_input_produces_empty_aggregate(files, folder):
    special = folder / "invalid.parquet"
    with duckdb.connect() as connection:
        connection.execute("""COPY (
            SELECT TIMESTAMP '2024-12-31 23:00:00' tpep_pickup_datetime,
                   TIMESTAMP '2024-12-31 23:10:00' tpep_dropoff_datetime,
                   1 PULocationID, 2.0 trip_distance
        ) TO ? (FORMAT PARQUET)""", [str(special)])
    result = build_database(special,files[1],folder/'empty.duckdb',date(2025,1,1))
    assert (result['source_rows'], result['accepted_rows'], result['rejected_rows'], result['aggregate_rows']) == (1,0,1,0)
