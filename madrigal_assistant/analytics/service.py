from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from madrigal_assistant.embeddings import EmbeddingService
from madrigal_assistant.models import (
    ProblemCard,
    ProblemCardsResponse,
    ProblemTimelineEvent,
    RawEvent,
    ScoreBreakdown,
    SimilarTopic,
    SimilarTopicsResponse,
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
    "ЖКХ": ["отоплен", "теплосет", "мусор", "контейнер", "водоснаб", "водоканал", "водопровод", "кран", "жкх", "свет", "электр"],
    "Дороги и транспорт": ["дорог", "автобус", "маршрут", "дтп", "пробк", "гололед", "остановк", "транспорт", "водител", "пешеход", "сбил", "наехал"],
    "Здравоохранение": ["поликлин", "врач", "мед", "больниц", "талон", "регистратур", "пациент"],
    "Образование": ["школ", "садик", "учител", "класс", "родител", "ремонт"],
    "Экология и ЧС": ["пожар", "дым", "гар", "мчс", "выброс", "запах", "задымл", "возгоран", "эваку", "чп", "атак", "бпла", "ракет", "дрон"],
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
MIN_CLUSTER_SIMILARITY = 0.47
MIN_TOPIC_RELEVANCE = 0.32
CLUSTER_GENERIC_TOKENS = {
    "ростов",
    "ростова",
    "ростове",
    "ростовской",
    "области",
    "района",
    "города",
    "городе",
    "дону",
    "дон",
    "россии",
    "власти",
    "правительство",
    "администрация",
    "сообщили",
    "рассказали",
    "обсудили",
    "показали",
    "человек",
    "человека",
    "люди",
    "женщина",
    "женщину",
    "мужчина",
    "девушка",
    "парень",
    "ребенок",
    "пострадали",
    "пострадал",
    "погиб",
    "погибли",
    "сегодня",
    "ночью",
    "утром",
    "вечером",
}
POSITIVE_SIGNAL_MARKERS = {
    "стартовал",
    "стартовала",
    "запустили",
    "запустят",
    "выйдет",
    "закупает",
    "обсудили",
    "награжд",
    "рассказал",
    "рассказали",
    "возглавил",
    "форум",
    "хакатон",
    "объективе",
    "итоги",
    "весной",
}
SOCIAL_NOISE_MARKERS = {
    "подпишись",
    "подписывайтесь",
    "прислать новость",
    "жиза",
    "кулич",
    "сладкоежки",
    "кумира",
    "интернет",
    "розыгрыш",
    "звездой",
    "телеграм",
    "канал",
    "подарок",
}
INCIDENT_MARKERS = {
    "пострад",
    "погиб",
    "сбили",
    "ракетн",
    "опасност",
    "взрыв",
    "пожар",
    "убий",
    "напад",
    "эваку",
    "мошенн",
    "дтп",
    "атак",
    "задержал",
    "сбежав",
}
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
    "человек",
    "человека",
    "люди",
    "женщина",
    "женщину",
    "мужчина",
    "девушка",
    "парень",
    "ребенок",
    "пострадали",
    "пострадал",
    "погиб",
    "погибли",
    "напал",
    "атаке",
    "атаку",
    "произошло",
    "произошла",
    "случилось",
    "месте",
}
TEMPORAL_TOKENS = {
    "утром",
    "вечером",
    "ночью",
    "днем",
    "днём",
    "сегодня",
    "вчера",
    "завтра",
    "апреля",
    "марта",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
    "января",
    "февраля",
}


@dataclass
class EnrichedEvent:
    raw: RawEvent
    combined_text: str
    normalized_text: str
    tokens: set[str]
    signal_tokens: set[str]
    anchor_tokens: set[str]
    sector: str
    municipality: str
    issue_score: float
    embedding: tuple[float, ...] | None = None


