from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from madrigal_assistant.models import ImportSeedResponse, IngestRequest, IngestRunResult, ProblemCardsResponse, RawEventsResponse, TopIssuesResponse, TopicSummary, TrendsResponse
from madrigal_assistant.services import RegionalPulseService


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def create_app(service: RegionalPulseService | None = None) -> FastAPI:
    api_service = service or RegionalPulseService()
    app = FastAPI(title="Madrigal Regional Pulse API", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "region": api_service.region_config["region_name"]}

    @app.get("/api/metadata")
    def metadata() -> dict:
        return {
            "region": api_service.region_config["region_name"],
            "timezone": api_service.region_config["timezone"],
            "sources": api_service.region_config["sources"],
            "source_catalog": api_service.get_source_catalog(),
            "source_catalog_summary": api_service.source_catalog_summary(),
            "filters": api_service.filter_options(),
        }

    @app.get("/api/top-issues", response_model=TopIssuesResponse)
    def top_issues(
        from_: Annotated[str | None, Query(alias="from")] = None,
        to: str | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 10,
    ) -> TopIssuesResponse:
        return api_service.get_top_issues(
            start=_parse_optional_datetime(from_),
            end=_parse_optional_datetime(to),
            sector=sector,
            municipality=municipality,
            source_type=source_type,
            limit=limit,
        )

    @app.get("/api/problem-cards", response_model=ProblemCardsResponse)
    def problem_cards(
        from_: Annotated[str | None, Query(alias="from")] = None,
        to: str | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 10,
    ) -> ProblemCardsResponse:
        return api_service.get_problem_cards(
            start=_parse_optional_datetime(from_),
            end=_parse_optional_datetime(to),
            sector=sector,
            municipality=municipality,
            source_type=source_type,
            limit=limit,
        )

    @app.get("/api/topics/{topic_id}", response_model=TopicSummary)
    def topic_detail(
        topic_id: str,
        from_: Annotated[str | None, Query(alias="from")] = None,
        to: str | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
    ) -> TopicSummary:
        topic = api_service.get_topic(
            topic_id,
            start=_parse_optional_datetime(from_),
            end=_parse_optional_datetime(to),
            sector=sector,
            municipality=municipality,
            source_type=source_type,
        )
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        return topic

    @app.get("/api/trends", response_model=TrendsResponse)
    def trends(
        from_: Annotated[str | None, Query(alias="from")] = None,
        to: str | None = None,
        sector: str | None = None,
        municipality: str | None = None,
    ) -> TrendsResponse:
        return api_service.get_trends(
            start=_parse_optional_datetime(from_),
            end=_parse_optional_datetime(to),
            sector=sector,
            municipality=municipality,
        )

    @app.get("/api/raw-events", response_model=RawEventsResponse)
    def raw_events(
        from_: Annotated[str | None, Query(alias="from")] = None,
        to: str | None = None,
        source_type: str | None = None,
    ) -> RawEventsResponse:
        return api_service.get_raw_events(
            start=_parse_optional_datetime(from_),
            end=_parse_optional_datetime(to),
            source_type=source_type,
        )

    @app.post("/api/ingest/run", response_model=IngestRunResult)
    def ingest_run(request: IngestRequest) -> IngestRunResult:
        return api_service.run_ingest(max_per_source=request.max_per_source)

    @app.post("/api/import/seed", response_model=ImportSeedResponse)
    async def import_seed(file: UploadFile | None = File(default=None)) -> ImportSeedResponse:
        if file is None:
            return api_service.import_seed()
        return api_service.import_seed(upload_bytes=await file.read(), filename=file.filename or "upload.json")

    @app.post("/api/import/manual", response_model=ImportSeedResponse)
    async def import_manual(file: UploadFile = File(...)) -> ImportSeedResponse:
        return api_service.import_manual(upload_bytes=await file.read(), filename=file.filename or "manual.json")

    @app.get("/api/export", response_class=PlainTextResponse)
    def export_report(
        format: str = "csv",
        from_: Annotated[str | None, Query(alias="from")] = None,
        to: str | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
    ):
        start = _parse_optional_datetime(from_)
        end = _parse_optional_datetime(to)
        if format == "html":
            return HTMLResponse(api_service.export_html(start, end, sector, municipality, source_type))
        return PlainTextResponse(api_service.export_csv(start, end, sector, municipality, source_type))

    return app


app = create_app()
