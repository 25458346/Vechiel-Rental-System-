import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import urllib.request

folder = Path(__file__).resolve().parents[1] / "data"
folder.mkdir(parents=True, exist_ok=True)
sources = {
    "yellow_tripdata_2025-01.parquet": "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-01.parquet",
    "taxi_zone_lookup.csv": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
}
manifest = []
for name, url in sources.items():
    target = folder / name
    if not target.exists():
        with urllib.request.urlopen(url, timeout=120) as response, target.with_suffix('.part').open('wb') as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        target.with_suffix('.part').replace(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest.append(dict(filename=name, url=url, bytes=target.stat().st_size, sha256=digest))
    print(name, target.stat().st_size, digest, flush=True)
(folder / 'sources.json').write_text(json.dumps({'retrieved_utc':datetime.now(timezone.utc).isoformat(), 'sources':manifest}, indent=2))