@dataclass
class TopicCluster:
    events: list[EnrichedEvent] = field(default_factory=list)
    sector: str = "Прочее"
    municipalities: set[str] = field(default_factory=set)
    label: str = ""
    key_terms: set[str] = field(default_factory=set)
    anchor_terms: set[str] = field(default_factory=set)
    topic_id: str = ""
    centroid_embedding: tuple[float, ...] | None = None
    embedding_count: int = 0

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
        self.key_terms = set(top_keywords([" ".join(sorted(item.signal_tokens)) for item in self.events], limit=6))
        anchor_counter = Counter(token for item in self.events for token in item.anchor_tokens)
        self.anchor_terms = {token for token, _ in anchor_counter.most_common(8)} | set(best_label_event.anchor_tokens)
        if event.embedding:
            if not self.centroid_embedding:
                self.centroid_embedding = event.embedding
                self.embedding_count = 1
            else:
                total = max(self.embedding_count, 1)
                self.centroid_embedding = _normalize_embedding_vector(tuple(
                    ((current * total) + incoming) / (total + 1)
                    for current, incoming in zip(self.centroid_embedding, event.embedding)
                ))
                self.embedding_count = total + 1
        digest = hashlib.sha1(f"{self.label}|{self.sector}|{'|'.join(sorted(self.municipalities))}".encode("utf-8")).hexdigest()
        self.topic_id = digest[:12]


def _majority_value(values: list[str]) -> str:
    if not values:
        return "Прочее"
    return Counter(values).most_common(1)[0][0]


def _normalize_embedding_vector(vector: tuple[float, ...]) -> tuple[float, ...]:
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return tuple(value / norm for value in vector)


