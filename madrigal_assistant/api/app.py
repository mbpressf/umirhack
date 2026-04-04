from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import hashlib
import hmac
import re
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from madrigal_assistant.models import (
    AuthResponse,
    AuthUser,
    ImportSeedResponse,
    IngestRequest,
    IngestRunResult,
    LoginRequest,
    ProblemCardsResponse,
    RawEventsResponse,
    RegisterRequest,
    SimilarTopicsResponse,
    TopIssuesResponse,
    TopicSummary,
    TrendsResponse,
)
from madrigal_assistant.services import RegionalPulseService


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _normalize_login(raw_login: str) -> str:
    value = (raw_login or "").strip()
    if "@" in value:
        return value.lower()
    digits = re.sub(r"\D+", "", value)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7"):
        return f"+{digits}"
    return value


def _is_login_valid(login: str) -> bool:
    if not login:
        return False
    if "@" in login:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", login))
    return bool(re.fullmatch(r"\+\d{11}", login))


def _hash_password(login: str, password: str) -> str:
    salt = hashlib.sha256(login.encode("utf-8")).digest()
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000).hex()


def create_app(service: RegionalPulseService | None = None) -> FastAPI:
    api_service = service or RegionalPulseService()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if service is None:
            api_service.start_auto_refresh()
        try:
            yield
        finally:
            if service is None:
                api_service.stop_auto_refresh()

    app = FastAPI(title="Madrigal Regional Pulse API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
            "embedding_layer": api_service.embedding_layer_status(),
            "auto_refresh": api_service.auto_refresh_status(),
            "filters": api_service.filter_options(),
        }

    @app.get("/api/frontend-snapshot")
    def frontend_snapshot() -> dict:
        return api_service.get_frontend_snapshot()

    @app.get("/api/refresh-status")
    def refresh_status() -> dict:
        return api_service.auto_refresh_status()

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

    @app.get("/api/similar-topics", response_model=SimilarTopicsResponse)
    def similar_topics(
        topic_id: str | None = None,
        q: str | None = None,
        from_: Annotated[str | None, Query(alias="from")] = None,
        to: str | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 5,
    ) -> SimilarTopicsResponse:
        if not topic_id and not q:
            raise HTTPException(status_code=400, detail="Provide topic_id or q")
        return api_service.get_similar_topics(
            topic_id=topic_id,
            query=q,
            start=_parse_optional_datetime(from_),
            end=_parse_optional_datetime(to),
            sector=sector,
            municipality=municipality,
            source_type=source_type,
            limit=limit,
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
        return api_service.run_ingest(max_per_source=request.max_per_source, trigger="manual")

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

    @app.post("/api/auth/register", response_model=AuthResponse)
    def register(payload: RegisterRequest) -> AuthResponse:
        login = _normalize_login(payload.login)
        if not _is_login_valid(login):
            raise HTTPException(status_code=400, detail="Введите корректную почту или телефон")
        if len(payload.password) < 6:
            raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")
        if payload.password != payload.password_confirm:
            raise HTTPException(status_code=400, detail="Пароли не совпадают")

        created = api_service.db.create_user(login=login, password_hash=_hash_password(login, payload.password))
        if not created:
            existing_user = api_service.db.get_user_with_secret(login=login)
            if existing_user:
                raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")
            raise HTTPException(status_code=500, detail="Не удалось зарегистрировать пользователя. Попробуйте позже")
        return AuthResponse(user=AuthUser(**created))

    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(payload: LoginRequest) -> AuthResponse:
        login = _normalize_login(payload.login)
        if not _is_login_valid(login):
            raise HTTPException(status_code=400, detail="Введите корректную почту или телефон")
        user = api_service.db.get_user_with_secret(login=login)
        if not user:
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")

        expected_hash = _hash_password(login, payload.password)
        if not hmac.compare_digest(user["password_hash"], expected_hash):
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")

        return AuthResponse(
            user=AuthUser(
                id=user["id"],
                login=user["login"],
                created_at=user["created_at"],
            )
        )

    return app


app = create_app()
