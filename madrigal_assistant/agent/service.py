from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from madrigal_assistant.models import IngestSourceStat, RawEvent, TopIssuesResponse
from madrigal_assistant.settings import ROOT_DIR

DEFAULT_SOURCE_CATALOG_PATH = ROOT_DIR / "config" / "source_catalog.rostov.json"


class MonitoringAgent:
    def __init__(self, region_name: str, source_catalog_path: Path | None = None):
        self.region_name = region_name
        self.source_catalog_path = source_catalog_path or DEFAULT_SOURCE_CATALOG_PATH
        self.source_catalog = self._load_catalog()

    def build_briefing(
        self,
        top_issues: TopIssuesResponse,
        raw_events: list[RawEvent],
        source_stats: list[IngestSourceStat] | None = None,
    ) -> dict[str, Any]:
        sector_distribution = Counter(issue.topic.sector for issue in top_issues.items)
        contradictions = [issue for issue in top_issues.items if issue.topic.contradiction_flag]
        noisy_topics = [issue for issue in top_issues.items if issue.topic.bot_score >= 0.45]
        official_sources = sum(1 for event in raw_events if event.is_official)
        citizen_sources = sum(1 for event in raw_events if not event.is_official)

        top_sector = sector_distribution.most_common(1)[0][0] if sector_distribution else "Прочее"
        summary = (
            f"По {self.region_name} сейчас в топе {len(top_issues.items)} тем. "
            f"Наиболее заметная сфера: {top_sector}. "
            f"Официальных сигналов: {official_sources}, пользовательских сообщений: {citizen_sources}."
        )

        return {
            "generated_at": datetime.now().astimezone().isoformat(),
            "region": self.region_name,
            "executive_summary": summary,
            "urgent_topics": [
                {
                    "rank": issue.rank,
                    "topic_id": issue.topic.topic_id,
                    "label": issue.topic.label,
                    "sector": issue.topic.sector,
                    "municipalities": issue.topic.municipalities,
                    "score": issue.topic.score,
                    "why_in_top": issue.topic.why_in_top,
                    "bot_score": issue.topic.bot_score,
                    "contradiction_flag": issue.topic.contradiction_flag,
                    "source_count": issue.topic.source_count,
                }
                for issue in top_issues.items[:5]
            ],
            "sector_distribution": dict(sector_distribution),
            "contradictions": [
                {
                    "rank": issue.rank,
                    "label": issue.topic.label,
                    "municipalities": issue.topic.municipalities,
                    "sources": issue.topic.sources,
                }
                for issue in contradictions
            ],
            "spam_watchlist": [
                {
                    "rank": issue.rank,
                    "label": issue.topic.label,
                    "bot_score": issue.topic.bot_score,
                }
                for issue in noisy_topics
            ],
            "source_health": self._source_health(source_stats or []),
            "next_collection_targets": self._prioritized_collection_targets(limit=6),
            "team_handoff": {
                "frontend": "Показывает top-10, карточку темы, why-in-top, source health и next collection targets.",
                "data_ml": "Расширяет сбор и улучшает дедупликацию, contradiction-логику, sector rules и bot-penalty.",
                "backend": "Поднимает jobs для планового ingest, хранение source health и выдачу briefing через API.",
            },
        }

    def to_markdown(self, briefing: dict[str, Any]) -> str:
        urgent_lines = []
        for item in briefing["urgent_topics"]:
            urgent_lines.append(
                f"- #{item['rank']} {item['label']} | {item['sector']} | {', '.join(item['municipalities'])} | score {item['score']}"
            )
        contradiction_lines = [
            f"- {item['label']} ({', '.join(item['municipalities'])})"
            for item in briefing["contradictions"]
        ] or ["- Не зафиксированы."]
        target_lines = [
            f"- {item['name']} | {item['status']} | {item['notes']}"
            for item in briefing["next_collection_targets"]
        ]
        health_lines = [
            f"- {item['source_name']}: {item['status']} (scanned={item['scanned']}, inserted={item['inserted']}, updated={item['updated']})"
            for item in briefing["source_health"]
        ] or ["- Нет данных о последнем ingest."]

        return "\n".join(
            [
                f"# Briefing: {briefing['region']}",
                "",
                briefing["executive_summary"],
                "",
                "## Срочные темы",
                *urgent_lines,
                "",
                "## Темы с противоречиями",
                *contradiction_lines,
                "",
                "## Здоровье источников",
                *health_lines,
                "",
                "## Следующие источники на подключение",
                *target_lines,
            ]
        )

    def _load_catalog(self) -> list[dict[str, Any]]:
        if not self.source_catalog_path.exists():
            return []
        payload = json.loads(self.source_catalog_path.read_text(encoding="utf-8"))
        return payload.get("sources", payload)

    def _source_health(self, source_stats: list[IngestSourceStat]) -> list[dict[str, Any]]:
        return [
            {
                "source_id": item.source_id,
                "source_name": item.source_name,
                "status": item.status,
                "scanned": item.scanned,
                "inserted": item.inserted,
                "updated": item.updated,
                "error": item.error,
            }
            for item in source_stats
        ]

    def _prioritized_collection_targets(self, limit: int = 6) -> list[dict[str, Any]]:
        candidates = sorted(
            self.source_catalog,
            key=lambda item: (
                0 if item.get("status") == "candidate" else 1,
                item.get("priority", 99),
                item.get("name", ""),
            ),
        )
        next_targets = []
        for item in candidates:
            if item.get("enabled_in_live_config"):
                continue
            next_targets.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "status": item.get("status"),
                    "priority": item.get("priority"),
                    "notes": item.get("notes", ""),
                }
            )
            if len(next_targets) >= limit:
                break
        return next_targets
