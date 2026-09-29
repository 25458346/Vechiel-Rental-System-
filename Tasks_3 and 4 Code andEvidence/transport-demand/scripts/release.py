"""Package the checked source after every verification gate succeeds."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
reports = root / "reports"
snapshot = json.loads((reports / "source-manifest.json").read_text())
static = json.loads((reports / "static-summary.json").read_text())
live = json.loads((reports / "live-tests.json").read_text())
dast = json.loads((reports / "dast.json").read_text())
suites = ET.parse(reports / "tests.xml").getroot().findall("testsuite")
if not suites or any(int(suite.get("failures", 0)) or int(suite.get("errors", 0)) for suite in suites):
    raise RuntimeError("Functional tests did not pass")
if static["known_vulnerabilities"] or static["blocking_sast_findings"]:
    raise RuntimeError("Static security gates did not pass")
if not all(case["passed"] for case in live["cases"]) or live["max_ms"] > live["acceptance_max_ms"]:
    raise RuntimeError("Live acceptance checks did not pass")
if dast["completed_percent"] != 100 or dast["blocking_findings"]:
    raise RuntimeError("Dynamic security gate did not pass")
for name, digest in snapshot["files"].items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
        raise RuntimeError(f"Source changed after tests: {name}")
database = Path(os.environ.get("TRANSPORT_DB", root / "data/demand.duckdb"))
destination = root / "dist"
destination.mkdir(exist_ok=True)
artifact = destination / "transport-demand-verified.zip"
with ZipFile(artifact, "w", ZIP_DEFLATED) as package:
    for name in snapshot["files"]:
        package.write(root/name, name)
    for name in ["README.md", "requirements.in", "requirements-dev.in"]:
        package.write(root/name, name)
    package.write(database, "data/demand.duckdb")
manifest = {"build_number":os.getenv("BUILD_NUMBER"), "commit":snapshot["commit"],
            "filename":artifact.name, "sha256":hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "database_sha256":hashlib.sha256(database.read_bytes()).hexdigest(), "status":"verified source delivery"}
(reports/"release.json").write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
