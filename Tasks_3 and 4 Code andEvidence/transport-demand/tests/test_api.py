import csv
from io import StringIO

import pytest


@pytest.mark.parametrize("query", [
    "hour=-1", "hour=24", "zone_id=0", "zone_id=264", "limit=0", "limit=101",
    "start=2025-01-02&end=2025-01-01", "start=2024-12-31", "end=2025-02-01",
    "start=not-a-date", "zone_id=1%20OR%201=1", "hour=%3Cscript%3E",
])
def test_invalid_filters_rejected(client, query):
    assert client.get("/demand?" + query).status_code == 422


def test_valid_response_and_export_agree(client):
    response = client.get("/demand?limit=1")
    assert response.status_code == 200
    assert response.json()[0]["zone_id"] == 1
    exported = client.get("/export.csv?limit=1")
    row = next(csv.DictReader(StringIO(exported.text)))
    assert int(row["pickups"]) == response.json()[0]["pickups"]


@pytest.mark.parametrize("path", ["/", "/health", "/summary", "/demand", "/export.csv", "/demand?limit=0"])
def test_headers_on_normal_and_rejected_responses(client, path):
    response = client.get(path)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_no_write_endpoint(client):
    assert client.post("/demand", json={"sql":"DELETE FROM demand"}).status_code == 405


def test_page_escapes_dataset_text(service):
    from fastapi.testclient import TestClient
    from transport.api import create_app
    from transport.service import DemandService

    class Reader:
        def summary(self):
            return service.summary()

        def demand(self, filters):
            return [{"zone_id":1, "zone":"<script>alert(1)</script>", "borough":"Test", "pickups":1}]

    with TestClient(create_app(DemandService(Reader()))) as client:
        page = client.get("/").text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
