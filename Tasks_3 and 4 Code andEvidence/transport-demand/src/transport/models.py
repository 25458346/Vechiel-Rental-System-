from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DemandFilter:
    start: date
    end: date
    zone_id: int | None = None
    hour: int | None = None
    limit: int = 20

    def __post_init__(self):
        if not 0 <= (self.end - self.start).days <= 30:
            raise ValueError("Choose an ordered date range of at most 31 days")
        if self.zone_id is not None and not 1 <= self.zone_id <= 263:
            raise ValueError("Zone must be between 1 and 263")
        if self.hour is not None and not 0 <= self.hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        if not 1 <= self.limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
