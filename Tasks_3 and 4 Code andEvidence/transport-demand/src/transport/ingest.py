"""Build a compact analytical database from a complete month of trips."""
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import duckdb


REQUIRED_COLUMNS = {
    "tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID", "trip_distance"
}


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def build_database(trips: Path, zones: Path, database: Path, month: date) -> dict:
    if month.day != 1:
        raise ValueError("Month must be its first day")
    if database.exists():
        raise FileExistsError("Choose a new output database to preserve existing results")
    end = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    database.parent.mkdir(parents=True, exist_ok=True)
    start = perf_counter()
    temporary = database.with_name(database.name + "." + uuid4().hex + ".building")
    connection = duckdb.connect(str(temporary))
    committed = False
    try:
        connection.execute("SET memory_limit = '512MB'")
        connection.execute("SET threads = 2")
        columns = set(connection.read_parquet(str(trips)).columns)
        if not REQUIRED_COLUMNS.issubset(columns):
            raise ValueError("Trip file is missing required columns")
        connection.execute("BEGIN TRANSACTION")
        connection.execute('CREATE TABLE zones AS SELECT CAST(LocationID AS INTEGER) AS zone_id, Borough AS borough, "Zone" AS zone_name FROM read_csv_auto(?) WHERE LocationID BETWEEN 1 AND 263', [str(zones)])
        duplicates = connection.execute("SELECT count(*) - count(DISTINCT zone_id) FROM zones").fetchone()[0]
        if duplicates:
            raise ValueError("Zone identifiers must be unique")
        connection.execute("""
            CREATE TEMP TABLE classified AS
            SELECT tpep_pickup_datetime pickup, PULocationID zone_id,
                CASE
                    WHEN tpep_pickup_datetime IS NULL OR tpep_pickup_datetime < ?
                         OR tpep_pickup_datetime >= ? THEN 'outside_month_or_missing_pickup'
                    WHEN PULocationID IS NULL OR PULocationID NOT IN (SELECT zone_id FROM zones)
                         THEN 'unknown_zone'
                    WHEN tpep_dropoff_datetime IS NULL
                         OR tpep_dropoff_datetime <= tpep_pickup_datetime
                         OR tpep_dropoff_datetime > tpep_pickup_datetime + INTERVAL '180 minutes'
                         THEN 'invalid_duration'
                    WHEN trip_distance IS NULL OR NOT isfinite(trip_distance)
                         OR trip_distance <= 0 OR trip_distance > 200 THEN 'invalid_distance'
                    ELSE 'accepted'
                END outcome
            FROM read_parquet(?)
        """, [month, end, str(trips)])
        counts = dict(connection.execute("SELECT outcome, count(*) FROM classified GROUP BY outcome").fetchall())
        connection.execute("""
            CREATE TABLE demand AS
                SELECT CAST(pickup AS DATE) service_date, CAST(hour(pickup) AS INTEGER) AS pickup_hour,
                   CAST(zone_id AS INTEGER) zone_id, count(*) pickups
            FROM classified WHERE outcome = 'accepted' GROUP BY 1, 2, 3
        """)
        accepted = counts.get("accepted", 0)
        grouped = connection.execute("SELECT coalesce(sum(pickups),0) FROM demand").fetchone()[0]
        if grouped != accepted:
            raise RuntimeError("Grouped counts do not reconcile with accepted rows")
        metadata = {
            "month": month.isoformat(), "end_exclusive":end.isoformat(),
            "source_rows":sum(counts.values()), "accepted_rows":accepted,
            "rejected_rows":sum(counts.values()) - accepted, "outcomes":counts,
            "aggregate_rows":connection.execute("SELECT count(*) FROM demand").fetchone()[0],
            "trip_file_sha256":digest(trips), "zone_file_sha256":digest(zones),
            "built_utc":datetime.now(timezone.utc).isoformat(),
            "processing_seconds":round(perf_counter() - start, 3),
            "memory_limit":"512MB", "threads":2,
            "interpretation":"Recorded yellow-taxi pickups, not unmet demand or a forecast"
        }
        connection.execute("CREATE TABLE metadata (payload VARCHAR)")
        connection.execute("INSERT INTO metadata VALUES (?)", [json.dumps(metadata)])
        connection.execute("COMMIT")
        committed = True
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except duckdb.Error:
            pass
        raise
    finally:
        connection.close()
        if not committed:
            temporary.unlink(missing_ok=True)
    temporary.rename(database)
    return metadata
