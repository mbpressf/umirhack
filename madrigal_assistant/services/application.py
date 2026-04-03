from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path

from madrigal_assistant.analytics import AnalyticsService
from madrigal_assistant.ingest import IngestionService
from madrigal_assistant.models import ImportSeedResponse, IngestRunResult, RawEvent, RawEventsResponse, TopIssuesResponse, TopicSummary, TrendsResponse
from madrigal_assistant.settings import get_config_path, get_db_path, get_seed_path, load_region_config
from madrigal_assistant.storage import Database
from madrigal_assistant.text import stable_event_id


class RegionalPulseService:
    def __init__(self, db_path: Path | None = None, config_path: Path | None = None):
        self.config_path = config_path or get_config_path()
        self.region_config = load_region_config(self.config_path)
        self.db = Database(db_path or get_db_path())
        self.db.init()
        self.ingestion = IngestionService(self.region_config)
        self.analytics = AnalyticsService(self.region_config)

    def import_seed(self, upload_bytes: bytes | None = None, filename: str | None = None) -> ImportSeedResponse:
        source = filename or str(get_seed_path())
        payload = upload_bytes if upload_bytes is not None else get_seed_path().read_bytes()
        events = self._parse_payload(payload, filename or get_seed_path().name)
        inserted, updated = self.db.upsert_events(events)
        return ImportSeedResponse(imported=inserted, updated=updated, source=source)

    def run_ingest(self, max_per_source: int = 8) -> IngestRunResult:
        existing_ids = {event.event_id for event in self.db.fetch_events()}
        events, stats = self.ingestion.run(max_per_source=max_per_source)
        inserted, updated = self.db.upsert_events(events)
        for stat in stats:
            if stat.status != "ok":
                continue
            source_events = [event for event in events if event.source_id == stat.source_id]
            stat.updated = sum(1 for event in source_events if event.event_id in existing_ids)
            stat.inserted = len(source_events) - stat.updated
        return IngestRunResult(inserted=inserted, updated=updated, scanned=len(events), source_stats=stats)

    def get_top_issues(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 10,
    ) -> TopIssuesResponse:
        events = self.db.fetch_events(start=start, end=end, source_type=source_type)
        return self.analytics.build_top_issues(events, start, end, sector, municipality, source_type, limit)

    def get_topic(
        self,
        topic_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
    ) -> TopicSummary | None:
        events = self.db.fetch_events(start=start, end=end, source_type=source_type)
        return self.analytics.build_topic_lookup(events, start, end, sector, municipality, source_type).get(topic_id)

    def get_trends(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
    ) -> TrendsResponse:
        return self.analytics.build_trends(self.db.fetch_events(start=start, end=end), start, end, sector, municipality)

    def get_raw_events(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        source_type: str | None = None,
    ) -> RawEventsResponse:
        items = self.db.fetch_events(start=start, end=end, source_type=source_type)
        return RawEventsResponse(
            generated_at=datetime.now().astimezone(),
            region=self.region_config["region_name"],
            total_events=len(items),
            items=items,
        )

    def export_csv(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
    ) -> str:
        snapshot = self.get_top_issues(start, end, sector, municipality, source_type)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "rank",
                "topic_id",
                "label",
                "sector",
                "municipalities",
                "score",
                "event_count",
                "source_count",
                "bot_score",
                "contradiction_flag",
                "why_in_top",
            ],
        )
        writer.writeheader()
        for issue in snapshot.items:
            writer.writerow(
                {
                    "rank": issue.rank,
                    "topic_id": issue.topic.topic_id,
                    "label": issue.topic.label,
                    "sector": issue.topic.sector,
                    "municipalities": ", ".join(issue.topic.municipalities),
                    "score": issue.topic.score,
                    "event_count": issue.topic.event_count,
                    "source_count": issue.topic.source_count,
                    "bot_score": issue.topic.bot_score,
                    "contradiction_flag": issue.topic.contradiction_flag,
                    "why_in_top": " | ".join(issue.topic.why_in_top),
                }
            )
        return output.getvalue()

    def export_html(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
    ) -> str:
        snapshot = self.get_top_issues(start, end, sector, municipality, source_type)
        cards = []
        for issue in snapshot.items:
            cards.append(
                f"""
                <section class="topic-card">
                    <div class="badge">#{issue.rank}</div>
                    <h2>{issue.topic.label}</h2>
                    <p><strong>Сфера:</strong> {issue.topic.sector}</p>
                    <p><strong>Муниципалитеты:</strong> {", ".join(issue.topic.municipalities)}</p>
                    <p><strong>Score:</strong> {issue.topic.score}</p>
                    <p>{issue.topic.neutral_summary}</p>
                    <p><strong>Почему в топе:</strong> {"; ".join(issue.topic.why_in_top)}</p>
                </section>
                """
            )
        return f"""
        <html lang="ru">
        <head>
            <meta charset="utf-8" />
            <title>Отчёт Madrigal Regional Pulse</title>
            <style>
                body {{ font-family: Arial, sans-serif; background: linear-gradient(180deg, #f1f7f8 0%, #ffffff 100%); color: #0f1720; margin: 32px; }}
                .topic-card {{ background: white; border: 1px solid #d9e4e8; border-radius: 16px; padding: 20px; margin-bottom: 16px; box-shadow: 0 10px 30px rgba(15, 23, 32, 0.08); }}
                .badge {{ display: inline-block; background: #0f766e; color: white; padding: 6px 10px; border-radius: 999px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Топ проблем региона</h1>
            <p>Регион: {self.region_config["region_name"]}</p>
            <p>Дата генерации: {snapshot.generated_at:%d.%m.%Y %H:%M}</p>
            {"".join(cards)}
        </body>
        </html>
        """

    def filter_options(self) -> dict:
        events = self.db.fetch_events()
        sectors = sorted({self.analytics._classify_sector(event) for event in events if event.text})
        municipalities = sorted({event.municipality or self.analytics._extract_municipality(f"{event.title or ''} {event.text}") for event in events})
        return {
            "region": self.region_config["region_name"],
            "sectors": [value for value in sectors if value],
            "municipalities": [value for value in municipalities if value],
            "source_types": sorted({event.source_type for event in events}),
        }

    def _parse_payload(self, payload: bytes, filename: str) -> list[RawEvent]:
        if filename.lower().endswith(".csv"):
            records = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
        else:
            parsed = json.loads(payload.decode("utf-8"))
            records = parsed.get("events", parsed) if isinstance(parsed, dict) else parsed

        events: list[RawEvent] = []
        for record in records:
            if not record.get("event_id"):
                identity = record.get("external_id") or record.get("url") or record.get("title") or record.get("text", "")
                record["event_id"] = stable_event_id(record.get("source_name", "seed"), str(identity), record.get("published_at", ""))
            if not record.get("region"):
                record["region"] = self.region_config["region_name"]
            events.append(RawEvent.model_validate(record))
        return events
