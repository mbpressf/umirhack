from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from madrigal_assistant.models import (
    ProblemCard,
    ProblemCardsResponse,
    RawEvent,
    ScoreBreakdown,
    SourceMix,
    TopicEvidence,
    TopicSummary,
    TopIssue,
    TopIssuesResponse,
    TrendPoint,
    TrendSeries,
    TrendsResponse,
)
from madrigal_assistant.text import normalize_text, shorten, tokenize, top_keywords

SECTOR_RULES = {
    "ЖКХ": ["отоплен", "теплосет", "мусор", "контейнер", "вод", "канал", "жкх", "свет", "электр", "авар"],
    "Дороги и транспорт": ["дорог", "автобус", "маршрут", "дтп", "пробк", "гололед", "остановк", "транспорт"],
    "Здравоохранение": ["поликлин", "врач", "мед", "больниц", "талон", "регистратур", "пациент"],
    "Образование": ["школ", "садик", "учител", "класс", "родител", "ремонт"],
    "Экология и ЧС": ["пожар", "дым", "гар", "мчс", "выброс", "запах", "задымл"],
    "Экономика и промышленность": ["зарплат", "сокращен", "предприят", "завод", "работник", "промышлен"],
    "Госуслуги и сервисы": ["мфц", "госуслуг", "электронн", "запис", "талон", "прием"],
}

SEVERITY_BY_SECTOR = {
    "Экология и ЧС": 1.0,
    "Здравоохранение": 0.9,
    "ЖКХ": 0.88,
    "Экономика и промышленность": 0.82,
    "Дороги и транспорт": 0.78,
    "Образование": 0.7,
    "Госуслуги и сервисы": 0.62,
    "Прочее": 0.55,
}

COMPLAINT_MARKERS = {"жалоб", "проблем", "очеред", "авар", "запах", "перебо", "срыв", "задерж", "отключ", "холод"}
RESOLUTION_MARKERS = {"восстанов", "устран", "нормализ", "открыли", "заверш", "опроверг", "усилили"}
BENIGN_MARKERS = {"форум", "хакатон", "конкурс", "наград", "побед", "турнир", "праздник", "литурги", "отборочн", "встретил", "выступил", "мероприят"}
ANCHOR_EXCLUDE = {
    "жители",
    "житель",
    "сообщили",
    "сообщает",
    "рассказали",
    "говорят",
    "пишут",
    "пишет",
    "ростовской",
    "области",
    "ростова",
    "ростове",
    "обновление",
    "официального",
    "официальные",
    "пользователи",
    "пользователь",
    "сегодня",
    "после",
    "часть",
    "несколько",
    "кварталах",
    "домов",
    "районе",
    "улице",
    "улица",
    "городе",
}


@dataclass
class EnrichedEvent:
    raw: RawEvent
    combined_text: str
    normalized_text: str
    tokens: set[str]
    anchor_tokens: set[str]
    sector: str
    municipality: str
    issue_score: float


@dataclass
class TopicCluster:
    events: list[EnrichedEvent] = field(default_factory=list)
    sector: str = "Прочее"
    municipalities: set[str] = field(default_factory=set)
    label: str = ""
    key_terms: set[str] = field(default_factory=set)
    anchor_terms: set[str] = field(default_factory=set)
    topic_id: str = ""

    def add(self, event: EnrichedEvent) -> None:
        self.events.append(event)
        self.sector = _majority_value([item.sector for item in self.events])
        self.municipalities = {item.municipality for item in self.events if item.municipality} or {"unknown"}
        best_label_event = max(
            self.events,
            key=lambda item: (
                item.issue_score,
                1 if item.raw.is_official else 0,
                len(item.raw.title or ""),
            ),
        )
        self.label = best_label_event.raw.title or shorten(best_label_event.combined_text, 90)
        self.key_terms = set(top_keywords([item.combined_text for item in self.events], limit=6))
        anchor_counter = Counter(token for item in self.events for token in item.anchor_tokens)
        self.anchor_terms = {token for token, _ in anchor_counter.most_common(5)}
        digest = hashlib.sha1(f"{self.label}|{self.sector}|{'|'.join(sorted(self.municipalities))}".encode("utf-8")).hexdigest()
        self.topic_id = digest[:12]


def _majority_value(values: list[str]) -> str:
    if not values:
        return "Прочее"
    return Counter(values).most_common(1)[0][0]


