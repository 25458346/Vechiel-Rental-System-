import csv
from datetime import date
from io import StringIO

from transport.models import DemandFilter
from transport.repository import DemandReader


class DemandService:
    def __init__(self, reader: DemandReader):
        self.reader = reader

    def summary(self):
        return self.reader.summary()

    def demand(self, filters: DemandFilter):
        coverage = self.summary()
        if filters.start < date.fromisoformat(coverage["month"]) or filters.end >= date.fromisoformat(coverage["end_exclusive"]):
            raise ValueError("Date range is outside the loaded month")
        return self.reader.demand(filters)

    def export_csv(self, filters: DemandFilter) -> str:
        output = StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=["zone_id", "zone", "borough", "pickups"])
        writer.writeheader()
        for row in self.demand(filters):
            safe = {key: ("'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value) for key, value in row.items()}
            writer.writerow(safe)
        return output.getvalue()