class AnalyticsService:
    def __init__(self, region_config: dict, embedding_service: EmbeddingService | None = None):
        self.region_config = region_config
        self.municipalities = region_config.get("municipalities", [])
        self.embedding_service = embedding_service or EmbeddingService()

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

    def build_similar_topics(
        self,
        events: list[RawEvent],
        topic_id: str | None = None,
        query: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        sector: str | None = None,
        municipality: str | None = None,
        source_type: str | None = None,
        limit: int = 5,
    ) -> SimilarTopicsResponse:
        filtered = self._filter_events(events, start, end, sector, municipality, source_type)
        clusters = self._build_clusters(filtered)
        topics = [self._cluster_to_topic(cluster) for cluster in clusters]
        topics = [topic for topic in topics if topic.issue_relevance >= MIN_TOPIC_RELEVANCE]
        cluster_lookup = {cluster.topic_id: cluster for cluster in clusters}
        topic_lookup = {topic.topic_id: topic for topic in topics}

        target_topic = topic_lookup.get(topic_id) if topic_id else None
        target_cluster = cluster_lookup.get(topic_id) if topic_id else None
        target_tokens = set()
        target_embedding = None
        target_sector = None
        target_municipalities: set[str] = set()

        if target_topic and target_cluster:
            target_tokens = set(target_cluster.key_terms) | set(target_cluster.anchor_terms)
            target_embedding = target_cluster.centroid_embedding
            target_sector = target_topic.sector
            target_municipalities = set(target_topic.municipalities)
        elif query:
            target_tokens = set(tokenize(query))
            target_embedding = self.embedding_service.encode_texts([f"clustering: {query}"])[0]
        else:
            return SimilarTopicsResponse(
                generated_at=datetime.now().astimezone(),
                region=self.region_config["region_name"],
                topic_id=topic_id,
                query=query,
                embedding_layer=self.embedding_service.status().as_dict(),
                items=[],
            )

        minimum_similarity = 0.28 if query and not topic_id else 0.36
        items: list[SimilarTopic] = []
        for candidate in topics:
            if topic_id and candidate.topic_id == topic_id:
                continue
            candidate_cluster = cluster_lookup.get(candidate.topic_id)
            if not candidate_cluster:
                continue
            similarity, reasons = self._score_related_topic(
                target_embedding=target_embedding,
                target_tokens=target_tokens,
                target_sector=target_sector,
                target_municipalities=target_municipalities,
                candidate_topic=candidate,
                candidate_cluster=candidate_cluster,
            )
            if similarity < minimum_similarity:
                continue
            items.append(
                SimilarTopic(
                    topic_id=candidate.topic_id,
                    label=candidate.label,
                    sector=candidate.sector,
                    municipalities=candidate.municipalities,
                    similarity=round(similarity, 3),
                    score=candidate.score,
                    confidence=candidate.confidence,
                    verification_state=candidate.verification_state,
                    reasons=reasons,
                )
            )
        items.sort(key=lambda item: (item.similarity, item.score or 0.0), reverse=True)
        return SimilarTopicsResponse(
            generated_at=datetime.now().astimezone(),
            region=self.region_config["region_name"],
            topic_id=topic_id,
            query=query,
            embedding_layer=self.embedding_service.status().as_dict(),
            items=items[:limit],
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
        candidates = [event for event in enriched if self._is_cluster_candidate(event)]
        if not candidates:
            return []
        self._apply_embeddings(candidates)
        for event in candidates:
            best_cluster = None
            best_score = 0.0
            for cluster in clusters:
                score = self._cluster_similarity(event, cluster)
                if score > best_score:
                    best_cluster = cluster
                    best_score = score
            if best_cluster and best_score >= MIN_CLUSTER_SIMILARITY:
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
            signal_tokens=self._extract_signal_tokens(combined_text),
            anchor_tokens=self._extract_anchor_tokens(combined_text),
            sector=self._classify_sector(event),
            municipality=event.municipality or self._extract_municipality(combined_text),
            issue_score=self._score_issue_relevance(event),
        )

    def _apply_embeddings(self, events: list[EnrichedEvent]) -> None:
        if not events:
            return
        texts = [self._build_embedding_text(item) for item in events]
        for event, vector in zip(events, self.embedding_service.encode_texts(texts)):
            event.embedding = vector

    @staticmethod
    def _build_embedding_text(event: EnrichedEvent) -> str:
        parts: list[str] = []
        if event.raw.title:
            parts.append(event.raw.title)
        body = event.raw.text or ""
        if body:
            parts.append(shorten(body, 500))
        combined = " ".join(part for part in parts if part)
        return f"clustering: {combined}" if combined else ""

    def _extract_municipality(self, text: str) -> str:
        normalized = normalize_text(text)
        best_match = "unknown"
        best_length = 0
        for item in self.municipalities:
            aliases = sorted(item.get("aliases", []), key=len, reverse=True)
            for alias in aliases:
                alias_normalized = normalize_text(alias).strip()
                if not alias_normalized:
                    continue
                pattern = rf"(?<!\w){re.escape(alias_normalized)}(?!\w)"
                if re.search(pattern, normalized) and len(alias_normalized) > best_length:
                    best_match = item["name"]
                    best_length = len(alias_normalized)
        return best_match

    def _classify_sector(self, event: RawEvent) -> str:
        text = normalize_text(" ".join(part for part in [event.title or "", event.text] if part))
        tokens = tokenize(text)
        scores = {sector: self._count_sector_hits(tokens, markers) for sector, markers in SECTOR_RULES.items()}
        best_sector = max(scores, key=lambda sector: (scores[sector], self._sector_tiebreak_score(sector, text)))
        return best_sector if scores[best_sector] else "Прочее"

    def _score_issue_relevance(self, event: RawEvent) -> float:
        text = normalize_text(" ".join(part for part in [event.title or "", event.text] if part))
        problem_hits = sum(1 for marker in COMPLAINT_MARKERS if marker in text)
        incident_hits = sum(1 for marker in INCIDENT_MARKERS if marker in text)
        sector_hits = sum(1 for markers in SECTOR_RULES.values() for marker in markers if marker in text)
        benign_hits = sum(1 for marker in BENIGN_MARKERS if marker in text)
        positive_hits = sum(1 for marker in POSITIVE_SIGNAL_MARKERS if marker in text)
        social_noise_hits = sum(1 for marker in SOCIAL_NOISE_MARKERS if marker in text)
        citizen_bonus = 0.15 if not event.is_official else 0.0
        raw_score = (
            problem_hits * 0.3
            + incident_hits * 0.18
            + min(0.25, sector_hits * 0.05)
            + citizen_bonus
            - benign_hits * 0.18
            - positive_hits * (0.14 if event.is_official else 0.08)
            - social_noise_hits * (0.16 if event.source_type == "social" else 0.08)
        )
        if event.is_official and problem_hits > 0:
            raw_score += 0.1
        if event.is_official and problem_hits == 0 and incident_hits == 0 and positive_hits >= 1:
            raw_score -= 0.2
        if event.source_type == "social" and problem_hits == 0 and incident_hits == 0 and sector_hits == 0:
            raw_score -= 0.22
        return max(0.0, min(1.0, raw_score * self._score_local_relevance(text)))

    def _is_cluster_candidate(self, event: EnrichedEvent) -> bool:
        text = event.normalized_text
        problem_hits = sum(1 for marker in COMPLAINT_MARKERS if marker in text)
        incident_hits = sum(1 for marker in INCIDENT_MARKERS if marker in text)
        resolution_hits = sum(1 for marker in RESOLUTION_MARKERS if marker in text)
        social_noise_hits = sum(1 for marker in SOCIAL_NOISE_MARKERS if marker in text)
        has_known_geo = event.municipality != "unknown"
        has_defined_sector = event.sector != "Прочее"

        if social_noise_hits >= 2 and problem_hits == 0 and incident_hits == 0:
            return False
        if event.raw.is_official:
            return event.issue_score >= 0.16 or problem_hits > 0 or incident_hits > 0 or resolution_hits > 0
        if event.raw.source_type == "social" and social_noise_hits >= 1 and problem_hits == 0 and incident_hits == 0:
            return False
        if event.issue_score >= 0.32:
            return True
        if event.municipality == "unknown" and (problem_hits > 0 or incident_hits > 0) and event.issue_score >= 0.14:
            return True
        if (problem_hits > 0 or incident_hits > 0 or resolution_hits > 0) and event.issue_score >= 0.18:
            return True
        return has_defined_sector and has_known_geo and event.issue_score >= 0.2

    def _score_local_relevance(self, normalized_text: str) -> float:
        for item in self.municipalities:
            for alias in item.get("aliases", []):
                alias_normalized = normalize_text(alias)
                pattern = rf"(?<!\w){re.escape(alias_normalized)}(?!\w)"
                if alias_normalized and re.search(pattern, normalized_text):
                    return 1.0
        if "ростовск" in normalized_text or "на дону" in normalized_text or "дон" in normalized_text:
            return 0.7
        return 0.45

    def _extract_signal_tokens(self, text: str) -> set[str]:
        return {
            token
            for token in tokenize(text)
            if token not in CLUSTER_GENERIC_TOKENS
            and token not in BENIGN_MARKERS
            and token not in TEMPORAL_TOKENS
            and len(token) >= 4
        }

    def _passes_cluster_gate(
        self,
        event: EnrichedEvent,
        cluster: TopicCluster,
        shared_tokens: int,
        anchor_overlap: int,
        title_ratio: float,
        jaccard: float,
        seq_ratio: float,
        semantic_similarity: float,
    ) -> bool:
        known_cluster_municipalities = {item for item in cluster.municipalities if item != "unknown"}
        municipality_conflict = (
            event.municipality != "unknown"
            and known_cluster_municipalities
            and event.municipality not in known_cluster_municipalities
        )
        cluster_issue_avg = sum(item.issue_score for item in cluster.events) / max(len(cluster.events), 1)
        same_known_municipality = event.municipality != "unknown" and event.municipality in cluster.municipalities
        both_unknown_geo = event.municipality == "unknown" and not known_cluster_municipalities
        strong_anchor_pair = anchor_overlap >= 2
        if municipality_conflict:
            return title_ratio >= 0.88 and anchor_overlap >= 2
        if event.issue_score < 0.28 and cluster_issue_avg >= 0.5 and title_ratio < 0.8 and anchor_overlap < 2:
            return False

        strong_title_match = title_ratio >= 0.72
        strong_anchor_match = anchor_overlap >= 1
        shared_context_match = shared_tokens >= 2 and (jaccard >= 0.16 or seq_ratio >= 0.45)
        same_sector_known = event.sector == cluster.sector and event.sector != "Прочее"
        if same_sector_known and same_known_municipality and (anchor_overlap >= 1 or shared_tokens >= 2) and (title_ratio >= 0.28 or semantic_similarity >= 0.58):
            return True
        sector_guided_match = same_sector_known and shared_tokens >= 2 and (anchor_overlap >= 1 or title_ratio >= 0.42)
        semantic_match = semantic_similarity >= 0.76 and (
            anchor_overlap >= 1
            or title_ratio >= 0.42
            or (same_sector_known and same_known_municipality and shared_tokens >= 2)
        )
        strong_semantic_match = semantic_similarity >= 0.84 and not municipality_conflict and (
            anchor_overlap >= 1
            or title_ratio >= 0.55
            or (same_known_municipality and shared_tokens >= 2)
        )
        if same_sector_known and same_known_municipality and shared_tokens == 0 and anchor_overlap == 0 and title_ratio < 0.35:
            return False
        if shared_tokens == 0 and anchor_overlap == 0 and title_ratio < 0.32 and semantic_similarity < 0.9:
            return False

        if cluster.sector == "Прочее" and event.sector == "Прочее":
            if strong_title_match:
                return True
            if strong_anchor_pair and (same_known_municipality or shared_tokens >= 2):
                return True
            if strong_semantic_match and (strong_anchor_pair or title_ratio >= 0.62 or same_known_municipality):
                return True
            if both_unknown_geo and strong_anchor_pair and seq_ratio >= 0.34:
                return True
            return shared_tokens >= 4 and jaccard >= 0.26 and anchor_overlap >= 1

        return strong_anchor_match or strong_title_match or shared_context_match or sector_guided_match or semantic_match or strong_semantic_match

    def _calculate_confidence(self, cluster: TopicCluster) -> float:
        if not cluster.events:
            return 0.0
        if len(cluster.events) == 1:
            single_event = cluster.events[0]
            municipality_bonus = 0.1 if single_event.municipality != "unknown" else 0.0
            source_bonus = 0.08 if single_event.raw.is_official else 0.0
            return round(min(1.0, 0.42 + municipality_bonus + source_bonus), 3)

        pair_scores: list[float] = []
        anchor_scores: list[float] = []
        for index, current in enumerate(cluster.events):
            current_tokens = current.signal_tokens or current.tokens
            for other in cluster.events[index + 1 :]:
                other_tokens = other.signal_tokens or other.tokens
                union = len(current_tokens | other_tokens) or 1
                lexical_overlap = len(current_tokens & other_tokens) / union
                title_ratio = 0.0
                if current.raw.title and other.raw.title:
                    title_ratio = SequenceMatcher(None, normalize_text(current.raw.title), normalize_text(other.raw.title)).ratio()
                anchor_union = len(current.anchor_tokens | other.anchor_tokens) or 1
                anchor_scores.append(len(current.anchor_tokens & other.anchor_tokens) / anchor_union)
                pair_scores.append(lexical_overlap * 0.45 + title_ratio * 0.35 + anchor_scores[-1] * 0.2)

        average_pair = sum(pair_scores) / len(pair_scores) if pair_scores else 0.0
        average_anchor = sum(anchor_scores) / len(anchor_scores) if anchor_scores else 0.0
        source_bonus = min(0.16, len({item.raw.source_name for item in cluster.events}) * 0.04)
        municipality_bonus = 0.08 if any(item.municipality != "unknown" for item in cluster.events) else 0.0
        official_bonus = 0.06 if any(item.raw.is_official for item in cluster.events) else 0.0
        event_bonus = min(0.12, len(cluster.events) * 0.02)
        confidence = 0.32 + average_pair * 0.36 + average_anchor * 0.16 + source_bonus + municipality_bonus + official_bonus + event_bonus
        return round(min(1.0, confidence), 3)

    def _detect_trend(self, cluster: TopicCluster, breakdown: ScoreBreakdown, contradiction_flag: bool) -> str:
        if contradiction_flag:
            return "mixed"
        latest_event = max(cluster.events, key=lambda item: item.raw.published_at)
        if latest_event.raw.is_official and any(marker in latest_event.normalized_text for marker in RESOLUTION_MARKERS):
            return "resolving"
        if breakdown.surge >= 0.72:
            return "rising"
        if breakdown.citizen_volume >= 0.8 and breakdown.official_signal == 0:
            return "escalating"
        return "stable"

    def _build_verification_state(self, cluster: TopicCluster) -> str:
        source_types = {item.raw.source_type for item in cluster.events}
        source_count = len({item.raw.source_name for item in cluster.events})
        has_official = any(item.raw.is_official for item in cluster.events)
        has_social = "social" in source_types
        has_media = "media" in source_types
        if has_official and has_social and has_media:
            return "triangulated"
        if has_official and (has_social or has_media):
            return "official_plus_public"
        if source_count >= 3:
            return "multi_source"
        return "single_source"

    def _cluster_similarity(self, event: EnrichedEvent, cluster: TopicCluster) -> float:
        representative = cluster.events[-1]
        comparison_tokens = cluster.key_terms or representative.signal_tokens or representative.tokens
        event_tokens = event.signal_tokens or event.tokens
        reference_tokens = representative.signal_tokens or representative.tokens
        shared_tokens = len(event_tokens & comparison_tokens)
        union = len(event_tokens | reference_tokens) or 1
        jaccard = shared_tokens / union
        anchor_pool = cluster.anchor_terms or representative.anchor_tokens
        anchor_overlap = len(event.anchor_tokens & anchor_pool)
        anchor_norm = max(len(event.anchor_tokens), len(anchor_pool), 1)
        anchor_score = anchor_overlap / anchor_norm
        seq_ratio = SequenceMatcher(None, event.normalized_text[:250], representative.normalized_text[:250]).ratio()
        title_ratio = 0.0
        if event.raw.title and representative.raw.title:
            title_ratio = SequenceMatcher(None, normalize_text(event.raw.title), normalize_text(representative.raw.title)).ratio()
        semantic_similarity = self._semantic_similarity(event, cluster, representative)
        if not self._passes_cluster_gate(event, cluster, shared_tokens, anchor_overlap, title_ratio, jaccard, seq_ratio, semantic_similarity):
            return 0.0
        same_sector = 0.12 if event.sector == cluster.sector else 0.0
        same_municipality = 0.12 if event.municipality in cluster.municipalities and event.municipality != "unknown" else 0.0
        shared_signal_bonus = 0.08 if shared_tokens >= 2 else 0.0
        anchor_bonus = 0.14 if anchor_overlap >= 1 and same_sector and same_municipality else 0.0
        semantic_bonus = 0.12 if semantic_similarity >= 0.74 else 0.0
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
            and (anchor_overlap >= 1 or (shared_tokens >= 2 and title_ratio >= 0.22))
        ) else 0.0
        return min(
            1.0,
            0.24 * seq_ratio
            + 0.24 * title_ratio
            + 0.18 * jaccard
            + 0.22 * semantic_similarity
            + 0.1 * anchor_score
            + same_sector
            + same_municipality
            + shared_signal_bonus
            + anchor_bonus
            + semantic_bonus
            + official_update_bonus
            + time_bonus
            + same_pattern_bonus
        )

    def _semantic_similarity(self, event: EnrichedEvent, cluster: TopicCluster, representative: EnrichedEvent) -> float:
        reference_embedding = cluster.centroid_embedding or representative.embedding
        return self.embedding_service.cosine_similarity(event.embedding, reference_embedding)

    def _score_related_topic(
        self,
        target_embedding: tuple[float, ...] | None,
        target_tokens: set[str],
        target_sector: str | None,
        target_municipalities: set[str],
        candidate_topic: TopicSummary,
        candidate_cluster: TopicCluster,
    ) -> tuple[float, list[str]]:
        candidate_tokens = set(candidate_cluster.key_terms) | set(candidate_cluster.anchor_terms)
        lexical_union = len(target_tokens | candidate_tokens) or 1
        lexical_overlap = len(target_tokens & candidate_tokens) / lexical_union if target_tokens else 0.0
        semantic_similarity = self.embedding_service.cosine_similarity(target_embedding, candidate_cluster.centroid_embedding)
        municipality_overlap = (
            len(target_municipalities & set(candidate_topic.municipalities)) / max(len(target_municipalities | set(candidate_topic.municipalities)), 1)
            if target_municipalities
            else 0.0
        )
        sector_overlap = 1.0 if target_sector and target_sector == candidate_topic.sector else 0.0
        score = (
            semantic_similarity * 0.65
            + lexical_overlap * 0.2
            + municipality_overlap * 0.1
            + sector_overlap * 0.05
        )
        reasons: list[str] = []
        if semantic_similarity >= 0.7:
            reasons.append("похожа по смыслу и формулировкам")
        if lexical_overlap >= 0.18:
            reasons.append("пересекаются ключевые слова")
        if municipality_overlap > 0:
            reasons.append("есть совпадение по географии")
        if sector_overlap:
            reasons.append("совпадает сфера проблемы")
        return score, reasons[:3]

    def _topic_issue_relevance(self, cluster: TopicCluster) -> float:
        scores = [item.issue_score for item in cluster.events]
        if not scores:
            return 0.0
        top_score = max(scores)
        average_score = sum(scores) / len(scores)
        relevant_ratio = sum(1 for score in scores if score >= 0.35) / len(scores)
        official_ratio = sum(1 for item in cluster.events if item.raw.is_official) / len(cluster.events)
        source_diversity = min(1.0, len({item.raw.source_name for item in cluster.events}) / 3)
        citizen_ratio = sum(1 for item in cluster.events if not item.raw.is_official) / len(cluster.events)
        relevance = (
            top_score * 0.35
            + average_score * 0.25
            + relevant_ratio * 0.15
            + official_ratio * 0.05
            + source_diversity * 0.1
            + citizen_ratio * 0.1
        )
        if len(cluster.events) == 1:
            only_event = cluster.events[0]
            complaint_signal = any(marker in only_event.normalized_text for marker in COMPLAINT_MARKERS | INCIDENT_MARKERS)
            if complaint_signal and top_score >= 0.2:
                relevance = max(relevance, 0.28 + top_score * 0.5)
        if average_score < 0.18 and relevant_ratio < 0.4:
            relevance *= 0.6
        return round(min(1.0, relevance), 3)

    def _finalize_topics(self, clusters: list[TopicCluster]) -> list[TopicSummary]:
        topics = [self._cluster_to_topic(cluster) for cluster in clusters]
        return [topic for topic in topics if topic.issue_relevance >= MIN_TOPIC_RELEVANCE]

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
        issue_relevance = self._topic_issue_relevance(cluster)
        score_breakdown = self._calculate_score(cluster, bot_score)
        confidence = self._calculate_confidence(cluster)
        trend = self._detect_trend(cluster, score_breakdown, contradiction_flag)
        verification_state = self._build_verification_state(cluster)
        score = (
            score_breakdown.surge * 30
            + score_breakdown.diversity * 20
            + score_breakdown.geography * 15
            + score_breakdown.severity * 15
            + score_breakdown.official_signal * 10
            + score_breakdown.citizen_volume * 10
            - score_breakdown.bot_penalty * 30
        ) * issue_relevance * (0.55 + confidence * 0.45)
        return TopicSummary(
            topic_id=cluster.topic_id,
            label=cluster.label,
            sector=cluster.sector,
            issue_relevance=round(issue_relevance, 3),
            confidence=confidence,
            trend=trend,
            verification_state=verification_state,
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
        urgency = "high" if (topic.score or 0) >= 52 or topic.contradiction_flag else "medium" if (topic.score or 0) >= 34 else "watch"
        if topic.contradiction_flag:
            status = "mixed_signal"
        elif topic.trend == "resolving":
            status = "resolving"
        elif topic.trend == "escalating":
            status = "citizen_escalation"
        elif topic.verification_state in {"triangulated", "official_plus_public"}:
            status = "verified_multi_source"
        else:
            status = "monitoring"
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
            primary_municipality=topic.municipalities[0] if topic.municipalities else "unknown",
            score=topic.score,
            confidence=topic.confidence,
            trend=topic.trend,
            verification_state=topic.verification_state,
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
            timeline=self._build_problem_timeline(topic.evidence),
            first_seen=topic.first_seen,
            last_seen=topic.last_seen,
        )

    def _extract_anchor_tokens(self, text: str) -> set[str]:
        anchors: set[str] = set()
        for token in tokenize(text):
            if token in ANCHOR_EXCLUDE or token in TEMPORAL_TOKENS:
                continue
            if len(token) >= 5 or any(char.isdigit() for char in token):
                anchors.add(token)
        return anchors

    @staticmethod
    def _count_sector_hits(tokens: list[str], markers: list[str]) -> int:
        hits = 0
        for marker in markers:
            if marker in {"водоснаб", "водоканал", "водопровод", "кран"}:
                if any(token.startswith(marker) for token in tokens):
                    hits += 1
                elif marker == "кран" and any(token in {"кран", "кранах", "крана"} for token in tokens):
                    hits += 1
                continue
            if any(token.startswith(marker) for token in tokens):
                hits += 1
        return hits

    @staticmethod
    def _sector_tiebreak_score(sector: str, normalized_text: str) -> tuple[int, int]:
        priority = {
            "Экология и ЧС": 5,
            "Дороги и транспорт": 4,
            "Здравоохранение": 3,
            "ЖКХ": 2,
            "Госуслуги и сервисы": 1,
            "Образование": 1,
            "Экономика и промышленность": 1,
            "Прочее": 0,
        }
        indicator_bonus = 0
        if sector == "Дороги и транспорт" and any(marker in normalized_text for marker in ("дтп", "авар", "сбил", "наехал", "маршрут", "автобус")):
            indicator_bonus = 2
        elif sector == "Экология и ЧС" and any(marker in normalized_text for marker in ("пожар", "дым", "гар", "мчс", "чп", "атак", "бпла")):
            indicator_bonus = 2
        elif sector == "ЖКХ" and any(marker in normalized_text for marker in ("мусор", "контейнер", "отоплен", "теплосет", "электр", "свет", "водоснаб", "водоканал", "водопровод", "кран")):
            indicator_bonus = 2
        return indicator_bonus, priority.get(sector, 0)

    def _build_problem_timeline(self, evidence: list[TopicEvidence]) -> list[ProblemTimelineEvent]:
        timeline: list[ProblemTimelineEvent] = []
        for item in sorted(evidence, key=lambda value: value.published_at):
            if item.is_official:
                signal_kind = "official_update"
            elif item.source_type == "social":
                signal_kind = "citizen_signal"
            else:
                signal_kind = "media_report"
            timeline.append(
                ProblemTimelineEvent(
                    published_at=item.published_at,
                    source_name=item.source_name,
                    source_type=item.source_type,
                    signal_kind=signal_kind,
                    snippet=item.snippet,
                    url=item.url,
                )
            )
        return timeline