class AnalyticsService:
    def __init__(self, region_config: dict):
        self.region_config = region_config
        self.municipalities = region_config.get("municipalities", [])

    def build_top_issues(
        self,
        events: list[RawEvent],
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 10,
    ) -> TopIssuesResponse:
        filtered = self._filter_events(events, start, end, sector, municipality, source_type)
        topics = self._finalize_topics(self._build_clusters(filtered))
        ranked = sorted(topics, key=lambda item: item.score or 0, reverse=True)
        return TopIssuesResponse(
            generated_at=datetime.now().astimezone(),
            region=self.region_config["region_name"],
            total_topics=len(ranked),
            items=[TopIssue(rank=index + 1, topic=topic) for index, topic in enumerate(ranked[:limit])],
        )

    def build_topic_lookup(
        self,
        events: list[RawEvent],
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
    ) -> dict[str, TopicSummary]:
        filtered = self._filter_events(events, start, end, sector, municipality, source_type)
        topics = self._finalize_topics(self._build_clusters(filtered))
        return {topic.topic_id: topic for topic in topics}

    def build_problem_cards(
        self,
        events: list[RawEvent],
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 10,
    ) -> ProblemCardsResponse:
        top_issues = self.build_top_issues(events, start, end, sector, municipality, source_type, limit)
        return ProblemCardsResponse(
            generated_at=top_issues.generated_at,
            region=top_issues.region,
            total_cards=top_issues.total_topics,
            items=[self._topic_to_problem_card(item) for item in top_issues.items],
        )

    def build_trends(
        self,
        events: list[RawEvent],
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
    ) -> TrendsResponse:
        filtered = self._filter_events(events, start, end, sector, municipality, None)
        clusters = self._build_clusters(filtered)
        topics = self._finalize_topics(clusters)
        top_topic_ids = {topic.topic_id for topic in sorted(topics, key=lambda item: item.score or 0, reverse=True)[:5]}
        series: list[TrendSeries] = []
        for cluster in clusters:
            if cluster.topic_id not in top_topic_ids:
                continue
            buckets: dict[str, int] = defaultdict(int)
            for event in cluster.events:
                bucket = event.raw.published_at.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
                buckets[bucket.isoformat()] += 1
            points = [TrendPoint(bucket_start=datetime.fromisoformat(bucket), value=value) for bucket, value in sorted(buckets.items())]
            series.append(TrendSeries(topic_id=cluster.topic_id, label=cluster.label, sector=cluster.sector, points=points))
        return TrendsResponse(
            generated_at=datetime.now().astimezone(),
            region=self.region_config["region_name"],
            series=series,
        )

    def _filter_events(
        self,
        events: list[RawEvent],
        start: datetime | None,
        end: datetime | None,
        sector: str | None,
        municipality: str | None,
        source_type: str | None,
    ) -> list[RawEvent]:
        filtered: list[RawEvent] = []
        for event in events:
            if start and event.published_at < start:
                continue
            if end and event.published_at > end:
                continue
            if source_type and event.source_type != source_type.lower():
                continue
            if sector and self._classify_sector(event) != sector:
                continue
            detected = event.municipality or self._extract_municipality(f"{event.title or ''} {event.text}")
            if municipality and detected != municipality:
                continue
            filtered.append(event)
        return filtered

    def _build_clusters(self, events: list[RawEvent]) -> list[TopicCluster]:
        clusters: list[TopicCluster] = []
        enriched = [self._enrich_event(item) for item in sorted(events, key=lambda value: value.published_at)]
        for event in enriched:
            best_cluster = None
            best_score = 0.0
            for cluster in clusters:
                score = self._cluster_similarity(event, cluster)
                if score > best_score:
                    best_cluster = cluster
                    best_score = score
            if best_cluster and best_score >= 0.48:
                best_cluster.add(event)
            else:
                new_cluster = TopicCluster()
                new_cluster.add(event)
                clusters.append(new_cluster)
        return clusters

    def _enrich_event(self, event: RawEvent) -> EnrichedEvent:
        combined_text = " ".join(part for part in [event.title or "", event.text] if part)
        return EnrichedEvent(
            raw=event,
            combined_text=combined_text,
            normalized_text=normalize_text(combined_text),
            tokens=set(tokenize(combined_text)),
            anchor_tokens=self._extract_anchor_tokens(combined_text),
            sector=self._classify_sector(event),
            municipality=event.municipality or self._extract_municipality(combined_text),
            issue_score=self._score_issue_relevance(event),
        )

    def _extract_municipality(self, text: str) -> str:
        normalized = normalize_text(text)
        for item in self.municipalities:
            for alias in item.get("aliases", []):
                if normalize_text(alias) in normalized:
                    return item["name"]
        return "unknown"

    def _classify_sector(self, event: RawEvent) -> str:
        text = normalize_text(" ".join(part for part in [event.title or "", event.text] if part))
        scores = {sector: sum(1 for marker in markers if marker in text) for sector, markers in SECTOR_RULES.items()}
        best_sector = max(scores, key=scores.get)
        return best_sector if scores[best_sector] else "Прочее"

    def _score_issue_relevance(self, event: RawEvent) -> float:
        text = normalize_text(" ".join(part for part in [event.title or "", event.text] if part))
        problem_hits = sum(1 for marker in COMPLAINT_MARKERS if marker in text)
        sector_hits = sum(1 for markers in SECTOR_RULES.values() for marker in markers if marker in text)
        benign_hits = sum(1 for marker in BENIGN_MARKERS if marker in text)
        citizen_bonus = 0.15 if not event.is_official else 0.0
        raw_score = problem_hits * 0.3 + min(0.25, sector_hits * 0.05) + citizen_bonus - benign_hits * 0.18
        if event.is_official and problem_hits > 0:
            raw_score += 0.1
        return max(0.0, min(1.0, raw_score * self._score_local_relevance(text)))

    def _score_local_relevance(self, normalized_text: str) -> float:
        for item in self.municipalities:
            for alias in item.get("aliases", []):
                alias_normalized = normalize_text(alias)
                if alias_normalized and alias_normalized in normalized_text:
                    return 1.0
        if "ростовск" in normalized_text or "на дону" in normalized_text or "дон" in normalized_text:
            return 0.7
        return 0.35

    def _cluster_similarity(self, event: EnrichedEvent, cluster: TopicCluster) -> float:
        representative = cluster.events[-1]
        shared_tokens = len(event.tokens & (cluster.key_terms or representative.tokens))
        union = len(event.tokens | representative.tokens) or 1
        jaccard = shared_tokens / union
        anchor_pool = cluster.anchor_terms or representative.anchor_tokens
        anchor_overlap = len(event.anchor_tokens & anchor_pool)
        anchor_norm = max(len(event.anchor_tokens), len(anchor_pool), 1)
        anchor_score = anchor_overlap / anchor_norm
        seq_ratio = SequenceMatcher(None, event.normalized_text[:250], representative.normalized_text[:250]).ratio()
        title_ratio = 0.0
        if event.raw.title and representative.raw.title:
            title_ratio = SequenceMatcher(None, normalize_text(event.raw.title), normalize_text(representative.raw.title)).ratio()
        same_sector = 0.12 if event.sector == cluster.sector else 0.0
        same_municipality = 0.12 if event.municipality in cluster.municipalities and event.municipality != "unknown" else 0.0
        shared_signal_bonus = 0.08 if shared_tokens >= 2 else 0.0
        anchor_bonus = 0.14 if anchor_overlap >= 1 and same_sector and same_municipality else 0.0
        official_update_bonus = 0.1 if (
            same_sector
            and same_municipality
            and (event.raw.is_official or representative.raw.is_official)
            and (shared_tokens >= 1 or anchor_overlap >= 1)
        ) else 0.0
        time_gap_hours = abs((event.raw.published_at - representative.raw.published_at).total_seconds()) / 3600
        time_bonus = 0.08 if time_gap_hours <= 72 else 0.0
        same_pattern_bonus = 0.08 if (
            time_gap_hours <= 48
            and event.sector == cluster.sector
            and event.municipality in cluster.municipalities
            and (anchor_overlap >= 1 or shared_tokens >= 3)
        ) else 0.0
        return min(
            1.0,
            0.28 * seq_ratio
            + 0.3 * title_ratio
            + 0.22 * jaccard
            + 0.1 * anchor_score
            + same_sector
            + same_municipality
            + shared_signal_bonus
            + anchor_bonus
            + official_update_bonus
            + time_bonus
            + same_pattern_bonus
        )

    def _finalize_topics(self, clusters: list[TopicCluster]) -> list[TopicSummary]:
        topics = [self._cluster_to_topic(cluster) for cluster in clusters]
        return [topic for topic in topics if topic.issue_relevance >= 0.28]

    def _cluster_to_topic(self, cluster: TopicCluster) -> TopicSummary:
        cluster.events.sort(key=lambda item: item.raw.published_at)
        municipalities = sorted(cluster.municipalities)
        evidence = [
            TopicEvidence(
                event_id=item.raw.event_id or "",
                source_name=item.raw.source_name,
                source_type=item.raw.source_type,
                url=item.raw.url,
                published_at=item.raw.published_at,
                snippet=shorten(item.raw.text or item.raw.title or "", 170),
                is_official=item.raw.is_official,
                engagement=item.raw.engagement,
            )
            for item in sorted(cluster.events, key=lambda value: value.raw.published_at, reverse=True)[:6]
        ]
        bot_score = self._calculate_bot_score(cluster)
        contradiction_flag = self._detect_contradiction(cluster)
        issue_relevance = max(item.issue_score for item in cluster.events)
        score_breakdown = self._calculate_score(cluster, bot_score)
        score = (
            score_breakdown.surge * 30
            + score_breakdown.diversity * 20
            + score_breakdown.geography * 15
            + score_breakdown.severity * 15
            + score_breakdown.official_signal * 10
            + score_breakdown.citizen_volume * 10
            - score_breakdown.bot_penalty * 30
        ) * issue_relevance
        return TopicSummary(
            topic_id=cluster.topic_id,
            label=cluster.label,
            sector=cluster.sector,
            issue_relevance=round(issue_relevance, 3),
            municipalities=municipalities,
            first_seen=cluster.events[0].raw.published_at,
            last_seen=cluster.events[-1].raw.published_at,
            event_count=len(cluster.events),
            source_count=len({item.raw.source_name for item in cluster.events}),
            neutral_summary=self._build_summary(cluster, municipalities, contradiction_flag),
            evidence=evidence,
            contradiction_flag=contradiction_flag,
            bot_score=round(bot_score, 3),
            score=round(max(score, 0), 2),
            score_breakdown=score_breakdown,
            why_in_top=self._build_why_in_top(score_breakdown, cluster, contradiction_flag),
            sources=sorted({item.raw.source_name for item in cluster.events}),
            source_mix=self._build_source_mix(cluster),
        )

    def _build_source_mix(self, cluster: TopicCluster) -> SourceMix:
        counts = Counter(item.raw.source_type for item in cluster.events)
        return SourceMix(
            official=counts.get("official", 0),
            media=counts.get("media", 0),
            social=counts.get("social", 0),
            other=sum(value for key, value in counts.items() if key not in {"official", "media", "social"}),
        )

    def _calculate_score(self, cluster: TopicCluster, bot_score: float) -> ScoreBreakdown:
        now = max(item.raw.published_at for item in cluster.events)
        recent = sum(1 for item in cluster.events if item.raw.published_at >= now - timedelta(hours=24))
        previous = max(len(cluster.events) - recent, 0)
        surge = min(1.0, ((recent * 1.4) + max(recent - previous, 0)) / 5)
        diversity = min(1.0, len({item.raw.source_name for item in cluster.events}) / 4)
        known_municipalities = len([name for name in cluster.municipalities if name != "unknown"])
        geography = 0.2 if known_municipalities == 0 else min(1.0, known_municipalities / 2)
        severity = SEVERITY_BY_SECTOR.get(cluster.sector, SEVERITY_BY_SECTOR["Прочее"])
        official_signal = 1.0 if any(item.raw.is_official for item in cluster.events) else 0.0
        citizen_volume = min(1.0, len([item for item in cluster.events if not item.raw.is_official]) / 5)
        return ScoreBreakdown(
            surge=round(surge, 3),
            diversity=round(diversity, 3),
            geography=round(geography, 3),
            severity=round(severity, 3),
            official_signal=round(official_signal, 3),
            citizen_volume=round(citizen_volume, 3),
            bot_penalty=round(min(1.0, bot_score), 3),
        )

    def _calculate_bot_score(self, cluster: TopicCluster) -> float:
        social_events = [item for item in cluster.events if item.raw.source_type == "social"]
        if len(social_events) < 2:
            return 0.0
        canonical_texts = [normalize_text(item.raw.text or item.raw.title or "") for item in social_events]
        duplicate_ratio = (len(canonical_texts) - len(set(canonical_texts))) / len(social_events)
        pairwise_scores: list[float] = []
        for index, current in enumerate(canonical_texts):
            for other in canonical_texts[index + 1 :]:
                pairwise_scores.append(SequenceMatcher(None, current, other).ratio())
        near_copy_ratio = (
            sum(1 for score in pairwise_scores if score >= 0.9) / len(pairwise_scores)
            if pairwise_scores
            else 0.0
        )
        source_dominance = max(Counter(item.raw.source_name for item in social_events).values()) / len(social_events)
        hourly_bursts = Counter(
            item.raw.published_at.astimezone().replace(minute=0, second=0, microsecond=0).isoformat()
            for item in social_events
        )
        burst_ratio = max(hourly_bursts.values()) / len(social_events)
        return min(1.0, duplicate_ratio * 0.45 + near_copy_ratio * 0.25 + source_dominance * 0.15 + burst_ratio * 0.15)

    def _detect_contradiction(self, cluster: TopicCluster) -> bool:
        official_texts = [item.normalized_text for item in cluster.events if item.raw.is_official]
        citizen_texts = [item.normalized_text for item in cluster.events if not item.raw.is_official]
        official_has_resolution = any(any(marker in text for marker in RESOLUTION_MARKERS) for text in official_texts)
        citizen_has_problem = any(any(marker in text for marker in COMPLAINT_MARKERS) for text in citizen_texts)
        return official_has_resolution and citizen_has_problem

    def _build_why_in_top(self, breakdown: ScoreBreakdown, cluster: TopicCluster, contradiction_flag: bool) -> list[str]:
        reasons: list[str] = []
        if breakdown.surge >= 0.8:
            reasons.append("есть всплеск сообщений за последние 24 часа")
        if breakdown.diversity >= 0.75:
            reasons.append("тема подтверждается несколькими независимыми источниками")
        if breakdown.official_signal >= 1.0:
            reasons.append("по теме есть официальный сигнал")
        if breakdown.citizen_volume >= 0.8:
            reasons.append("заметный объём жалоб и пользовательских сообщений")
        if contradiction_flag:
            reasons.append("есть расхождение между официальным обновлением и пользовательскими сообщениями")
        if breakdown.bot_penalty >= 0.45:
            reasons.append("учтён риск однотипных или аномальных вбросов")
        return reasons[:4]

    def _build_summary(self, cluster: TopicCluster, municipalities: list[str], contradiction_flag: bool) -> str:
        sources = sorted({item.raw.source_name for item in cluster.events})
        facts = " ".join(shorten(item.raw.text or item.raw.title or "", 130) for item in sorted(cluster.events, key=lambda value: value.raw.published_at, reverse=True)[:2])
        official_presence = "Есть официальные сообщения." if any(item.raw.is_official for item in cluster.events) else "Официальных сообщений пока нет."
        contradiction_note = " Отмечено расхождение между официальной версией и сообщениями пользователей." if contradiction_flag else ""
        return (
            f"За период с {cluster.events[0].raw.published_at:%d.%m %H:%M} по {cluster.events[-1].raw.published_at:%d.%m %H:%M} "
            f"по теме «{cluster.label}» зафиксировано {len(cluster.events)} сообщений из {len(sources)} источников. "
            f"География: {', '.join(municipalities)}. Основные факты: {facts} {official_presence}{contradiction_note}"
        )

    def _topic_to_problem_card(self, issue: TopIssue) -> ProblemCard:
        topic = issue.topic
        latest_official = next((item.snippet for item in topic.evidence if item.is_official), None)
        latest_citizen = next((item.snippet for item in topic.evidence if not item.is_official), None)
        urgency = "high" if (topic.score or 0) >= 55 or topic.contradiction_flag else "medium" if (topic.score or 0) >= 40 else "watch"
        status = "mixed_signal" if topic.contradiction_flag else "official_response" if topic.source_mix.official else "citizen_escalation" if topic.source_mix.social >= 2 else "monitoring"
        key_facts = []
        seen_facts: set[str] = set()
        for item in topic.evidence:
            fact = item.snippet.strip()
            if not fact or fact in seen_facts:
                continue
            seen_facts.add(fact)
            key_facts.append(fact)
            if len(key_facts) >= 3:
                break
        return ProblemCard(
            topic_id=topic.topic_id,
            rank=issue.rank,
            title=topic.label,
            sector=topic.sector,
            municipalities=topic.municipalities,
            score=topic.score,
            urgency=urgency,
            status=status,
            summary=topic.neutral_summary,
            why_now=topic.why_in_top,
            key_facts=key_facts,
            latest_official_update=latest_official,
            latest_citizen_signal=latest_citizen,
            contradiction_flag=topic.contradiction_flag,
            bot_score=topic.bot_score,
            source_mix=topic.source_mix,
            evidence=topic.evidence[:4],
            first_seen=topic.first_seen,
            last_seen=topic.last_seen,
        )

    def _extract_anchor_tokens(self, text: str) -> set[str]:
        anchors: set[str] = set()
        for token in tokenize(text):
            if token in ANCHOR_EXCLUDE:
                continue
            if len(token) >= 5 or any(char.isdigit() for char in token):
                anchors.add(token)
        return anchors
