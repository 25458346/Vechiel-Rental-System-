"""Run the Task 4 test specification and retain machine-readable evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import statistics
import subprocess
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
APP_PORT = int(os.environ.get("TRANSPORT_TEST_PORT", "18775"))
ZAP_PORT = int(os.environ.get("TRANSPORT_ZAP_PORT", "18776"))
TARGET = f"http://127.0.0.1:{APP_PORT}"
session = requests.Session()
session.trust_env = False


def save(name, data):
    (REPORTS / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def run(arguments, allowed=(0,)):
    result = subprocess.run([str(arg) for arg in arguments], check=False)
    if result.returncode not in allowed:
        raise RuntimeError(f"Stage failed with exit code {result.returncode}")
    return result.returncode


def source_manifest():
    paths = sorted([*ROOT.glob("src/**/*.py"), *ROOT.glob("tests/**/*.py"), *ROOT.glob("scripts/*.py"), ROOT / "requirements.lock", ROOT / "requirements-dev.lock", ROOT / "Jenkinsfile", ROOT / "pyproject.toml"])
    files = {path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        revision = None
    save("source-manifest.json", {"created_utc":datetime.now(timezone.utc).isoformat(), "commit":revision, "build_number":os.getenv("BUILD_NUMBER"), "files":files})


def static_checks():
    source_manifest()
    run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=reports/tests.xml"])
    pins = re.findall(r"^([\w.-]+==[^\s]+)", (ROOT / "requirements.lock").read_text(), re.M)
    (REPORTS / "audit-requirements.txt").write_text("\n".join(pins)+"\n")
    (REPORTS / "sca.json").unlink(missing_ok=True)
    audit_exit = run([sys.executable, "scripts/audit_dependencies.py", "-r", REPORTS / "audit-requirements.txt", "--no-deps", "--disable-pip", "--timeout", "15", "--progress-spinner", "off", "-f", "json", "-o", REPORTS / "sca.json"], (0, 1))
    sca = json.loads((REPORTS / "sca.json").read_text())
    expected = set(re.findall(r"^([\w.-]+)==", (ROOT / "requirements.lock").read_text(), re.M))
    observed = {dependency["name"] for dependency in sca["dependencies"] if "skip_reason" not in dependency}
    vulnerabilities = sum(len(dependency.get("vulns", [])) for dependency in sca["dependencies"])
    if expected != observed or vulnerabilities or audit_exit:
        raise RuntimeError("Dependency audit was incomplete or reported vulnerabilities")
    (REPORTS / "sast.json").unlink(missing_ok=True)
    sast_exit = run([sys.executable, "-m", "bandit", "-r", "src", "--ignore-nosec", "-f", "json", "-o", REPORTS / "sast.json"], (0, 1))
    sast = json.loads((REPORTS / "sast.json").read_text())
    scanned = [name for name in sast["metrics"] if name != "_totals"]
    blocked = [finding for finding in sast["results"] if finding["issue_severity"] in ("MEDIUM", "HIGH")]
    if sast["errors"] or len(scanned) != len(list((ROOT / "src").rglob("*.py"))) or blocked or (sast_exit and not sast["results"]):
        raise RuntimeError("Static analysis was incomplete or contained blocking findings")
    save("static-summary.json", {"audited_packages":len(observed), "known_vulnerabilities":vulnerabilities,
                                "scanned_files":len(scanned), "sast_findings":len(sast["results"]), "blocking_sast_findings":len(blocked)})


def live_checks():
    cases = []
    for path, expected in [("/health",200), ("/summary",200), ("/demand",200), ("/export.csv",200),
                           ("/demand?zone_id=1%20OR%201=1",422), ("/demand?hour=%3Cscript%3Ealert(1)%3C/script%3E",422),
                           ("/demand?limit=1000000",422), ("/demand?start=2025-02-01",422)]:
        response = session.get(TARGET + path, timeout=10)
        passed = response.status_code == expected and response.headers.get("X-Content-Type-Options") == "nosniff"
        cases.append({"path":path, "expected":expected, "actual":response.status_code, "passed":passed})
    response = session.post(TARGET + "/demand", json={"sql":"DELETE FROM demand"}, timeout=10)
    cases.append({"path":"POST /demand", "expected":405, "actual":response.status_code, "passed":response.status_code == 405})
    timings = []
    for _ in range(20):
        started = time.perf_counter()
        response = session.get(TARGET + "/demand", timeout=10)
        response.raise_for_status()
        timings.append((time.perf_counter()-started)*1000)
    summary = session.get(TARGET + "/summary", timeout=10).json()
    save("data-quality.json", summary)
    save("top-zones.json", response.json())
    save("live-tests.json", {"target":TARGET, "cases":cases, "samples":20, "median_ms":round(statistics.median(timings),3),
                            "max_ms":round(max(timings),3), "acceptance_max_ms":2000, "source_rows":summary["source_rows"]})
    if not all(case["passed"] for case in cases) or max(timings) > 2000:
        raise RuntimeError("Live test specification failed")


def zap_scan():
    java, jar = os.environ["JAVA_EXE"], Path(os.environ["ZAP_JAR"]).resolve()
    key = secrets.token_hex(24)
    address = f"http://127.0.0.1:{ZAP_PORT}"
    home = REPORTS / ("zap-" + datetime.now().strftime("%Y%m%d%H%M%S"))
    home.mkdir()

    def api(component, kind, action, **params):
        response = session.get(f"{address}/JSON/{component}/{kind}/{action}/", params={"apikey":key, **params}, timeout=30)
        data = response.json()
        if response.status_code != 200 or "code" in data:
            raise RuntimeError(f"ZAP rejected {action}: {data.get('code', response.status_code)}")
        return data

    with (REPORTS / "zap.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([java, "-Xmx768m", "-Djava.awt.headless=true", "-jar", str(jar), "-daemon", "-silent", "-host", "127.0.0.1", "-port", str(ZAP_PORT), "-dir", str(home), "-config", "api.key="+key, "-config", "autoupdate.checkOnStart=false"], cwd=jar.parent, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 120
            while True:
                try:
                    version = api("core", "view", "version")["version"]
                    break
                except requests.RequestException:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("ZAP failed to start; inspect reports/zap.log") from None
                    time.sleep(1)
            context = api("context", "action", "newContext", contextName="transport")["contextId"]
            api("context", "action", "includeInContext", contextName="transport", regex=re.escape(TARGET)+r"(?:/.*)?")
            api("context", "action", "setContextInScope", contextName="transport", booleanInScope="true")
            api("openapi", "action", "importUrl", url=TARGET+"/openapi.json", hostOverride=TARGET, contextId=context)
            proxy = requests.Session()
            proxy.trust_env = False
            proxy.proxies = {"http":address}
            for route in ["/", "/health", "/summary", "/demand?start=2025-01-01&end=2025-01-31&limit=20&zone_id=1&hour=8", "/export.csv?start=2025-01-01&end=2025-01-31&limit=20&zone_id=1&hour=8"]:
                proxy.get(TARGET+route, timeout=30).raise_for_status()
            rules = ["6", "7", "40012", "40018", "90019", "90020"]
            api("ascan", "action", "disableAllScanners")
            api("ascan", "action", "enableScanners", ids=",".join(rules))
            for rule in rules:
                api("ascan", "action", "setScannerAttackStrength", id=rule, attackStrength="LOW")
                api("ascan", "action", "setScannerAlertThreshold", id=rule, alertThreshold="MEDIUM")
            scan = api("ascan", "action", "scan", url=TARGET+"/", recurse="true", inScopeOnly="true", contextId=context)["scan"]
            deadline = time.monotonic()+600
            while api("ascan", "view", "status", scanId=scan)["status"] != "100":
                if time.monotonic() > deadline:
                    raise RuntimeError("DAST timed out")
                time.sleep(2)
            while int(api("pscan", "view", "recordsToScan")["recordsToScan"]) > 0:
                if time.monotonic() > deadline:
                    raise RuntimeError("Passive scan timed out")
                time.sleep(1)
            urls = api("core", "view", "urls", baseurl=TARGET)["urls"]
            scanners = api("ascan", "view", "scanners")["scanners"]
            enabled = {str(item["id"]) for item in scanners if str(item["enabled"]).lower() == "true"}
            if enabled != set(rules):
                raise RuntimeError("Active rule coverage did not match policy")
            for route in ["/health", "/summary", "/demand", "/export.csv"]:
                if not any(url.split("?")[0] == TARGET+route for url in urls):
                    raise RuntimeError("DAST endpoint coverage incomplete")
            alerts = api("core", "view", "alerts", baseurl=TARGET)["alerts"]
            blocked = [item for item in alerts if str(item.get("risk", "")).lower() in ("medium", "high", "2", "3")]
            save("dast.json", {"target":TARGET,"version":version,"completed_percent":100,"rules":rules,"urls":urls,"alerts":alerts,"blocking_findings":len(blocked)})
            response = session.get(address+"/OTHER/core/other/htmlreport/", params={"apikey":key}, timeout=30)
            response.raise_for_status()
            (REPORTS / "dast.html").write_text(response.text, encoding="utf-8")
            if blocked:
                raise RuntimeError("DAST found medium or high risk alerts")
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def runtime_checks():
    environment = {**os.environ, "PYTHONPATH":str(ROOT / "src")}
    with (REPORTS / "application.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "transport.api:create_app", "--factory", "--host", "127.0.0.1", "--port", str(APP_PORT), "--no-server-header"], env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(60):
                try:
                    session.get(TARGET+"/health", timeout=1).raise_for_status()
                    break
                except requests.RequestException:
                    if process.poll() is not None:
                        raise RuntimeError("Application did not start")
                    time.sleep(1)
            else:
                raise RuntimeError("Application readiness timed out")
            live_checks()
            zap_scan()
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["all", "static", "runtime"], default="all")
    args = parser.parse_args()
    if args.stage in ("all", "static"):
        static_checks()
    if args.stage in ("all", "runtime"):
        runtime_checks()
    print("Requested verification stages passed", flush=True)
