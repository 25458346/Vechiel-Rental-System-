"""Read-only local interface for the analyst."""
from datetime import date
from html import escape
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from transport.models import DemandFilter
from transport.repository import DuckDBReader
from transport.service import DemandService


def create_app(service: DemandService | None = None) -> FastAPI:
    if service is None:
        service = DemandService(DuckDBReader(Path(os.environ.get("TRANSPORT_DB", "data/demand.duckdb"))))
    app = FastAPI(title="Transport Demand Analysis", version="1.0.0", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(ValueError)
    async def invalid_request(request, exception):
        return PlainTextResponse(str(exception), status_code=422)

    def filters(start: date = date(2025, 1, 1), end: date = date(2025, 1, 31),
                zone_id: Annotated[int | None, Query(ge=1, le=263)] = None,
                hour: Annotated[int | None, Query(ge=0, le=23)] = None,
                limit: Annotated[int, Query(ge=1, le=100)] = 20):
        return DemandFilter(start, end, zone_id, hour, limit)

    @app.get("/health")
    def health():
        return {"status":"ok"}

    @app.get("/summary")
    def summary():
        return service.summary()

    @app.get("/demand")
    def demand(selection: Annotated[DemandFilter, Depends(filters)]):
        return service.demand(selection)

    @app.get("/export.csv")
    def export(selection: Annotated[DemandFilter, Depends(filters)]):
        return Response(service.export_csv(selection), media_type="text/csv", headers={"Content-Disposition":'attachment; filename="demand.csv"'})

    @app.get("/style.css", include_in_schema=False)
    def stylesheet():
        return Response("body{font-family:Georgia,serif;max-width:1000px;margin:40px auto;padding:0 24px;color:#111;background:white;line-height:1.5}h1{font-size:32px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid #bbb}input,button{font:inherit;padding:6px;margin:4px}a{color:#111}form{margin:24px 0}small{display:block}", media_type="text/css")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(selection: Annotated[DemandFilter, Depends(filters)]):
        result = service.demand(selection)
        summary = service.summary()
        rows = "".join(f"<tr><td>{item['zone_id']}</td><td>{escape(item['zone'])}</td><td>{escape(item['borough'])}</td><td>{item['pickups']:,}</td></tr>" for item in result)
        return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Transport Demand Analysis</title><link rel="stylesheet" href="/style.css"></head>
        <body><h1>Transport Demand Analysis</h1><p>New York yellow taxi pickups in January 2025</p>
        <p>{summary['source_rows']:,} source records &nbsp; {summary['accepted_rows']:,} accepted &nbsp; {summary['rejected_rows']:,} excluded</p>
        <form method="get"><label>From <input type="date" name="start" value="{selection.start}" required></label>
        <label>To <input type="date" name="end" value="{selection.end}" required></label>
        <label>Results <input type="number" name="limit" min="1" max="100" value="{selection.limit}"></label><button>Analyse</button></form>
        <p>Showing {len(result)} zones for {selection.start} to {selection.end}. API filters also support zone and hour.</p>
        <table><thead><tr><th>Zone ID</th><th>Zone</th><th>Borough</th><th>Recorded pickups</th></tr></thead><tbody>{rows}</tbody></table>
        <p><a href="/export.csv?start={selection.start}&amp;end={selection.end}&amp;limit={selection.limit}{'&amp;zone_id='+str(selection.zone_id) if selection.zone_id is not None else ''}{'&amp;hour='+str(selection.hour) if selection.hour is not None else ''}">Download these results as CSV</a> &nbsp; <a href="/summary">Data quality report</a></p>
        <small>Source: NYC Taxi and Limousine Commission. Counts describe recorded pickups, not unmet demand or a forecast. Data quality rules exclude invalid dates, zones, durations and distances.</small></body></html>'''

    return app
