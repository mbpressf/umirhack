from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from madrigal_assistant.analytics import AnalyticsService
from madrigal_assistant.embeddings import EmbeddingService
from madrigal_assistant.ingest import IngestionService
from madrigal_assistant.models import ImportSeedResponse, IngestRunResult, ProblemCardsResponse, RawEvent, RawEventsResponse, SimilarTopicsResponse, TopIssuesResponse, TopicSummary, TrendsResponse
from madrigal_assistant.settings import get_config_path, get_db_path, get_seed_path, load_region_config
from madrigal_assistant.storage import Database
from madrigal_assistant.text import stable_event_id


class RegionalPulseService:
    def __init__(
        self,
        db_path: Path | None = None,
        config_path: Path | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.config_path = config_path or get_config_path()
        self.region_config = load_region_config(self.config_path)
        self.db = Database(db_path or get_db_path())
        self.db.init()
        self.ingestion = IngestionService(self.region_config)
        self.embedding_service = embedding_service or EmbeddingService()
        self.analytics = AnalyticsService(self.region_config, embedding_service=self.embedding_service)

    def import_seed(self, upload_bytes: bytes | None = None, filename: str | None = None) -> ImportSeedResponse:
        source = filename or str(get_seed_path())
        payload = upload_bytes if upload_bytes is not None else get_seed_path().read_bytes()
        events = self._parse_payload(payload, filename or get_seed_path().name)
        inserted, updated = self.db.upsert_events(events)
        return ImportSeedResponse(imported=inserted, updated=updated, source=source)

    def import_manual(self, upload_bytes: bytes, filename: str) -> ImportSeedResponse:
        events = self._parse_payload(upload_bytes, filename)
        inserted, updated = self.db.upsert_events(events)
        return ImportSeedResponse(imported=inserted, updated=updated, source=filename)

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

    def get_problem_cards(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 10,
    ) -> ProblemCardsResponse:
        events = self.db.fetch_events(start=start, end=end, source_type=source_type)
        return self.analytics.build_problem_cards(events, start, end, sector, municipality, source_type, limit)

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

    def get_similar_topics(
        self,
        topic_id: str | None = None,
        query: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 5,
    ) -> SimilarTopicsResponse:
        events = self.db.fetch_events(start=start, end=end, source_type=source_type)
        return self.analytics.build_similar_topics(
            events,
            topic_id=topic_id,
            query=query,
            start=start,
            end=end,
            sector=sector,
            municipality=municipality,
            source_type=source_type,
            limit=limit,
        )

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

    def embedding_layer_status(self) -> dict[str, object]:
        return self.embedding_service.status().as_dict()

    def get_source_catalog(self) -> list[dict[str, Any]]:
        return self.region_config.get("source_catalog", [])

    def source_catalog_summary(self) -> dict[str, int]:
        catalog = self.get_source_catalog()
        counts = Counter(item.get("status", "candidate") for item in catalog)
        return {
            "total": len(catalog),
            "stable": counts.get("stable", 0),
            "candidate": counts.get("candidate", 0),
            "blocked": counts.get("blocked", 0),
            "live_enabled": sum(1 for item in catalog if item.get("enabled_in_live_config")),
        }

    def _parse_payload(self, payload: bytes, filename: str) -> list[RawEvent]:
        text_payload = self._decode_payload(payload)
        lower_name = filename.lower()
        if lower_name.endswith(".csv"):
            records = list(csv.DictReader(io.StringIO(text_payload)))
        elif lower_name.endswith(".jsonl"):
            records = [json.loads(line) for line in text_payload.splitlines() if line.strip()]
        else:
            parsed = json.loads(text_payload)
            if isinstance(parsed, dict):
                records = parsed.get("events") or parsed.get("items") or parsed.get("records") or parsed.get("posts") or parsed
            else:
                records = parsed
        if isinstance(records, dict):
            records = [records]

        events: list[RawEvent] = []
        for record in records:
            normalized = self._normalize_record(record, filename)
            events.append(RawEvent.model_validate(normalized))
        return events

    @staticmethod
    def _decode_payload(payload: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="ignore")

    def _normalize_record(self, record: dict[str, Any], filename: str) -> dict[str, Any]:
        known_keys = {
            "event_id",
            "external_id",
            "url",
            "source_id",
            "source_type",
            "source_name",
            "region",
            "published_at",
            "title",
            "text",
            "author",
            "municipality",
            "engagement",
            "is_official",
            "metadata",
        }
        source_name = self._pick_first(record, "source_name", "source", "group_name", "community", "channel", "publisher")
        source_name = source_name or Path(filename).stem.replace("_", " ")
        source_type = self._pick_first(record, "source_type", "kind", "type")
        source_type = (str(source_type).strip().lower() if source_type else self._default_source_type(source_name, record))
        source_id = self._pick_first(record, "source_id", "source_slug", "group_domain", "channel_id")
        source_id = source_id or self._slugify(source_name)
        external_id = self._pick_first(record, "external_id", "post_id", "guid", "id")
        published_at = self._parse_published_at(
            self._pick_first(record, "published_at", "published", "date", "created_at", "timestamp", "post_date")
        )
        text = self._pick_first(record, "text", "message", "content", "description", "body", "post_text", "caption")
        title = self._pick_first(record, "title", "headline", "subject")
        if not text:
            text = title or ""
        if not title:
            title = text.split(".")[0][:120].strip() if text else source_name
        url = self._pick_first(record, "url", "link", "post_url", "permalink")
        if not url:
            identity = external_id or title or text or source_name
            url = f"manual://{source_id}/{self._slugify(str(identity)) or 'event'}"
        municipality = self._pick_first(record, "municipality", "municipality_name", "city", "district", "locality")
        engagement = self._pick_first(record, "engagement", "views", "view_count", "reach")
        is_official = self._coerce_bool(self._pick_first(record, "is_official", "official", "isOfficial"))

        normalized = {
            "event_id": record.get("event_id"),
            "external_id": str(external_id) if external_id is not None else None,
            "url": str(url),
            "source_id": str(source_id),
            "source_type": source_type,
            "source_name": str(source_name),
            "region": record.get("region") or self.region_config["region_name"],
            "published_at": published_at,
            "title": title,
            "text": text,
            "author": self._pick_first(record, "author", "author_name", "user", "sender"),
            "municipality": municipality,
            "engagement": self._coerce_int(engagement),
            "is_official": is_official,
            "metadata": record.get("metadata", {}),
        }

        metadata = dict(normalized["metadata"]) if isinstance(normalized["metadata"], dict) else {"raw_metadata": normalized["metadata"]}
        for key, value in record.items():
            if key in known_keys or value in (None, ""):
                continue
            metadata[key] = value
        normalized["metadata"] = metadata

        if not normalized["event_id"]:
            identity = normalized["external_id"] or normalized["url"] or normalized["title"] or normalized["text"]
            normalized["event_id"] = stable_event_id(normalized["source_id"], str(identity), normalized["published_at"].isoformat())
        return normalized

    @staticmethod
    def _pick_first(record: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = record.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        normalized = str(value).strip().lower()
        return normalized in {"1", "true", "yes", "y", "да"}

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        digits = re.sub(r"[^\d]", "", str(value))
        return int(digits) if digits else None

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^0-9a-zа-яё]+", "-", value.lower(), flags=re.IGNORECASE).strip("-")
        return slug or "manual-source"

    @staticmethod
    def _parse_published_at(raw_value: Any) -> datetime:
        if isinstance(raw_value, datetime):
            return raw_value if raw_value.tzinfo else raw_value.astimezone()
        if isinstance(raw_value, (int, float)):
            return datetime.fromtimestamp(raw_value).astimezone()
        if isinstance(raw_value, str):
            stripped = raw_value.strip()
            if stripped.isdigit():
                return datetime.fromtimestamp(int(stripped)).astimezone()
            return datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        return datetime.now().astimezone()

    def _default_source_type(self, source_name: str, record: dict[str, Any]) -> str:
        haystack = " ".join(
            str(value)
            for value in (
                source_name,
                record.get("url"),
                record.get("source"),
                record.get("group_name"),
            )
            if value
        ).lower()
        if any(marker in haystack for marker in ("vk.com", "telegram", "t.me", "max", "чат")):
            return "social"
        if any(marker in haystack for marker in ("администрац", "правительств", "мчс", "официаль")):
            return "official"
        return "media"
