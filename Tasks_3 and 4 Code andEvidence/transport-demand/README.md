# Transport Demand Analysis

ATHE Level 5 Unit 9 Tasks 3 and 4. Analyse recorded NYC yellow-taxi pickups by date, zone and hour, and export ranked results as CSV.

The January 2025 source contains 3,475,226 trips. The supplied analytical database contains aggregate counts derived from the complete file. It does not contain individual trip records. This is a local teaching application. It measures recorded pickups, not unmet demand or future demand.

## Run on Windows

Install Python 3.12 or later. From this project folder:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r requirements-dev.lock
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m uvicorn transport.api:create_app --factory --host 127.0.0.1 --port 18775 --no-server-header
```

Open http://127.0.0.1:18775/ and use the date and result-limit fields. API examples:

* `/summary` shows row counts and exclusion reasons.
* `/demand?start=2025-01-01&end=2025-01-07&hour=8&limit=10` ranks zones at 08:00 across the first week.
* `/demand?zone_id=161` returns Midtown Center's recorded pickups.
* `/export.csv?limit=10` downloads the top ten zones.

Stop the server with Ctrl+C. The service must remain bound to loopback; public hosting would require a separate authentication, TLS and operational review.

## Rebuild from the source dataset

The 59 MB raw Parquet file is not included in the ZIP. Download it from the official TLC host with:

```powershell
.venv/Scripts/python.exe scripts/fetch_data.py
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m transport.cli --trips data/yellow_tripdata_2025-01.parquet --zones data/taxi_zone_lookup.csv --database data/rebuilt.duckdb
```

The importer refuses to overwrite an existing database. To use the rebuilt version, set `$env:TRANSPORT_DB = 'data/rebuilt.duckdb'` before starting the server. The interface defaults and displayed month are January 2025; changing the study month also requires updating the interface defaults and fixtures.

Data source: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page. The source URLs, download time and SHA-256 hashes are in `data/sources.json`. Identical input rows are retained because the selected fields do not contain a unique trip identifier. Exclusions apply in this order: pickup outside January or missing, unknown zone, invalid duration, invalid distance. Duration must be greater than zero and at most 180 minutes; distance must be finite, greater than zero and at most 200 miles. These are assignment analysis rules, not TLC definitions of valid trips.

## Run Task 4 verification

```powershell
.venv/Scripts/python.exe scripts/verify.py --stage static
```

This runs 37 pytest cases, audits every runtime package from the lock file using pip-audit, and scans all application Python files with Bandit. The audit wrapper uses an in-memory HTTP cache to avoid restrictive Windows temporary-folder permissions. It leaves vulnerability queries, results and gate decisions unchanged.

For ZAP, install Java 17 or later and obtain the official ZAP 2.17.0 cross-platform package. Check its release checksum. Stop the interactive application before this command because verification starts its own instance:

```powershell
$env:JAVA_EXE = 'C:/path/to/java.exe'
$env:ZAP_JAR = 'C:/path/to/ZAP_2.17.0/zap-2.17.0.jar'
.venv/Scripts/python.exe scripts/verify.py --stage runtime
```

The runtime stage runs nine HTTP checks, measures 20 sequential requests, imports OpenAPI into ZAP and runs six active rules plus passive scanning against 127.0.0.1 only. `--stage all` runs both stages. The performance threshold is a maximum of 2 seconds for each of those 20 local requests; it is not a concurrent load or production capacity test.

Runtime dependency vulnerabilities block verification. Bandit medium/high findings and ZAP medium/high alerts also block it. Scanner failures and missing coverage fail the stage. Zero findings only describe the configured scans at their execution time.

`reports/` contains the actual JSON, XML and HTML evidence. `source-manifest.json` identifies the tested source by file hashes. Re-running verification replaces reports, so copy them first if retaining an earlier run.

## Jenkins integration

The Jenkinsfile runs on a Windows agent labelled `transport-windows`. Configure Pipeline from SCM and set these agent environment variables: `TRANSPORT_PYTHON` (Python 3.12 environment), `TRANSPORT_UV` (uv executable), `JAVA_EXE`, `ZAP_JAR` and `TRANSPORT_DB` (absolute path to the supplied aggregate database). Optional `TRANSPORT_TEST_PORT` and `TRANSPORT_ZAP_PORT` select separate loopback ports; the recorded Jenkins run uses 18785 and 18786. The pipeline synchronises hash-locked dependencies, runs functional tests, SCA, SAST, live checks and DAST, then archives a verified source ZIP with a checksum. A failed gate blocks delivery. Jenkins polls SCM every two minutes and records JUnit results and report artifacts.

Real Jenkins evidence is supplied in the submission's `ci-evidence` directory. Build 1 passed. Build 2 was an explicitly labelled fault-injection demonstration: replacing `SUM(d.pickups)` with `SUM(d.pickups * 2)` caused three independently specified count tests to fail and blocked the delivery stage. The next revision restores the correct calculation and reruns the same gates. Refer to the archived build results for the final result and commit; the deliberate fault is not in this delivered source. This is a local continuous integration and source-delivery demonstration, not public production deployment.

The release manifest identifies the tested Git commit, database hash and delivered ZIP hash. The original full-month data provenance and processing results remain separately available in `data/sources.json` and `reports/data-quality.json`.

## Code map

* `models.py`: immutable validated filters.
* `ingest.py`: source validation, quality classification and database creation.
* `repository.py`: narrow reader protocol and parameterised DuckDB queries.
* `service.py`: coverage validation and safe CSV export.
* `api.py`: HTTP validation, escaped HTML and response headers.
* `tests/`: deterministic small fixtures and expected outcomes.
* `scripts/verify.py`: functional, dependency, static and dynamic checks.

The source demonstrates single responsibility, dependency inversion, interface segregation and substitutable reader implementations. Comments are limited to useful module context.
