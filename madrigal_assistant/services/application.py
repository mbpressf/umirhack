from __future__ import annotations

import csv
import io
import json
import re
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from madrigal_assistant.analytics import AnalyticsService
from madrigal_assistant.chat import RegionalChatProvider
from madrigal_assistant.embeddings import EmbeddingService
from madrigal_assistant.ingest import IngestionService
from madrigal_assistant.models import (
    ChatAskResponse,
    ChatMessage,
    ChatSessionDetailResponse,
    ChatSessionSummary,
    ChatSessionsResponse,
    ChatStatusResponse,
    ImportSeedResponse,
    IngestRunResult,
    ProblemCardsResponse,
    RawEvent,
    RawEventsResponse,
    SimilarTopicsResponse,
    TopIssuesResponse,
    TopicSummary,
    TrendsResponse,
)
from madrigal_assistant.settings import (
    get_auto_refresh_enabled,
    get_auto_refresh_interval_seconds,
    get_auto_refresh_max_per_source,
    get_chat_context_limit,
    get_chat_history_limit,
    get_config_path,
    get_db_path,
    get_seed_path,
    load_region_config,
)
from madrigal_assistant.storage import Database
from madrigal_assistant.text import shorten, stable_event_id, tokenize


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
        self.chat_provider = RegionalChatProvider()
        self.chat_context_limit = get_chat_context_limit()
        self.chat_history_limit = get_chat_history_limit()
        self.auto_refresh_enabled = get_auto_refresh_enabled()
        self.auto_refresh_interval_seconds = get_auto_refresh_interval_seconds()
        self.auto_refresh_max_per_source = get_auto_refresh_max_per_source()
        self._refresh_lock = threading.Lock()
        self._refresh_stop_event = threading.Event()
        self._refresh_thread: threading.Thread | None = None
        self._refresh_state: dict[str, Any] = {
            "enabled": self.auto_refresh_enabled,
            "running": False,
            "intervalSeconds": self.auto_refresh_interval_seconds,
            "maxPerSource": self.auto_refresh_max_per_source,
            "lastStartedAt": None,
            "lastFinishedAt": None,
            "nextScheduledAt": None,
            "lastError": None,
            "lastResult": None,
        }

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

    def run_ingest(self, max_per_source: int = 8, trigger: str = "manual") -> IngestRunResult:
        with self._refresh_lock:
            started_at = datetime.now().astimezone()
            self._refresh_state.update(
                {
                    "running": True,
                    "lastStartedAt": started_at.isoformat(),
                    "lastError": None,
                }
            )
            try:
                existing_ids = {event.event_id for event in self.db.fetch_events()}
                events, stats = self.ingestion.run(max_per_source=max_per_source)
                inserted, updated = self.db.upsert_events(events)
                for stat in stats:
                    if stat.status != "ok":
                        continue
                    source_events = [event for event in events if event.source_id == stat.source_id]
                    stat.updated = sum(1 for event in source_events if event.event_id in existing_ids)
                    stat.inserted = len(source_events) - stat.updated
                result = IngestRunResult(inserted=inserted, updated=updated, scanned=len(events), source_stats=stats)
                self._refresh_state["lastResult"] = {
                    "trigger": trigger,
                    "inserted": result.inserted,
                    "updated": result.updated,
                    "scanned": result.scanned,
                    "okSources": sum(1 for item in result.source_stats if item.status == "ok"),
                    "failedSources": sum(1 for item in result.source_stats if item.status != "ok"),
                }
                return result
            except Exception as error:
                self._refresh_state["lastError"] = str(error)
                raise
            finally:
                finished_at = datetime.now().astimezone()
                self._refresh_state["running"] = False
                self._refresh_state["lastFinishedAt"] = finished_at.isoformat()
                if self.auto_refresh_enabled:
                    self._refresh_state["nextScheduledAt"] = (
                        finished_at + timedelta(seconds=self.auto_refresh_interval_seconds)
                    ).isoformat()

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

    def pyrogram_status(self) -> dict[str, object]:
        return self.ingestion.pyrogram.status()

    def chat_status(self) -> ChatStatusResponse:
        return ChatStatusResponse(**self.chat_provider.status())

    def list_chat_sessions(self, user_id: int) -> ChatSessionsResponse:
        self._require_user(user_id)
        items = [
            ChatSessionSummary(**row)
            for row in self.db.list_chat_sessions(user_id)
        ]
        return ChatSessionsResponse(
            generated_at=datetime.now().astimezone(),
            items=items,
            status=self.chat_status(),
        )

    def get_chat_session_detail(self, user_id: int, session_id: int) -> ChatSessionDetailResponse:
        self._require_user(user_id)
        session = self.db.get_chat_session(session_id, user_id)
        if not session:
            raise ValueError("Chat session not found")
        messages = [ChatMessage(**row) for row in self.db.list_chat_messages(session_id, user_id)]
        return ChatSessionDetailResponse(
            generated_at=datetime.now().astimezone(),
            session=ChatSessionSummary(**session),
            messages=messages,
            status=self.chat_status(),
        )

    def ask_chat(self, user_id: int, message: str, session_id: int | None = None) -> ChatAskResponse:
        user = self._require_user(user_id)
        normalized_message = " ".join((message or "").split())
        if not normalized_message:
            raise ValueError("Message is empty")

        session = self.db.get_chat_session(session_id, user_id) if session_id else None
        if not session:
            session = self.db.create_chat_session(
                user_id=user_id,
                title=self._chat_title_from_message(normalized_message),
                provider=self.chat_status().provider,
            )
        if not session:
            raise ValueError("Unable to create chat session")

        user_message = self.db.create_chat_message(
            session_id=session["id"],
            role="user",
            content=normalized_message,
            provider="user",
        )
        if not user_message:
            raise ValueError("Unable to save user message")

        history_rows = self.db.list_chat_messages(session["id"], user_id)
        history = [
            {"role": row["role"], "content": row["content"]}
            for row in history_rows[:-1]
            if row["role"] in {"user", "assistant"}
        ][-self.chat_history_limit :]
        contexts = self._retrieve_chat_context(normalized_message)
        answer = self.chat_provider.answer(
            question=normalized_message,
            history=history,
            contexts=contexts,
        )
        assistant_message = self.db.create_chat_message(
            session_id=session["id"],
            role="assistant",
            content=answer["content"],
            provider=answer["provider"],
            citations=self._build_chat_citations(contexts),
        )
        if not assistant_message:
            raise ValueError("Unable to save assistant message")

        if len([row for row in history_rows if row["role"] == "user"]) <= 1:
            self.db.update_chat_session_title(
                session_id=session["id"],
                user_id=user_id,
                title=self._chat_title_from_message(normalized_message),
            )
            session = self.db.get_chat_session(session["id"], user_id) or session

        return ChatAskResponse(
            generated_at=datetime.now().astimezone(),
            session=ChatSessionSummary(**session),
            user_message=ChatMessage(**user_message),
            assistant_message=ChatMessage(**assistant_message),
            status=self.chat_status(),
        )

    def auto_refresh_status(self) -> dict[str, Any]:
        return dict(self._refresh_state)

    def start_auto_refresh(self) -> None:
        if not self.auto_refresh_enabled:
            return
        if self._refresh_thread and self._refresh_thread.is_alive():
            return
        self._refresh_stop_event.clear()
        self._refresh_state["nextScheduledAt"] = datetime.now().astimezone().isoformat()
        self._refresh_thread = threading.Thread(
            target=self._auto_refresh_loop,
            name="madrigal-auto-refresh",
            daemon=True,
        )
        self._refresh_thread.start()

    def stop_auto_refresh(self) -> None:
        self._refresh_stop_event.set()
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=2.0)

    def _auto_refresh_loop(self) -> None:
        while not self._refresh_stop_event.is_set():
            try:
                self.run_ingest(max_per_source=self.auto_refresh_max_per_source, trigger="auto")
            except Exception as error:
                self._refresh_state["lastError"] = str(error)
                next_run = datetime.now().astimezone() + timedelta(seconds=self.auto_refresh_interval_seconds)
                self._refresh_state["nextScheduledAt"] = next_run.isoformat()
            if self._refresh_stop_event.wait(self.auto_refresh_interval_seconds):
                break

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

    def get_frontend_snapshot(self) -> dict[str, Any]:
        all_events = self.db.fetch_events()
        if not all_events:
            return self._empty_frontend_snapshot()

        latest_seen = max(event.published_at for event in all_events)
        window_24h = (latest_seen - timedelta(hours=24), latest_seen)
        window_72h = (latest_seen - timedelta(hours=72), latest_seen)
        window_7d = (latest_seen - timedelta(days=7), latest_seen)
        window_30d = (latest_seen - timedelta(days=30), latest_seen)
        events_24h = self._events_in_window(all_events, *window_24h)
        events_72h = self._events_in_window(all_events, *window_72h)
        events_7d = self._events_in_window(all_events, *window_7d)
        events_30d = self._events_in_window(all_events, *window_30d)

        topics_7d = self.analytics.build_top_issues(events_7d, start=window_7d[0], end=window_7d[1], limit=24)
        cards_7d = self.analytics.build_problem_cards(events_7d, start=window_7d[0], end=window_7d[1], limit=24)
        topics_72h = self.analytics.build_top_issues(events_72h, start=window_72h[0], end=window_72h[1], limit=16)
        cards_72h = self.analytics.build_problem_cards(events_72h, start=window_72h[0], end=window_72h[1], limit=16)
        topic_lookup = {item.topic.topic_id: item.topic for item in topics_7d.items}
        topic_clusters = self.analytics.build_topic_lookup(events_7d, start=window_7d[0], end=window_7d[1])
        topic_lookup.update(topic_clusters)
        topic_lookup.update({item.topic.topic_id: item.topic for item in topics_72h.items})

        frontend_topics_week = [
            self._build_frontend_problem_entry(card, topic_lookup.get(card.topic_id))
            for card in cards_7d.items
        ]
        frontend_topics_recent = [
            self._build_frontend_problem_entry(card, topic_lookup.get(card.topic_id))
            for card in cards_72h.items
        ]
        frontend_topics = self._rerank_frontend_topics(
            self._merge_frontend_topics(
                self._sort_frontend_topics(frontend_topics_recent, latest_seen),
                self._sort_frontend_topics(frontend_topics_week, latest_seen),
            )
        )
        top_problems = frontend_topics[:10]

        municipalities = self._build_frontend_municipalities(frontend_topics)
        sources = self._build_frontend_sources(events_7d, topic_lookup, latest_seen)
        trends = {
            "24h": self._build_frontend_trends_window(*window_24h, bucket="4h", label="24 часа", events=events_24h),
            "7d": self._build_frontend_trends_window(*window_7d, bucket="1d", label="7 дней", events=events_7d),
            "30d": self._build_frontend_trends_window(*window_30d, bucket="7d", label="30 дней", events=events_30d),
        }

        critical_signals = [
            {
                "id": topic["id"],
                "time": self._format_time(topic["updatedAt"]),
                "title": topic["title"],
                "municipality": topic["municipality"],
                "source": " + ".join(topic["sourceTypes"][:2]) or "Источники уточняются",
                "priority": topic["priority"],
            }
            for topic in top_problems[:4]
        ]
        official_confirmed = sum(1 for topic in frontend_topics if topic["officialSignal"])
        top_sectors = [item["sector"] for item in trends["7d"]["sectorDynamics"][:2]]
        day_cards = self.analytics.build_problem_cards(events_24h, start=window_24h[0], end=window_24h[1], limit=16)
        day_summary = self._build_overview_summary(
            count=len(events_24h),
            topics=len(day_cards.items),
            top_sectors=top_sectors,
            latest_seen=latest_seen,
            period_label="24 часа",
        )
        week_summary = self._build_overview_summary(
            count=len(events_7d),
            topics=topics_7d.total_topics,
            top_sectors=top_sectors,
            latest_seen=latest_seen,
            period_label="7 дней",
        )

        return {
            "meta": {
                "regionName": self.region_config["region_name"],
                "pilot": True,
                "dataReady": bool(frontend_topics),
                "lastUpdate": latest_seen.strftime("%d.%m.%Y %H:%M"),
            },
            "kpi": {
                "totalTopics": topics_7d.total_topics,
                "newCriticalTopics": sum(
                    1 for topic in frontend_topics if topic["priority"] in {"Критический", "Высокий"}
                ),
                "municipalitiesWithSignals": len([item for item in municipalities if item["signals"] > 0]),
                "officialConfirmedShare": round((official_confirmed / max(len(frontend_topics), 1)) * 100),
            },
            "overviewSummary": {
                "day": day_summary,
                "week": week_summary,
            },
            "miniTrendLabels": trends["7d"]["timelineLabels"],
            "miniTrendSeries": trends["7d"]["volumeSeries"],
            "criticalSignals": critical_signals,
            "topProblems": top_problems,
            "topics": frontend_topics,
            "municipalities": municipalities,
            "trends": trends,
            "sources": sources,
            "reportPreview": self._build_report_preview(top_problems, week_summary),
        }

    @staticmethod
    def _events_in_window(events: list[RawEvent], start: datetime, end: datetime) -> list[RawEvent]:
        return [event for event in events if start <= event.published_at <= end]

    @staticmethod
    def _sort_frontend_topics(topics: list[dict[str, Any]], latest_seen: datetime) -> list[dict[str, Any]]:
        def sort_key(item: dict[str, Any]) -> tuple[float, float]:
            updated_at = datetime.fromisoformat(item["updatedAt"])
            age_hours = max(0.0, (latest_seen - updated_at).total_seconds() / 3600)
            if age_hours <= 24:
                freshness_bonus = 18.0
            elif age_hours <= 72:
                freshness_bonus = 12.0
            elif age_hours <= 168:
                freshness_bonus = 4.0
            else:
                freshness_bonus = 0.0
            priority_bonus = {
                "Критический": 6.0,
                "Высокий": 4.0,
                "Средний": 2.0,
                "Наблюдение": 0.0,
            }.get(item.get("priority"), 0.0)
            official_bonus = 1.5 if item.get("officialSignal") else 0.0
            return (
                float(item.get("score", 0)) + freshness_bonus + priority_bonus + official_bonus,
                updated_at.timestamp(),
            )

        return sorted(topics, key=sort_key, reverse=True)

    @staticmethod
    def _merge_frontend_topics(*topic_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for group in topic_groups:
            for item in group:
                topic_id = item.get("id")
                if not topic_id or topic_id in seen_ids:
                    continue
                seen_ids.add(topic_id)
                merged.append(dict(item))
        return merged

    @staticmethod
    def _rerank_frontend_topics(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for index, item in enumerate(topics, start=1):
            ranked_item = dict(item)
            ranked_item["rank"] = index
            ranked.append(ranked_item)
        return ranked

    def _empty_frontend_snapshot(self) -> dict[str, Any]:
        return {
            "meta": {
                "regionName": self.region_config["region_name"],
                "pilot": True,
                "dataReady": False,
                "lastUpdate": "Данные ещё не собраны",
            },
            "kpi": {
                "totalTopics": 0,
                "newCriticalTopics": 0,
                "municipalitiesWithSignals": 0,
                "officialConfirmedShare": 0,
            },
            "overviewSummary": {
                "day": "Пока нет данных по последним 24 часам.",
                "week": "После первого сбора появится недельная аналитическая сводка.",
            },
            "miniTrendLabels": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
            "miniTrendSeries": [0, 0, 0, 0, 0, 0, 0],
            "criticalSignals": [],
            "topProblems": [],
            "topics": [],
            "municipalities": [],
            "trends": {
                "24h": self._empty_trend_window("24 часа", ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"]),
                "7d": self._empty_trend_window("7 дней", ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]),
                "30d": self._empty_trend_window("30 дней", ["Нед 1", "Нед 2", "Нед 3", "Нед 4", "Нед 5"]),
            },
            "sources": [],
            "reportPreview": "После загрузки данных здесь появится превью региональной сводки.",
        }

    @staticmethod
    def _empty_trend_window(label: str, timeline_labels: list[str]) -> dict[str, Any]:
        return {
            "label": label,
            "timelineLabels": timeline_labels,
            "volumeSeries": [0 for _ in timeline_labels],
            "spikes": [],
            "sectorDynamics": [],
            "geographyGrowth": [],
            "complaintGrowth": 0,
        }

    def _build_frontend_problem_entry(self, card: Any, topic: TopicSummary | None) -> dict[str, Any]:
        municipality = self._pick_problem_municipality(card)
        source_types = self._build_problem_source_types(card)
        breakdown = topic.score_breakdown if topic else None
        factors = {
            "intensity": round((breakdown.surge if breakdown else 0.5) * 100),
            "coverage": round((((breakdown.diversity if breakdown else 0.45) + (breakdown.geography if breakdown else 0.4)) / 2) * 100),
            "socialImpact": round((((breakdown.citizen_volume if breakdown else 0.5) + (breakdown.severity if breakdown else 0.55)) / 2) * 100),
            "officialGap": round(max((0.85 if card.contradiction_flag else 0.4), card.bot_score) * 100),
        }
        priority = self._priority_label(card.urgency, card.score or 0, card.contradiction_flag)
        return {
            "id": card.topic_id,
            "rank": card.rank,
            "title": card.title,
            "summary": card.summary,
            "sector": card.sector,
            "municipality": municipality,
            "priority": priority,
            "score": round(card.score or 0),
            "whyTop": "; ".join(card.why_now) if card.why_now else "Тема попала в топ по совокупности силы сигнала и подтверждённости.",
            "sourceCount": topic.source_count if topic else len({item.source_name for item in card.evidence}),
            "officialSignal": bool(card.latest_official_update or card.source_mix.official),
            "contradiction": card.contradiction_flag,
            "spamRisk": card.bot_score >= 0.45,
            "periodLabel": f"{card.first_seen:%d.%m %H:%M} — {card.last_seen:%d.%m %H:%M}",
            "updatedAt": card.last_seen.isoformat(),
            "sourceTypes": source_types,
            "factors": factors,
            "snippets": card.key_facts[:3],
            "sources": [
                {
                    "name": evidence.source_name,
                    "type": self._frontend_source_type_label(evidence.source_type, evidence.source_name),
                    "status": self._frontend_source_status_label(evidence.source_type),
                    "timestamp": evidence.published_at.strftime("%d.%m %H:%M"),
                }
                for evidence in card.evidence
            ],
            "timeline": [
                {
                    "date": item.published_at.strftime("%d.%m"),
                    "event": item.snippet,
                }
                for item in card.timeline
            ],
            "trend": self._sparkline_points(card, topic),
            "confidence": card.confidence,
            "verificationState": card.verification_state,
            "status": card.status,
        }

    def _build_frontend_municipalities(self, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for topic in topics:
            grouped[topic["municipality"]].append(topic)
        municipalities = []
        for name, items in grouped.items():
            signal_total = sum(max(item["score"], 1) for item in items)
            critical_total = sum(1 for item in items if item["priority"] in {"Критический", "Высокий"})
            top_topic = max(items, key=lambda item: item["score"])
            municipalities.append(
                {
                    "name": name,
                    "signals": signal_total,
                    "critical": critical_total,
                    "topTopic": top_topic["title"],
                    "level": round(min(1.0, signal_total / 120), 2),
                }
            )
        return sorted(municipalities, key=lambda item: item["signals"], reverse=True)

    def _build_frontend_sources(
        self,
        events: list[RawEvent],
        topics: dict[str, TopicSummary],
        latest_seen: datetime,
    ) -> list[dict[str, Any]]:
        catalog = {
            item.get("id"): item
            for item in self.get_source_catalog()
        }
        topic_count_by_source: Counter[str] = Counter()
        for topic in topics.values():
            for source_name in topic.sources:
                topic_count_by_source[source_name] += 1

        source_totals: dict[str, dict[str, Any]] = {}
        total_events = max(len(events), 1)
        for event in events:
            key = event.source_name
            entry = source_totals.setdefault(
                key,
                {
                    "id": event.source_id or self._slugify(key),
                    "name": key,
                    "type": self._frontend_source_type_label(event.source_type, key),
                    "status": self._frontend_source_status_label(event.source_type),
                    "count": 0,
                    "last_seen": event.published_at,
                    "source_id": event.source_id,
                },
            )
            entry["count"] += 1
            if event.published_at > entry["last_seen"]:
                entry["last_seen"] = event.published_at

        items = []
        for entry in source_totals.values():
            catalog_item = catalog.get(entry["source_id"] or "")
            reliability = self._source_reliability(entry["status"], catalog_item)
            items.append(
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "type": entry["type"],
                    "status": entry["status"],
                    "share": round((entry["count"] / total_events) * 100),
                    "topicCount": topic_count_by_source.get(entry["name"], 0),
                    "reliability": reliability,
                    "lastSeen": entry["last_seen"].strftime("%d.%m %H:%M"),
                }
            )
        items.sort(key=lambda item: (item["share"], item["topicCount"], item["reliability"]), reverse=True)
        return items

    def _build_frontend_trends_window(
        self,
        start: datetime,
        end: datetime,
        bucket: str,
        label: str,
        events: list[RawEvent] | None = None,
    ) -> dict[str, Any]:
        events = events if events is not None else self.db.fetch_events(start=start, end=end)
        if not events:
            return self._empty_trend_window(label, [])

        bucket_starts, timeline_labels = self._build_time_buckets(start, end, bucket)
        volume_series = [0 for _ in bucket_starts]
        bucket_index = {bucket_start: index for index, bucket_start in enumerate(bucket_starts)}
        sector_counts: Counter[str] = Counter()
        municipality_counts: Counter[str] = Counter()
        complaint_events = 0

        for event in events:
            current_bucket = self._bucket_start(event.published_at, start, bucket)
            index = bucket_index.get(current_bucket)
            if index is not None:
                volume_series[index] += 1
            sector = self.analytics._classify_sector(event)
            sector_counts[sector] += 1
            municipality = event.municipality or self.analytics._extract_municipality(f"{event.title or ''} {event.text}") or "unknown"
            if municipality != "unknown":
                municipality_counts[municipality] += 1
            text = f"{event.title or ''} {event.text}".lower()
            if any(marker in text for marker in ("жалоб", "перебо", "авар", "очеред", "отключ", "проблем")):
                complaint_events += 1

        spikes = self._build_spikes(events, start, end)
        sector_total = max(sum(sector_counts.values()), 1)
        sector_dynamics = [
            {
                "sector": sector,
                "change": round((count / sector_total) * 100),
                "volume": count,
            }
            for sector, count in sector_counts.most_common(5)
        ]
        geography_growth = [
            {
                "municipality": municipality,
                "growth": round((count / max(len(events), 1)) * 100),
            }
            for municipality, count in municipality_counts.most_common(6)
        ]
        complaint_growth = round((complaint_events / max(len(events), 1)) * 100)
        return {
            "label": label,
            "timelineLabels": timeline_labels,
            "volumeSeries": volume_series,
            "spikes": spikes,
            "sectorDynamics": sector_dynamics,
            "geographyGrowth": geography_growth,
            "complaintGrowth": complaint_growth,
        }

    def _build_time_buckets(self, start: datetime, end: datetime, bucket: str) -> tuple[list[datetime], list[str]]:
        current = start
        bucket_starts: list[datetime] = []
        labels: list[str] = []
        step = timedelta(hours=4) if bucket == "4h" else timedelta(days=1) if bucket == "1d" else timedelta(days=7)
        while current <= end:
            bucket_starts.append(current)
            if bucket == "4h":
                labels.append(current.strftime("%H:%M"))
            elif bucket == "1d":
                labels.append(current.strftime("%d.%m"))
            else:
                labels.append(f"Нед {len(labels) + 1}")
            current += step
        return bucket_starts, labels

    def _bucket_start(self, value: datetime, start: datetime, bucket: str) -> datetime:
        if bucket == "4h":
            elapsed_hours = int((value - start).total_seconds() // 14400)
            return start + timedelta(hours=elapsed_hours * 4)
        if bucket == "1d":
            elapsed_days = int((value - start).total_seconds() // 86400)
            return start + timedelta(days=elapsed_days)
        elapsed_weeks = int((value - start).total_seconds() // (86400 * 7))
        return start + timedelta(days=elapsed_weeks * 7)

    def _build_spikes(self, events: list[RawEvent], start: datetime, end: datetime) -> list[dict[str, str]]:
        topics = self.get_top_issues(start=start, end=end, limit=3)
        spikes = []
        for item in topics.items[:3]:
            spikes.append(
                {
                    "time": item.topic.last_seen.strftime("%d.%m"),
                    "title": item.topic.label,
                    "growth": f"+{round(item.topic.score or 0)}%",
                }
            )
        return spikes

    def _build_problem_source_types(self, card: Any) -> list[str]:
        labels: list[str] = []
        if card.source_mix.media:
            labels.append("СМИ")
        if card.source_mix.social:
            if any("vk" in item.source_name.lower() for item in card.evidence):
                labels.append("ВКонтакте")
            if any("telegram" in item.source_name.lower() for item in card.evidence):
                labels.append("Telegram")
            if not labels:
                labels.append("Публичные обращения")
        if card.source_mix.official:
            labels.append("Официальный")
        return labels or ["Публичные обращения"]

    def _pick_problem_municipality(self, card: Any) -> str:
        combined = " ".join([card.title, card.summary, card.latest_citizen_signal or "", card.latest_official_update or ""]).lower()
        for municipality in card.municipalities:
            if municipality and municipality.lower() in combined:
                return municipality
        return card.primary_municipality or (card.municipalities[0] if card.municipalities else "unknown")

    @staticmethod
    def _priority_label(urgency: str, score: float, contradiction_flag: bool) -> str:
        if urgency == "high" or score >= 70 or contradiction_flag:
            return "Критический"
        if score >= 50:
            return "Высокий"
        if score >= 30:
            return "Средний"
        return "Наблюдение"

    @staticmethod
    def _sparkline_points(card: Any, topic: TopicSummary | None) -> list[int]:
        timeline_len = max(len(card.timeline), 3)
        base = round(card.score or 0)
        if topic and topic.score_breakdown:
            surge = round(topic.score_breakdown.surge * 18)
            diversity = round(topic.score_breakdown.diversity * 12)
        else:
            surge = 8
            diversity = 6
        points = []
        for index in range(min(max(timeline_len, 5), 7)):
            points.append(max(4, min(100, base - 16 + index * surge // 2 + diversity)))
        return points

    @staticmethod
    def _frontend_source_type_label(source_type: str, source_name: str) -> str:
        lowered_name = source_name.lower()
        if source_type == "official":
            return "Официальный"
        if "telegram" in lowered_name:
            return "Telegram"
        if "vk" in lowered_name:
            return "ВКонтакте"
        if source_type == "media":
            return "СМИ"
        return "Публичные обращения"

    @staticmethod
    def _frontend_source_status_label(source_type: str) -> str:
        if source_type == "official":
            return "Официальный"
        if source_type == "media":
            return "СМИ"
        return "Пользовательский"

    @staticmethod
    def _source_reliability(status: str, catalog_item: dict[str, Any] | None) -> float:
        base = 0.95 if status == "Официальный" else 0.82 if status == "СМИ" else 0.7
        if catalog_item and catalog_item.get("status") == "stable":
            base += 0.05
        return round(min(base, 0.99), 2)

    @staticmethod
    def _format_time(iso_value: str) -> str:
        try:
            return datetime.fromisoformat(iso_value).strftime("%H:%M")
        except ValueError:
            return iso_value

    @staticmethod
    def _build_overview_summary(
        count: int,
        topics: int,
        top_sectors: list[str],
        latest_seen: datetime,
        period_label: str,
    ) -> str:
        sectors = ", ".join(top_sectors) if top_sectors else "приоритетных секторах"
        return (
            f"За {period_label} в регионе зафиксировано {count} публичных сигналов и {topics} тематических кластеров. "
            f"Наибольшая плотность обсуждений сейчас наблюдается в блоках {sectors}. "
            f"Последнее обновление данных: {latest_seen:%d.%m.%Y %H:%M}."
        )

    @staticmethod
    def _build_report_preview(top_problems: list[dict[str, Any]], week_summary: str) -> str:
        if not top_problems:
            return "Топ-проблемы ещё не сформированы."
        leaders = "; ".join(item["title"] for item in top_problems[:3])
        return f"{week_summary} Ключевые темы недели: {leaders}."

    def _require_user(self, user_id: int) -> dict[str, Any]:
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        return user

    @staticmethod
    def _chat_title_from_message(message: str) -> str:
        compact = " ".join((message or "").split())
        if not compact:
            return "Новый диалог"
        return shorten(compact, 60)

    def _retrieve_chat_context(self, message: str) -> list[dict[str, Any]]:
        all_events = self.db.fetch_events()
        if not all_events:
            return []
        latest_seen = max(event.published_at for event in all_events)
        window_start = latest_seen - timedelta(days=14)
        events = [event for event in all_events if event.published_at >= window_start]
        cards = self.analytics.build_problem_cards(
            events,
            start=window_start,
            end=latest_seen,
            limit=32,
        )
        query_tokens = set(tokenize(message))
        query_municipality = self.analytics._extract_municipality(message)
        normalized_query = message.lower()
        scored: list[tuple[float, Any]] = []
        for card in cards.items:
            score = self._score_chat_card(
                card,
                query_tokens,
                latest_seen,
                query_municipality=query_municipality,
                official_required="официал" in normalized_query,
            )
            if score <= 0:
                continue
            scored.append((score, card))
        if not scored:
            return [self._chat_context_from_card(card) for card in cards.items[: self.chat_context_limit]]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            self._chat_context_from_card(card)
            for _, card in scored[: self.chat_context_limit]
        ]

    def _score_chat_card(
        self,
        card: Any,
        query_tokens: set[str],
        latest_seen: datetime,
        *,
        query_municipality: str | None,
        official_required: bool,
    ) -> float:
        haystack = " ".join(
            [
                card.title,
                card.summary,
                card.sector,
                card.primary_municipality,
                " ".join(card.key_facts),
                " ".join(item.snippet for item in card.evidence[:4]),
            ]
        ).lower()
        token_hits = sum(1 for token in query_tokens if token in haystack)
        token_ratio = token_hits / max(len(query_tokens), 1)
        age_hours = max(0.0, (latest_seen - card.last_seen).total_seconds() / 3600)
        freshness = 1.0 if age_hours <= 24 else 0.75 if age_hours <= 72 else 0.45 if age_hours <= 168 else 0.2
        source_bonus = min(1.0, len(card.evidence) / 4)
        official_bonus = 0.15 if card.latest_official_update else 0.0
        base = (card.score or 0) / 100
        municipality_bonus = 0.0
        if query_municipality and query_municipality != "unknown":
            if (card.primary_municipality or "").lower() == query_municipality.lower():
                municipality_bonus = 0.45
            elif query_tokens and token_hits == 0:
                return 0.0
        if query_tokens and token_hits == 0:
            municipality_hit = any(token in (card.primary_municipality or "").lower() for token in query_tokens)
            sector_hit = any(token in (card.sector or "").lower() for token in query_tokens)
            if not municipality_hit and not sector_hit:
                return 0.0
        score = token_ratio * 0.5 + freshness * 0.18 + source_bonus * 0.12 + base * 0.1 + official_bonus + municipality_bonus
        if official_required and not card.latest_official_update:
            score *= 0.75
        return round(score, 4)

    def _chat_context_from_card(self, card: Any) -> dict[str, Any]:
        why = "; ".join(card.why_now[:3]) if card.why_now else "Тема выделена по совокупности силы сигнала и подтверждений."
        return {
            "topic_id": card.topic_id,
            "title": card.title,
            "municipality": card.primary_municipality,
            "sector": card.sector,
            "summary": card.summary,
            "why": why,
            "last_seen": card.last_seen.isoformat(),
            "sources": [
                {
                    "source_name": evidence.source_name,
                    "source_type": evidence.source_type,
                    "published_at": evidence.published_at.isoformat(),
                    "url": evidence.url,
                    "snippet": evidence.snippet,
                }
                for evidence in card.evidence[:3]
            ],
        }

    @staticmethod
    def _build_chat_citations(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for context in contexts:
            for source in context.get("sources", [])[:1]:
                citations.append(
                    {
                        "topic_id": context.get("topic_id"),
                        "title": context.get("title"),
                        "municipality": context.get("municipality"),
                        "source_name": source.get("source_name"),
                        "source_type": source.get("source_type"),
                        "published_at": source.get("published_at"),
                        "url": source.get("url"),
                        "snippet": source.get("snippet"),
                    }
                )
                break
        return citations

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
