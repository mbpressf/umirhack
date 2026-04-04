from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
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

    def get_frontend_snapshot(self) -> dict[str, Any]:
        all_events = self.db.fetch_events()
        if not all_events:
            return self._empty_frontend_snapshot()

        latest_seen = max(event.published_at for event in all_events)
        window_24h = (latest_seen - timedelta(hours=24), latest_seen)
        window_7d = (latest_seen - timedelta(days=7), latest_seen)
        window_30d = (latest_seen - timedelta(days=30), latest_seen)

        topics_7d = self.get_top_issues(start=window_7d[0], end=window_7d[1], limit=24)
        cards_7d = self.get_problem_cards(start=window_7d[0], end=window_7d[1], limit=24)
        topic_lookup = {item.topic.topic_id: item.topic for item in topics_7d.items}
        topic_clusters = self.analytics.build_topic_lookup(
            self.db.fetch_events(start=window_7d[0], end=window_7d[1]),
            start=window_7d[0],
            end=window_7d[1],
        )
        topic_lookup.update(topic_clusters)

        frontend_topics = [
            self._build_frontend_problem_entry(card, topic_lookup.get(card.topic_id))
            for card in cards_7d.items
        ]
        top_problems = frontend_topics[:10]

        municipalities = self._build_frontend_municipalities(frontend_topics)
        sources = self._build_frontend_sources(
            self.db.fetch_events(start=window_7d[0], end=window_7d[1]),
            topic_lookup,
            latest_seen,
        )
        trends = {
            "24h": self._build_frontend_trends_window(*window_24h, bucket="4h", label="24 часа"),
            "7d": self._build_frontend_trends_window(*window_7d, bucket="1d", label="7 дней"),
            "30d": self._build_frontend_trends_window(*window_30d, bucket="7d", label="30 дней"),
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
        day_summary = self._build_overview_summary(
            count=len(self.db.fetch_events(start=window_24h[0], end=window_24h[1])),
            topics=len(self.get_problem_cards(start=window_24h[0], end=window_24h[1], limit=16).items),
            top_sectors=top_sectors,
            latest_seen=latest_seen,
            period_label="24 часа",
        )
        week_summary = self._build_overview_summary(
            count=len(self.db.fetch_events(start=window_7d[0], end=window_7d[1])),
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
    ) -> dict[str, Any]:
        events = self.db.fetch_events(start=start, end=end)
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
