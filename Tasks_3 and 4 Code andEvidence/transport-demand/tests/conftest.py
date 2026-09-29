import csv
from datetime import date
from pathlib import Path
from uuid import uuid4

import duckdb
import pytest
from fastapi.testclient import TestClient

from transport.api import create_app
from transport.ingest import build_database
from transport.repository import DuckDBReader
from transport.service import DemandService


@pytest.fixture
def folder():
    path = Path("reports/testdata") / uuid4().hex
    path.mkdir(parents=True)
    return path


@pytest.fixture
def files(folder):
    trips = folder / "trips.parquet"
    zones = folder / "zones.csv"
    with zones.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerows([["LocationID", "Borough", "Zone"], [1, "Test", "Alpha"], [2, "Test", "Beta"]])
    rows = [
        ("2025-01-01 08:00", "2025-01-01 08:10", 1, 2.0),
        ("2025-01-01 08:00", "2025-01-01 08:10", 1, 2.0),
        ("2025-01-02 09:00", "2025-01-02 09:10", 2, 3.0),
        ("2025-01-31 23:50", "2025-02-01 00:10", 2, 4.0),
        ("2025-02-01 08:00", "2025-02-01 08:10", 1, 2.0),
        (None, "2025-01-01 08:10", 1, 2.0),
        ("2025-01-01 08:00", "2025-01-01 08:10", 265, 2.0),
        ("2025-01-01 08:00", "2025-01-01 07:59", 1, 2.0),
        ("2025-01-01 08:00", "2025-01-01 11:01", 1, 2.0),
        ("2025-01-01 08:00", "2025-01-01 08:10", 1, 0.0),
        ("2025-01-01 08:00", "2025-01-01 08:10", 1, None),
        ("2025-01-01 08:00", "2025-01-01 08:10", 1, float("nan")),
    ]
    with duckdb.connect() as connection:
        connection.execute("CREATE TABLE sample(tpep_pickup_datetime TIMESTAMP, tpep_dropoff_datetime TIMESTAMP, PULocationID INTEGER, trip_distance DOUBLE)")
        connection.executemany("INSERT INTO sample VALUES (?, ?, ?, ?)", rows)
        connection.execute("COPY sample TO ? (FORMAT PARQUET)", [str(trips)])
    return trips, zones


@pytest.fixture
def service(files, folder):
    database = folder / "test.duckdb"
    build_database(*files, database, date(2025, 1, 1))
    return DemandService(DuckDBReader(database))


@pytest.fixture
def client(service):
    with TestClient(create_app(service)) as session:
        yield session
