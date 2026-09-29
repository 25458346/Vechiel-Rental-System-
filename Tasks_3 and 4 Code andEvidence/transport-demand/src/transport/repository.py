import json
from pathlib import Path
from typing import Protocol

import duckdb

from transport.models import DemandFilter


class DemandReader(Protocol):
    def summary(self) -> dict: ...
    def demand(self, filters: DemandFilter) -> list[dict]: ...


class DuckDBReader:
    def __init__(self, database: Path):
        if not database.is_file():
            raise FileNotFoundError("Build the analytical database first")
        self.database = database

    def _connect(self):
        connection = duckdb.connect(str(self.database), read_only=True)
        connection.execute("SET enable_external_access = false")
        return connection

    def summary(self) -> dict:
        with self._connect() as connection:
            return json.loads(connection.execute("SELECT payload FROM metadata").fetchone()[0])

    def demand(self, filters: DemandFilter) -> list[dict]:
        with self._connect() as connection:
            cursor = connection.execute("""
                SELECT d.zone_id, z.zone_name AS "zone", z.borough, SUM(d.pickups)::BIGINT pickups
                FROM demand d JOIN zones z USING(zone_id)
                WHERE service_date BETWEEN ? AND ?
                  AND (? IS NULL OR d.zone_id = ?)
                  AND (? IS NULL OR d.pickup_hour = ?)
                GROUP BY d.zone_id, z.zone_name, z.borough
                ORDER BY pickups DESC, d.zone_id ASC LIMIT ?
            """, [filters.start, filters.end, filters.zone_id, filters.zone_id,
                   filters.hour, filters.hour, filters.limit])
            names = [item[0] for item in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
